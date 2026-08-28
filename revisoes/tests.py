import json

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from ia.schemas import EtapaGerada, PassoGerado, PlanoGerado
from projetos.models import Passo, Projeto
from projetos.servicos import salvar_plano
from revisoes.models import Revisao, Submissao


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


@pytest.fixture
def passos(aluno):
    projeto = Projeto.objects.create(usuario=aluno, titulo="Lista", objetivo="Tarefas.")
    salvar_plano(
        projeto,
        PlanoGerado(
            resumo="r",
            etapas=[
                EtapaGerada(
                    titulo="e",
                    passos=[
                        PassoGerado(
                            titulo=f"Passo {i}",
                            o_que_fazer="faça",
                            como_fazer="assim",
                            teoria="porque",
                            criterios_aceite=["o teste passa"],
                        )
                        for i in (1, 2)
                    ],
                )
            ],
        ),
        "fake",
    )
    return list(Passo.objects.filter(etapa__plano__projeto=projeto))


def _eventos(resposta):
    conteudo = resposta.streaming_content
    if hasattr(conteudo, "__aiter__"):

        async def drenar():
            return b"".join([bloco async for bloco in conteudo])

        bruto = async_to_sync(drenar)().decode()
    else:
        bruto = b"".join(conteudo).decode()

    saida = []
    for bloco in bruto.split("\n\n"):
        linhas = [l for l in bloco.splitlines() if l and not l.startswith(":")]
        if len(linhas) == 2:
            saida.append((linhas[0].removeprefix("event: "), json.loads(linhas[1].removeprefix("data: "))))
    return saida


@pytest.mark.django_db(transaction=True)
def test_codigo_aprovado_conclui_o_passo_e_libera_o_proximo(client, aluno, passos):
    primeiro, segundo = passos
    client.force_login(aluno)

    resposta = client.post(f"/revisoes/passo/{primeiro.pk}/submeter/", {"conteudo": "def somar(a, b):\n    return a + b\n"})
    submissao = Submissao.objects.get()
    assert resposta["Location"] == f"/revisoes/aguardar/{submissao.pk}/"

    eventos = _eventos(client.get(f"/revisoes/aguardar/{submissao.pk}/stream/"))
    assert eventos[-1][0] == "fim"

    revisao = Revisao.objects.get()
    primeiro.refresh_from_db()
    segundo.refresh_from_db()
    assert revisao.veredito == "atende"
    assert primeiro.status == Passo.Status.CONCLUIDO
    assert primeiro.concluido_manualmente is False
    assert segundo.status == Passo.Status.DISPONIVEL


@pytest.mark.django_db(transaction=True)
def test_codigo_reprovado_deixa_o_passo_em_revisao(client, aluno, passos):
    """Reprovado não volta a 'disponível': fica em revisão, e a lista de
    critérios diz o que falta."""
    primeiro, segundo = passos
    client.force_login(aluno)

    client.post(f"/revisoes/passo/{primeiro.pk}/submeter/", {"conteudo": "def somar(a, b):\n    pass  # TODO\n"})
    submissao = Submissao.objects.get()
    _eventos(client.get(f"/revisoes/aguardar/{submissao.pk}/stream/"))

    revisao = Revisao.objects.get()
    primeiro.refresh_from_db()
    segundo.refresh_from_db()
    assert revisao.veredito == "nao_atende"
    assert revisao.problemas[0]["severidade"] == "bloqueia"
    assert primeiro.status == Passo.Status.EM_REVISAO
    assert segundo.status == Passo.Status.BLOQUEADO


def test_submissao_vazia_nao_cria_registro(client, aluno, passos):
    client.force_login(aluno)
    client.post(f"/revisoes/passo/{passos[0].pk}/submeter/", {"conteudo": "   "})
    assert Submissao.objects.count() == 0


def test_codigo_grande_demais_e_recusado_com_orientacao(client, aluno, passos):
    """Truncar em silêncio daria uma revisão sobre metade do código, sem
    ninguém saber. Recusar com instrução é mais honesto."""
    from revisoes.views import MAX_CARACTERES

    client.force_login(aluno)
    resposta = client.post(
        f"/revisoes/passo/{passos[0].pk}/submeter/",
        {"conteudo": "x" * (MAX_CARACTERES + 1)},
        follow=True,
    )
    assert Submissao.objects.count() == 0
    assert any("grande demais" in str(m) for m in resposta.context["messages"])


def test_revisao_de_outro_usuario_devolve_404(client, aluno, passos, db):
    submissao = Submissao.objects.create(passo=passos[0], usuario=aluno, conteudo="x")
    outro = get_user_model().objects.create_user("outro", password="senha-de-teste-123")
    client.force_login(outro)
    assert client.get(f"/revisoes/aguardar/{submissao.pk}/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_submissao_grande_demais_e_recusada_antes_da_chamada(client, aluno, passos, settings):
    """O limite de caracteres da view pega o exagero óbvio; este pega o caso em
    que o texto cabe mas o pedido, com plano e contexto junto, não."""
    settings.IA_MAX_TOKENS_SUBMISSAO = 50

    client.force_login(aluno)
    client.post(f"/revisoes/passo/{passos[0].pk}/submeter/", {"conteudo": "x " * 2000})
    submissao = Submissao.objects.get()

    eventos = _eventos(client.get(f"/revisoes/aguardar/{submissao.pk}/stream/"))
    assert eventos[-1][0] == "erro"
    assert "revisão útil" in eventos[-1][1]["mensagem"]
    assert Revisao.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_revisao_aprovada_leva_ao_proximo_passo(client, aluno, passos):
    """O botão dizia 'ver o próximo passo' e levava ao plano. De onde a pessoa
    tinha acabado de sair."""
    primeiro, segundo = passos
    client.force_login(aluno)

    client.post(f"/revisoes/passo/{primeiro.pk}/submeter/", {"conteudo": "def somar(a, b):\n    return a + b\n"})
    submissao = Submissao.objects.get()
    _eventos(client.get(f"/revisoes/aguardar/{submissao.pk}/stream/"))

    conteudo = client.get(f"/revisoes/{Revisao.objects.get().pk}/").content
    assert f'href="/projetos/passo/{segundo.pk}/"'.encode() in conteudo
