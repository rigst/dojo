import json

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from ia.schemas import EtapaGerada, PassoGerado, PlanoGerado
from mentoria.models import Conversa, Mensagem
from mentoria.servicos import historico_para_api, registrar_pergunta, registrar_resposta
from projetos.models import Projeto
from projetos.servicos import salvar_plano


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


@pytest.fixture
def projeto(aluno):
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
                            titulo="Primeiro passo",
                            o_que_fazer="faça",
                            como_fazer="assim",
                            teoria="porque",
                            o_que_enviar="o trecho",
                            criterios_aceite=["roda"],
                        )
                    ],
                )
            ],
        ),
        "fake",
    )
    return projeto


def _corpo(resposta):
    """Drena o corpo do stream.

    A view é assíncrona, então `streaming_content` é um iterador assíncrono.
    Juntar com um for comum levanta TypeError e não diz por quê.
    """
    conteudo = resposta.streaming_content
    if hasattr(conteudo, "__aiter__"):

        async def drenar():
            return b"".join([bloco async for bloco in conteudo])

        return async_to_sync(drenar)()
    return b"".join(conteudo)


def _eventos(resposta):
    """Quebra o corpo do SSE em (evento, dados). Batimento vira comentário e é
    descartado, que é o que o navegador também faz."""
    bruto = _corpo(resposta).decode()
    saida = []
    for bloco in bruto.split("\n\n"):
        linhas = [linha for linha in bloco.splitlines() if linha and not linha.startswith(":")]
        if len(linhas) == 2:
            saida.append(
                (linhas[0].removeprefix("event: "), json.loads(linhas[1].removeprefix("data: ")))
            )
    return saida


@pytest.mark.django_db(transaction=True)
def test_stream_responde_em_pedacos_e_grava_a_conversa(client, aluno, projeto):
    client.force_login(aluno)
    resposta = client.get(
        f"/projetos/{projeto.pk}/chat/stream/", {"pergunta": "por que migration?"}
    )

    eventos = _eventos(resposta)
    tipos = [e for e, _ in eventos]
    # Mais de um delta é o ponto: se chegasse tudo de uma vez, o streaming não
    # estaria funcionando. Estaria só parecendo funcionar.
    assert tipos.count("delta") > 1
    assert tipos[-1] == "fim"

    conversa = Conversa.objects.get(projeto=projeto)
    papeis = list(conversa.mensagens.values_list("papel", flat=True))
    assert papeis == ["user", "assistant"]

    mentor = conversa.mensagens.last()
    assert mentor.custo_usd > 0
    assert mentor.tokens_saida == 500
    assert mentor.stop_reason == "end_turn"


@pytest.mark.django_db(transaction=True)
def test_stream_sem_pergunta_recusa(client, aluno, projeto):
    client.force_login(aluno)
    assert client.get(f"/projetos/{projeto.pk}/chat/stream/").status_code == 400


@pytest.mark.django_db(transaction=True)
def test_stream_de_projeto_alheio_devolve_404(client, projeto, db):
    outro = get_user_model().objects.create_user("outro", password="senha-de-teste-123")
    client.force_login(outro)
    resposta = client.get(f"/projetos/{projeto.pk}/chat/stream/", {"pergunta": "oi"})
    assert resposta.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_quota_estourada_barra_antes_de_gastar(client, aluno, projeto, settings):
    from ia.contabilidade import uso_do_mes

    settings.IA_LIMITE_MENSAL_USD = 0.01
    uso = uso_do_mes(aluno)
    uso.custo_usd = 5
    uso.save()

    client.force_login(aluno)
    resposta = client.get(f"/projetos/{projeto.pk}/chat/stream/", {"pergunta": "oi"})

    eventos = _eventos(resposta)
    assert eventos[0][0] == "erro"
    assert "limite" in eventos[0][1]["mensagem"]
    # Nada foi gravado: a pergunta nem chegou a virar mensagem.
    assert Mensagem.objects.count() == 0


def test_historico_respeita_a_janela(aluno, projeto, settings):
    """O plano inteiro já vai no bloco cacheado; o histórico só dá continuidade.
    Mandar tudo desde o começo encareceria cada turno."""
    from mentoria import servicos

    conversa = Conversa.objects.create(projeto=projeto)
    for i in range(servicos.JANELA_MENSAGENS + 5):
        registrar_pergunta(conversa, f"pergunta {i}")

    historico = historico_para_api(conversa)
    assert len(historico) == servicos.JANELA_MENSAGENS
    # E a janela pega as mais recentes, na ordem certa.
    assert historico[-1]["content"] == f"pergunta {servicos.JANELA_MENSAGENS + 4}"


@pytest.mark.django_db(transaction=True)
def test_cada_passo_tem_a_propria_conversa_separada(client, aluno, projeto):
    """Um chat por passo: a pergunta feita num passo não aparece na conversa
    de outro, nem na conversa geral do projeto."""
    from projetos.models import Passo

    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    segundo = Passo.objects.create(
        etapa=primeiro.etapa, ordem=2, titulo="Segundo passo", status=Passo.Status.DISPONIVEL
    )

    client.force_login(aluno)
    _eventos(
        client.get(
            f"/projetos/{projeto.pk}/chat/stream/",
            {"pergunta": "dúvida do primeiro", "passo": primeiro.pk},
        )
    )
    _eventos(
        client.get(
            f"/projetos/{projeto.pk}/chat/stream/",
            {"pergunta": "dúvida do segundo", "passo": segundo.pk},
        )
    )

    conversa_1 = Conversa.objects.get(passo=primeiro)
    conversa_2 = Conversa.objects.get(passo=segundo)
    assert conversa_1.pk != conversa_2.pk
    assert conversa_1.mensagens.first().conteudo == "dúvida do primeiro"
    assert conversa_2.mensagens.first().conteudo == "dúvida do segundo"

    # E nenhuma das duas é a conversa geral: aquela só existe quando alguém
    # pergunta sem um passo em foco.
    assert not Conversa.objects.filter(projeto=projeto, passo=None).exists()


def test_resposta_interrompida_e_gravada_com_o_parcial(aluno, projeto):
    """O que já foi gerado foi cobrado. Não gravar o parcial faria o gasto
    sumir da tela sem sumir da fatura."""
    from ia.contabilidade import Uso

    conversa = Conversa.objects.create(projeto=projeto)
    mensagem = registrar_resposta(
        conversa,
        "metade da explicação",
        None,
        Uso(modelo="fake", entrada=10, saida=5),
        "",
        "cancelado",
    )
    assert mensagem.erro == "cancelado"
    assert mensagem.conteudo == "metade da explicação"
    assert mensagem.custo_usd > 0


def test_str_da_mensagem_traz_papel_e_inicio_do_conteudo(projeto):
    conversa = Conversa.objects.create(projeto=projeto)
    mensagem = Mensagem.objects.create(
        conversa=conversa, papel=Mensagem.Papel.ALUNO, conteudo="a" * 80
    )
    # Trunca em 60: no admin uma resposta longa empurraria a coluna toda.
    assert str(mensagem) == f"{mensagem.get_papel_display()}: {'a' * 60}"


def test_str_da_conversa_distingue_geral_de_passo(projeto):
    """As duas conversas convivem no admin; sem distinguir, viram linhas iguais."""
    from projetos.models import Passo

    geral = Conversa.objects.create(projeto=projeto)
    assert str(geral) == f"Conversa geral de {projeto}"

    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    do_passo = Conversa.objects.create(projeto=projeto, passo=passo)
    assert str(do_passo) == f"Conversa de {passo}"
