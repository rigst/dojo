import pytest
from django.contrib.auth import get_user_model

from projetos.models import Passo, Plano, Projeto, Stack
from projetos.servicos import salvar_plano
from ia.schemas import EtapaGerada, PassoGerado, PlanoGerado


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


@pytest.fixture
def outro(db):
    return get_user_model().objects.create_user("outro", password="senha-de-teste-123")


@pytest.fixture
def projeto(aluno):
    p = Projeto.objects.create(usuario=aluno, titulo="Lista de tarefas", objetivo="Um app de tarefas.")
    p.stacks.add(Stack.objects.create(nome="Django", categoria=Stack.Categoria.FRAMEWORK))
    return p


def _gerado(qtd_passos=3):
    return PlanoGerado(
        resumo="Do esqueleto ao deploy.",
        etapas=[
            EtapaGerada(
                titulo="Esqueleto",
                objetivo="Ter algo de pé.",
                passos=[
                    PassoGerado(
                        titulo=f"Passo {i}",
                        o_que_fazer="faça",
                        como_fazer="assim",
                        teoria="porque",
                        criterios_aceite=[f"critério {i}"],
                    )
                    for i in range(1, qtd_passos + 1)
                ],
            )
        ],
    )


def test_so_o_primeiro_passo_nasce_aberto(projeto):
    """A fila é o que faz o app ser passo a passo. Se todos nascessem
    disponíveis, o plano viraria uma lista de tarefas."""
    salvar_plano(projeto, _gerado(), "fake")

    status = list(Passo.objects.filter(etapa__plano__projeto=projeto).values_list("status", flat=True))
    assert status == [Passo.Status.DISPONIVEL, Passo.Status.BLOQUEADO, Passo.Status.BLOQUEADO]


def test_replanejar_versiona_em_vez_de_sobrescrever(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    salvar_plano(projeto, _gerado(2), "fake")

    assert projeto.planos.count() == 2
    assert projeto.plano_ativo.versao == 2
    # A restrição do banco garante um ativo só; o teste garante que o serviço
    # desativa o anterior antes de criar o novo.
    assert Plano.objects.filter(projeto=projeto, ativo=True).count() == 1


def test_progresso_conta_so_o_plano_ativo(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    passo = Passo.objects.filter(etapa__plano=projeto.plano_ativo).first()
    passo.status = Passo.Status.CONCLUIDO
    passo.save()

    feitos, total, pct = projeto.progresso()
    assert (feitos, total, pct) == (1, 3, 33)


def test_projeto_de_outro_usuario_devolve_404(client, projeto, outro):
    """404 e não 403: quem não pode ver também não deveria descobrir que
    existe."""
    client.force_login(outro)
    assert client.get(f"/projetos/{projeto.pk}/").status_code == 404


def test_passo_de_outro_usuario_devolve_404(client, projeto, outro):
    salvar_plano(projeto, _gerado(), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(outro)
    assert client.get(f"/projetos/passo/{passo.pk}/").status_code == 404


def test_concluir_manualmente_libera_o_proximo(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro, segundo, _ = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    client.force_login(aluno)
    resposta = client.post(f"/projetos/passo/{primeiro.pk}/concluir/")

    primeiro.refresh_from_db()
    segundo.refresh_from_db()
    assert primeiro.status == Passo.Status.CONCLUIDO
    # Fica registrado que não passou por revisão. O dado some se não for salvo.
    assert primeiro.concluido_manualmente is True
    assert segundo.status == Passo.Status.DISPONIVEL
    assert resposta.status_code == 302


def test_criar_projeto_leva_para_o_planejamento(client, aluno):
    client.force_login(aluno)
    resposta = client.post(
        "/projetos/novo/",
        {
            "titulo": "API de receitas",
            "objetivo": "Uma API para guardar receitas.",
            "nivel": "iniciante",
            "horas_por_semana": 5,
            "preferencia_didatica": "socratico",
        },
    )
    projeto = Projeto.objects.get(titulo="API de receitas")
    assert projeto.usuario == aluno
    assert resposta["Location"] == f"/projetos/{projeto.pk}/planejar/"


def test_passo_conhece_o_lugar_dele_na_fila(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro, segundo, terceiro = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    assert (primeiro.posicao, primeiro.total_no_plano) == (1, 3)
    assert primeiro.anterior is None
    assert primeiro.proximo.pk == segundo.pk
    assert segundo.anterior.pk == primeiro.pk
    assert terceiro.proximo is None


def test_tela_do_passo_oferece_o_seguinte(client, aluno, projeto):
    """Num app que é uma fila, não ter o 'próximo' à mão obriga a voltar ao
    plano e procurar a linha certa a cada passo."""
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/passo/{primeiro.pk}/").content
    assert b"Pr\xc3\xb3ximo" in conteudo
    assert f'href="/projetos/passo/{primeiro.proximo.pk}/"'.encode() in conteudo


def test_tela_do_projeto_destaca_o_passo_da_vez(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/{projeto.pk}/").content
    # A ação central da tela precisa ser um botão, não uma linha de lista.
    assert b"Come\xc3\xa7ar" in conteudo
    assert f'href="/projetos/passo/{primeiro.pk}/"'.encode() in conteudo


def test_passo_na_fila_pode_ser_lido_com_aviso(client, aluno, projeto):
    """Ler adiante é legítimo, o que a fila ordena é a prática, não a leitura."""
    salvar_plano(projeto, _gerado(), "fake")
    bloqueado = Passo.objects.filter(etapa__plano__projeto=projeto)[1]
    assert bloqueado.status == Passo.Status.BLOQUEADO

    client.force_login(aluno)
    resposta = client.get(f"/projetos/passo/{bloqueado.pk}/")
    assert resposta.status_code == 200
    assert b"ainda est\xc3\xa1 na fila" in resposta.content


def test_plano_concluido_fecha_a_tela_do_projeto(client, aluno, projeto):
    salvar_plano(projeto, _gerado(1), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    passo.status = Passo.Status.CONCLUIDO
    passo.save()

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/{projeto.pk}/").content
    assert b"Plano conclu\xc3\xaddo" in conteudo
    # E não sobra um "Começar" apontando para lugar nenhum.
    assert b"Come\xc3\xa7ar \xe2\x80\x94 passo" not in conteudo


def test_editar_projeto_corrige_o_objetivo(client, aluno, projeto):
    """Objetivo mal escrito é a causa mais comum de plano ruim, e antes ficava
    congelado para sempre."""
    client.force_login(aluno)
    resposta = client.post(
        f"/projetos/{projeto.pk}/editar/",
        {
            "titulo": "Lista de tarefas",
            "objetivo": "Agora com o objetivo escrito direito.",
            "nivel": "iniciante",
            "horas_por_semana": 5,
            "preferencia_didatica": "socratico",
        },
    )
    projeto.refresh_from_db()
    assert resposta.status_code == 302
    assert projeto.objetivo == "Agora com o objetivo escrito direito."


def test_arquivar_tira_do_painel_e_desarquivar_traz_de_volta(client, aluno, projeto):
    client.force_login(aluno)

    client.post(f"/projetos/{projeto.pk}/arquivar/")
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.ARQUIVADO
    assert projeto.titulo.encode() not in client.get("/").content
    # Mas continua inteiro, na aba de arquivados.
    assert projeto.titulo.encode() in client.get("/?arquivados=1").content

    client.post(f"/projetos/{projeto.pk}/arquivar/")
    projeto.refresh_from_db()
    assert projeto.status != Projeto.Status.ARQUIVADO


def test_excluir_exige_o_titulo_digitado(client, aluno, projeto):
    client.force_login(aluno)

    client.post(f"/projetos/{projeto.pk}/excluir/", {"confirmacao": "errado"})
    assert Projeto.objects.filter(pk=projeto.pk).exists()

    client.post(f"/projetos/{projeto.pk}/excluir/", {"confirmacao": projeto.titulo})
    assert not Projeto.objects.filter(pk=projeto.pk).exists()


def test_projeto_de_outro_nao_pode_ser_editado_nem_excluido(client, projeto, outro):
    client.force_login(outro)
    assert client.get(f"/projetos/{projeto.pk}/editar/").status_code == 404
    assert client.post(f"/projetos/{projeto.pk}/arquivar/").status_code == 404
    assert client.post(f"/projetos/{projeto.pk}/excluir/", {"confirmacao": projeto.titulo}).status_code == 404
    assert Projeto.objects.filter(pk=projeto.pk).exists()


def test_ultimo_passo_concluido_fecha_o_projeto(client, aluno, projeto):
    """Quatro caminhos concluem um passo; o status do projeto não pode depender
    de qual deles foi usado."""
    salvar_plano(projeto, _gerado(2), "fake")
    primeiro, segundo = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    client.force_login(aluno)
    client.post(f"/projetos/passo/{primeiro.pk}/concluir/")
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.EM_ANDAMENTO

    client.post(f"/projetos/passo/{segundo.pk}/concluir/")
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.CONCLUIDO


def test_editar_passo_ajusta_texto_e_criterios(client, aluno, projeto):
    """O plano sai de um modelo de linguagem, e modelo erra. Antes a única
    saída para um passo ruim era refazer o plano inteiro."""
    salvar_plano(projeto, _gerado(), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(aluno)
    resposta = client.post(
        f"/projetos/passo/{passo.pk}/editar/",
        {
            "titulo": "Subir o esqueleto",
            "o_que_fazer": "faça isto",
            "como_fazer": "assim",
            "teoria": "porque sim",
            "criterios_aceite": "responde 200\n\ntem teste\n",
            "armadilhas": "esquecer a migration",
            "estimativa_min": 40,
        },
    )
    passo.refresh_from_db()
    assert resposta.status_code == 302
    assert passo.titulo == "Subir o esqueleto"
    # Linhas viram lista; linha em branco não vira critério vazio.
    assert passo.criterios_aceite == ["responde 200", "tem teste"]
    assert passo.armadilhas == ["esquecer a migration"]


def test_mover_passo_troca_com_o_vizinho(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro, segundo, _ = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    client.force_login(aluno)
    client.post(f"/projetos/passo/{segundo.pk}/mover/", {"direcao": "cima"})

    titulos = list(
        Passo.objects.filter(etapa__plano__projeto=projeto).values_list("titulo", flat=True)
    )
    assert titulos[:2] == [segundo.titulo, primeiro.titulo]


def test_mover_no_topo_nao_faz_nada(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(aluno)
    client.post(f"/projetos/passo/{primeiro.pk}/mover/", {"direcao": "cima"})

    assert Passo.objects.filter(etapa__plano__projeto=projeto).first().pk == primeiro.pk


def test_remover_passo_recompoe_a_numeracao(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    _, segundo, terceiro = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    client.force_login(aluno)
    client.post(f"/projetos/passo/{segundo.pk}/remover/")

    ordens = list(
        Passo.objects.filter(etapa__plano__projeto=projeto).values_list("ordem", flat=True)
    )
    # Sem buraco: removeu o 2 e o 3 virou 2.
    assert ordens == [1, 2]


def test_remover_o_passo_em_curso_abre_o_seguinte(client, aluno, projeto):
    """Sem isto, a fila fica sem passo aberto e o botão principal do projeto
    some da tela."""
    salvar_plano(projeto, _gerado(), "fake")
    primeiro, segundo, _ = list(Passo.objects.filter(etapa__plano__projeto=projeto))
    assert primeiro.status == Passo.Status.DISPONIVEL

    client.force_login(aluno)
    client.post(f"/projetos/passo/{primeiro.pk}/remover/")

    segundo.refresh_from_db()
    assert segundo.status == Passo.Status.DISPONIVEL


def test_adicionar_passo_entra_no_fim_da_etapa(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    etapa = projeto.plano_ativo.etapas.first()

    client.force_login(aluno)
    client.post(
        f"/projetos/etapa/{etapa.pk}/passo/novo/",
        {
            "titulo": "Passo que faltava",
            "o_que_fazer": "x",
            "como_fazer": "y",
            "teoria": "z",
            "criterios_aceite": "roda",
            "armadilhas": "",
            "estimativa_min": "",
        },
    )
    ultimo = Passo.objects.filter(etapa=etapa).last()
    assert ultimo.titulo == "Passo que faltava"
    assert ultimo.ordem == 4


def test_plano_de_outro_usuario_nao_e_editavel(client, projeto, outro):
    salvar_plano(projeto, _gerado(), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(outro)
    assert client.get(f"/projetos/{projeto.pk}/plano/editar/").status_code == 404
    assert client.get(f"/projetos/passo/{passo.pk}/editar/").status_code == 404
    assert client.post(f"/projetos/passo/{passo.pk}/remover/").status_code == 404
    assert Passo.objects.filter(pk=passo.pk).exists()


def test_briefing_chega_como_perguntas_do_mentor(client, aluno, projeto):
    """As perguntas eram um campo de texto livre; agora quem pergunta é o
    mentor, e cada pergunta explica o que ela muda no plano."""
    import json

    from asgiref.sync import async_to_sync

    client.force_login(aluno)
    resposta = client.get(f"/projetos/{projeto.pk}/planejar/briefing/")

    conteudo = resposta.streaming_content
    if hasattr(conteudo, "__aiter__"):

        async def drenar():
            return b"".join([bloco async for bloco in conteudo])

        bruto = async_to_sync(drenar)().decode()
    else:
        bruto = b"".join(conteudo).decode()

    dados = json.loads(bruto.split("data: ")[1])
    assert 3 <= len(dados["perguntas"]) <= 5
    assert dados["perguntas"][0]["porque"]


def test_versao_antiga_do_plano_e_visivel_e_somente_leitura(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    salvar_plano(projeto, _gerado(2), "fake")

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/{projeto.pk}/plano/v1/").content
    assert b"Plano v1" in conteudo
    # Não oferece edição: versão antiga é registro, não rascunho.
    assert b"Editar" not in conteudo


def test_historico_de_revisoes_pagina(client, aluno, projeto):
    from revisoes.models import Submissao

    salvar_plano(projeto, _gerado(1), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    for i in range(12):
        Submissao.objects.create(passo=passo, usuario=aluno, conteudo=f"tentativa {i}")

    client.force_login(aluno)
    primeira = client.get(f"/projetos/passo/{passo.pk}/revisoes/")
    assert primeira.context["pagina"].paginator.num_pages == 2
    assert len(primeira.context["pagina"].object_list) == 10

    segunda = client.get(f"/projetos/passo/{passo.pk}/revisoes/?p=2")
    assert len(segunda.context["pagina"].object_list) == 2
