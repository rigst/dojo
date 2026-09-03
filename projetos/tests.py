import pytest
from django.contrib.auth import get_user_model

from ia.schemas import EtapaGerada, PassoGerado, PlanoGerado
from projetos.models import Etapa, Passo, Plano, Projeto, Stack
from projetos.servicos import salvar_plano


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


@pytest.fixture
def outro(db):
    return get_user_model().objects.create_user("outro", password="senha-de-teste-123")


@pytest.fixture
def projeto(aluno):
    p = Projeto.objects.create(
        usuario=aluno, titulo="Lista de tarefas", objetivo="Um app de tarefas."
    )
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
                        o_que_enviar="o trecho",
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

    status = list(
        Passo.objects.filter(etapa__plano__projeto=projeto).values_list("status", flat=True)
    )
    assert status == [Passo.Status.DISPONIVEL, Passo.Status.BLOQUEADO, Passo.Status.BLOQUEADO]


def test_replanejar_versiona_em_vez_de_sobrescrever(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    salvar_plano(projeto, _gerado(2), "fake")

    assert projeto.planos.count() == 2
    assert projeto.plano_ativo.versao == 2
    # A restrição do banco garante um ativo só; o teste garante que o serviço
    # desativa o anterior antes de criar o novo.
    assert Plano.objects.filter(projeto=projeto, ativo=True).count() == 1


def test_progresso_conta_etapas_concluidas_e_nao_passos_soltos(projeto):
    """Por etapa, e não por passo: os passos de uma etapa nascem aos poucos, à
    medida que o aluno avança (geração incremental), e contar por passo faria
    o percentual cair sempre que um passo novo aparecesse. As etapas, ao
    contrário, são todas conhecidas desde o primeiro plano."""
    plano = Plano.objects.create(projeto=projeto, versao=1, resumo="r", ativo=True)
    etapa1 = Etapa.objects.create(plano=plano, ordem=1, titulo="Etapa 1", passos_prontos=True)
    etapa2 = Etapa.objects.create(plano=plano, ordem=2, titulo="Etapa 2", passos_prontos=True)
    Passo.objects.create(etapa=etapa1, ordem=1, titulo="p1", status=Passo.Status.CONCLUIDO)
    Passo.objects.create(etapa=etapa2, ordem=1, titulo="p2", status=Passo.Status.DISPONIVEL)

    # Uma etapa concluída de duas: 50%, mesmo que a segunda ainda ganhe mais
    # passos depois.
    feitos, total, pct = projeto.progresso()
    assert (feitos, total, pct) == (1, 2, 50)

    Passo.objects.create(etapa=etapa1, ordem=2, titulo="p1b", status=Passo.Status.DISPONIVEL)
    # A etapa 1 ganhou um passo novo, ainda não feito: ela deixa de contar
    # como concluída até esse também terminar.
    feitos, total, pct = projeto.progresso()
    assert (feitos, total, pct) == (0, 2, 0)


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
    """A criação não pede título (ver _form_projeto.html): só o objetivo. O
    mentor é quem batiza o projeto, ao gerar o plano."""
    client.force_login(aluno)
    resposta = client.post(
        "/projetos/novo/",
        {
            "objetivo": "Uma API para guardar receitas.",
            "nivel": "iniciante",
            "horas_por_semana": 5,
            "preferencia_didatica": "socratico",
        },
    )
    projeto = Projeto.objects.get(objetivo="Uma API para guardar receitas.")
    assert projeto.usuario == aluno
    # Nasce com um nome provisório até o plano existir.
    assert projeto.titulo == "Novo projeto"
    assert resposta["Location"] == f"/projetos/{projeto.pk}/planejar/"


def test_passo_conhece_o_lugar_dele_na_fila(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro, segundo, terceiro = list(Passo.objects.filter(etapa__plano__projeto=projeto))

    assert (primeiro.posicao, primeiro.total_no_plano) == (1, 3)
    assert primeiro.anterior is None
    assert primeiro.proximo.pk == segundo.pk
    assert segundo.anterior.pk == primeiro.pk
    assert terceiro.proximo is None


def test_tela_do_passo_oferece_o_seguinte_quando_ja_aberto(client, aluno, projeto):
    """Num app que é uma fila, não ter o 'próximo' à mão obriga a voltar ao
    plano e procurar a linha certa a cada passo — mas só quando ele já abriu."""
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    segundo = primeiro.proximo
    segundo.status = Passo.Status.DISPONIVEL
    segundo.save(update_fields=["status"])

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/passo/{primeiro.pk}/").content
    assert b"Pr\xc3\xb3ximo" in conteudo
    assert f'href="/projetos/passo/{segundo.pk}/"'.encode() in conteudo


def test_tela_do_passo_nao_linka_o_seguinte_bloqueado(client, aluno, projeto):
    """O próximo passo ainda bloqueado aparece só como aviso, sem link: ele
    continua inacessível até este passar na revisão."""
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    assert primeiro.proximo.status == Passo.Status.BLOQUEADO

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/passo/{primeiro.pk}/").content
    assert f'href="/projetos/passo/{primeiro.proximo.pk}/"'.encode() not in conteudo
    assert b"abre quando este passar na revis\xc3\xa3o" in conteudo


def test_tela_do_projeto_destaca_o_passo_da_vez(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    primeiro = Passo.objects.filter(etapa__plano__projeto=projeto).first()

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/{projeto.pk}/").content
    # A ação central da tela precisa ser um botão, não uma linha de lista.
    assert b"Come\xc3\xa7ar" in conteudo
    assert f'href="/projetos/passo/{primeiro.pk}/"'.encode() in conteudo


def test_passo_bloqueado_e_inacessivel(client, aluno, projeto):
    """Bloqueado é inacessível de verdade: a URL direta não mostra o conteúdo,
    só manda de volta para o passo anterior."""
    salvar_plano(projeto, _gerado(), "fake")
    passos = list(Passo.objects.filter(etapa__plano__projeto=projeto))
    bloqueado = passos[1]
    assert bloqueado.status == Passo.Status.BLOQUEADO

    client.force_login(aluno)
    resposta = client.get(f"/projetos/passo/{bloqueado.pk}/")
    assert resposta["Location"] == f"/projetos/passo/{passos[0].pk}/"


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
    assert (
        client.post(f"/projetos/{projeto.pk}/excluir/", {"confirmacao": projeto.titulo}).status_code
        == 404
    )
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
    _, segundo, _terceiro = list(Passo.objects.filter(etapa__plano__projeto=projeto))

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


# --- geração incremental do plano --------------------------------------------
#
# A geração cheia (todas as etapas com todos os passos numa resposta só)
# estourava o limite de tokens da resposta estruturada em planos grandes, e o
# JSON cortado no meio virava erro de validação. Agora a primeira chamada gera
# só o roteiro (títulos e objetivos das etapas) e o primeiro passo; os demais
# passos vêm um de cada vez, à medida que o aluno avança.


def test_plano_inicial_gera_esqueleto_e_so_o_primeiro_passo(aluno, projeto):
    from asgiref.sync import async_to_sync

    from projetos.servicos import gerar_e_salvar_plano

    plano, _uso = async_to_sync(gerar_e_salvar_plano)(projeto, aluno, "")

    etapas = list(plano.etapas.order_by("ordem").prefetch_related("passos"))
    assert len(etapas) >= 2

    primeira = etapas[0]
    assert primeira.passos.count() == 1
    assert primeira.passos.first().status == Passo.Status.DISPONIVEL
    # A primeira etapa pode precisar de mais passos além do primeiro: só o
    # mentor decide isso na geração seguinte, não a chamada inicial.
    assert primeira.passos_prontos is False

    for etapa in etapas[1:]:
        assert etapa.passos.count() == 0
        assert etapa.passos_prontos is False

    projeto.refresh_from_db()
    assert projeto.gerando is False
    assert projeto.erro_geracao == ""
    assert projeto.briefing_pendente == ""
    # O mentor escolhe título e subtítulo ao gerar o plano; o subtítulo não
    # existia antes disso (a criação não pede um).
    assert projeto.titulo
    assert projeto.subtitulo


def test_f5_no_meio_da_geracao_nao_mostra_perguntas_de_novo(client, aluno, projeto):
    """Um recarregamento no meio da geração tem de cair na tela de espera, não
    de volta nas perguntas do briefing (já respondidas da primeira vez)."""
    from projetos.servicos import _iniciar_geracao

    _iniciar_geracao(projeto.pk, "respostas do briefing de antes")

    client.force_login(aluno)
    conteudo = client.get(f"/projetos/{projeto.pk}/planejar/").content
    assert b'data-gerando="1"' in conteudo
    assert b"data-briefing-perguntas" not in conteudo


def test_gerar_proximo_passo_fecha_a_etapa_quando_o_mentor_diz_que_acabou(aluno, projeto):
    from asgiref.sync import async_to_sync

    from projetos.servicos import gerar_e_salvar_plano, gerar_e_salvar_proximo_passo

    plano, _ = async_to_sync(gerar_e_salvar_plano)(projeto, aluno, "")
    primeira_etapa = plano.etapas.order_by("ordem").first()

    passo, _ = async_to_sync(gerar_e_salvar_proximo_passo)(projeto, aluno)

    primeira_etapa.refresh_from_db()
    assert passo.etapa_id == primeira_etapa.pk
    assert passo.ordem == 2
    # O dublê sempre fecha a etapa no passo seguinte (ver fake_motor).
    assert primeira_etapa.passos_prontos is True

    projeto.refresh_from_db()
    assert projeto.gerando is False


def test_concluir_passo_sem_fila_pronta_manda_preparar_o_proximo(client, aluno, projeto):
    """Sem passo já materializado esperando na fila, e com etapa ainda em
    aberto, a tela certa é a de espera, não o projeto sem ação nenhuma."""
    from asgiref.sync import async_to_sync

    from projetos.servicos import gerar_e_salvar_plano

    plano, _ = async_to_sync(gerar_e_salvar_plano)(projeto, aluno, "")
    passo = plano.etapas.first().passos.first()

    client.force_login(aluno)
    resposta = client.post(f"/projetos/passo/{passo.pk}/concluir/")

    assert resposta["Location"] == f"/projetos/{projeto.pk}/planejar/passo/"


# Os __str__ abaixo aparecem no admin e em qualquer log ou mensagem de erro que
# imprima o objeto. Sem teste, uma mudança de campo os quebra em silêncio e só
# se descobre lendo um traceback confuso.
def test_str_da_stack_e_o_nome(db):
    stack = Stack.objects.create(nome="Postgres", categoria=Stack.Categoria.BANCO)
    assert str(stack) == "Postgres"


def test_str_da_etapa_traz_ordem_e_titulo(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    etapa = Etapa.objects.filter(plano__projeto=projeto).first()
    assert str(etapa) == f"{etapa.ordem}. {etapa.titulo}"


def test_str_do_passo_traz_numero_e_titulo(projeto):
    salvar_plano(projeto, _gerado(), "fake")
    passo = Passo.objects.filter(etapa__plano__projeto=projeto).first()
    assert str(passo) == f"{passo.numero} {passo.titulo}"


def test_stacks_por_categoria_agrupa_e_nao_perde_opcao(projeto):
    """O agrupamento existe para a tela não virar 26 caixas em fila."""
    from projetos.forms import ProjetoForm

    Stack.objects.create(nome="Vue", categoria=Stack.Categoria.FRAMEWORK)
    form = ProjetoForm(instance=projeto)

    grupos = form.stacks_por_categoria()
    assert grupos, "esperava ao menos uma categoria com opções"
    # Nenhuma opção some no caminho: a soma dos grupos é o total do campo.
    total = sum(len(g["opcoes"]) for g in grupos)
    assert total == Stack.objects.count()


def test_semear_stacks_cria_e_nao_duplica(db):
    """O comando roda no deploy. Se duplicasse, a tela de escolha de stack
    encheria de repetidas; se não criasse, ninguém escolheria nada."""
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()
    call_command("semear_stacks", stdout=saida)
    total = Stack.objects.count()
    assert total > 0
    assert "no total" in saida.getvalue()

    # Segunda vez: idempotente, é o que o help do comando promete.
    call_command("semear_stacks", stdout=StringIO())
    assert Stack.objects.count() == total


def test_semear_stacks_respeita_os_slugs_manuais(db):
    """Alguns nomes gerariam slug ruim no automático (C#, C++)."""
    from io import StringIO

    from django.core.management import call_command

    from projetos.management.commands.semear_stacks import SLUGS_MANUAIS

    call_command("semear_stacks", stdout=StringIO())
    for nome, slug in SLUGS_MANUAIS.items():
        assert Stack.objects.get(nome=nome).slug == slug


# --- serviços: guardas e versionamento --------------------------------------


def test_etapa_pendente_e_passo_atual_aceitam_plano_inexistente(db):
    """Projeto recém-criado ainda não tem plano. As duas funções são chamadas
    pela tela antes disso existir, e sem a guarda o painel quebraria em vez de
    mostrar 'nada planejado ainda'."""
    from projetos.servicos import etapa_pendente, passo_atual

    assert etapa_pendente(None) is None
    assert passo_atual(None) is None


def test_salvar_plano_inicial_desativa_o_plano_anterior(projeto):
    """Replanejar versiona em vez de sobrescrever, e só um plano fica ativo —
    dois ativos fariam a tela do projeto escolher um deles por acaso."""
    from asgiref.sync import async_to_sync

    from ia.motores import fake_motor
    from projetos.models import Plano
    from projetos.servicos import salvar_plano_inicial

    class _Pedido:
        titulo_projeto = "Lista"
        objetivo = "Tarefas."

    gerado, _uso = async_to_sync(fake_motor.gerar_plano)(_Pedido())

    salvar_plano_inicial(projeto, gerado, "fake")
    salvar_plano_inicial(projeto, gerado, "fake")

    ativos = Plano.objects.filter(projeto=projeto, ativo=True)
    assert ativos.count() == 1
    assert ativos.first().versao == Plano.objects.filter(projeto=projeto).count()


# --- tela de espera e disparo do próximo passo ------------------------------


def test_passo_gerando_manda_para_o_projeto_quando_nao_ha_o_que_gerar(client, aluno, projeto):
    """Só se chega aqui por link direto ou F5 tardio. Renderizar a espera nesse
    caso deixaria a pessoa olhando um spinner que nunca termina."""
    salvar_plano(projeto, _gerado(), "fake")

    client.force_login(aluno)
    resposta = client.get(f"/projetos/{projeto.pk}/planejar/passo/")

    assert resposta.status_code == 302
    assert resposta.url == f"/projetos/{projeto.pk}/"


def test_passo_gerando_mostra_a_espera_enquanto_gera(client, aluno, projeto):
    salvar_plano(projeto, _gerado(), "fake")
    projeto.gerando = True
    projeto.save(update_fields=["gerando"])

    client.force_login(aluno)
    resposta = client.get(f"/projetos/{projeto.pk}/planejar/passo/")

    assert resposta.status_code == 200


def test_pre_gerar_so_aceita_post(client, aluno, projeto):
    client.force_login(aluno)
    assert client.get(f"/projetos/{projeto.pk}/planejar/passo/pre-gerar/").status_code == 405


def test_pre_gerar_nao_dispara_com_geracao_em_curso(client, aluno, projeto):
    """Duas abas abertas não podem virar duas gerações do mesmo passo."""
    salvar_plano(projeto, _gerado(), "fake")
    projeto.gerando = True
    projeto.save(update_fields=["gerando"])

    client.force_login(aluno)
    resposta = client.post(f"/projetos/{projeto.pk}/planejar/passo/pre-gerar/")
    assert resposta.status_code == 204


def test_pre_gerar_nao_dispara_com_passo_bloqueado_na_fila(client, aluno, projeto):
    """Já existe passo materializado esperando: gerar outro furaria a fila."""
    salvar_plano(projeto, _gerado(), "fake")

    client.force_login(aluno)
    resposta = client.post(f"/projetos/{projeto.pk}/planejar/passo/pre-gerar/")
    assert resposta.status_code == 204
    assert Passo.objects.filter(etapa__plano__projeto=projeto).count() == 3


def test_pre_gerar_de_projeto_alheio_nao_dispara(client, db, projeto):
    outro = get_user_model().objects.create_user("intruso", password="senha-de-teste-123")
    client.force_login(outro)
    assert client.post(f"/projetos/{projeto.pk}/planejar/passo/pre-gerar/").status_code == 404
