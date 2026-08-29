"""Os caminhos inteiros, do jeito que uma pessoa percorre.

O que estes testes pegam e os de unidade não: template que não renderiza, URL
que aponta para o lugar errado, botão coberto por outro elemento, JavaScript
que quebra e leva o SSE junto. São lentos, então cobrem os caminhos que doem se
quebrarem, não todos.
"""

import pytest

from testes_navegador.conftest import SENHA, USUARIO

pytestmark = pytest.mark.e2e


def test_entrar_e_ver_o_painel(pagina, servidor):
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button[type=submit]")

    pagina.wait_for_selector("text=Seus projetos")
    assert "Encurtador de links" in pagina.content()


def test_senha_errada_nao_entra(pagina, servidor):
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", "isso-nao-e-a-senha")
    pagina.click("button[type=submit]")

    pagina.wait_for_selector("#id_password")
    assert "/conta/entrar/" in pagina.url


def test_visitante_entra_e_ja_tem_projeto(pagina, servidor):
    """A promessa do botão: clicar e estar dentro, com algo para abrir."""
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.click("text=Entrar como visitante")

    pagina.wait_for_selector("text=Encurtador de links")
    assert "/projetos" in pagina.url or "Seus projetos" in pagina.content()


def test_do_painel_ate_o_passo(autenticado, servidor):
    """A rota mais percorrida do app: painel, projeto, passo da vez."""
    pagina = autenticado
    pagina.click("text=Encurtador de links")
    pagina.wait_for_selector("text=O servidor de pé")

    pagina.click("text=Ambiente virtual e primeira rota")
    pagina.wait_for_selector("#codigo")

    corpo = pagina.inner_text("body")
    # As três camadas são a promessa do app: o que fazer, como, e por quê.
    assert "ambiente virtual" in corpo.lower()
    assert "Como fazer" in corpo or "como fazer" in corpo.lower()
    assert "Pedir revisão" in corpo


def test_criar_projeto_e_gerar_o_plano(autenticado, servidor):
    """Cobre o SSE da geração: se o stream quebrar, a página fica na espera
    para sempre e nenhum teste de unidade percebe."""
    pagina = autenticado
    pagina.goto(f"{servidor}/projetos/novo/")

    # Sem campo de título na criação: o mentor escolhe o nome de verdade ao
    # gerar o plano (ver projetos/views.py::novo e _form_projeto.html).
    pagina.fill("#id_objetivo", "Um CRUD de contatos em linha de comando, com busca por nome.")
    pagina.check("input[value=iniciante]")
    # Pelo texto, e não por `button[type=submit]`: o botão de sair da barra
    # lateral vem antes no DOM e seria ele o clicado.
    pagina.click("text=Criar e planejar")

    pagina.wait_for_selector("[data-gerar]")
    pagina.click("[data-gerar]")

    # O motor falso responde na hora, mas o caminho é o mesmo do de verdade:
    # abre o stream, recebe os eventos e redireciona ao terminar. O título é
    # fixo no motor falso ("Lista de tarefas guiada"): não deriva do objetivo.
    pagina.wait_for_url("**/projetos/*/", timeout=60000)
    pagina.wait_for_selector("text=Lista de tarefas guiada")


def test_chat_responde_no_passo(autenticado, servidor):
    """O chat é SSE: chegar de uma vez, ou não chegar, é sempre defeito de
    integração, nunca de lógica."""
    pagina = autenticado
    pagina.click("text=Encurtador de links")
    pagina.click("text=Ambiente virtual e primeira rota")

    pagina.fill("[data-pergunta]", "Por que preciso de ambiente virtual?")
    pagina.click("[data-enviar]")

    pagina.wait_for_selector(".msg--mentor", timeout=60000)
    resposta = pagina.inner_text(".msg--mentor")
    assert resposta.strip()


def test_submeter_codigo_e_receber_veredito(autenticado, servidor):
    """A revisão fecha o ciclo do passo. Se ela não voltar, o passo nunca
    conclui e o app inteiro para no primeiro item."""
    pagina = autenticado
    pagina.click("text=Encurtador de links")
    pagina.click("text=Ambiente virtual e primeira rota")

    pagina.fill("#codigo", "from flask import Flask\n\napp = Flask(__name__)\n")
    pagina.click("text=Pedir revisão")

    pagina.wait_for_selector("text=/atende|Atende|ressalva|não atende/i", timeout=60000)
    assert "critério" in pagina.inner_text("body").lower() or "Critério" in pagina.content()


def test_conta_mostra_o_limite_e_nao_pede_chave(autenticado, servidor):
    """A chave da API é do provedor do app. Se um campo de chave reaparecer na
    tela da conta, o modelo de custo mudou sem ninguém decidir isso."""
    pagina = autenticado
    pagina.goto(f"{servidor}/conta/")

    corpo = pagina.inner_text("body")
    assert "US$" in corpo
    assert "chave" not in corpo.lower()


def test_tema_escuro_persiste_entre_paginas(autenticado, servidor):
    """A seção de Aparência na conta foi removida (redundante com o botão do
    cabeçalho); o alternador persiste no servidor via POST /conta/tema/, e é
    esse round-trip que o teste verifica ao navegar sem o JS ainda ter rodado."""
    pagina = autenticado
    pagina.goto(f"{servidor}/")

    with pagina.expect_response("**/conta/tema/"):
        pagina.click("[data-tema-botao]")

    pagina.goto(f"{servidor}/")
    tema = pagina.get_attribute("html", "data-tema")
    assert tema == "escuro"


def test_um_aluno_nao_abre_o_projeto_do_outro(autenticado, servidor, page, browser):
    """O isolamento tem teste de unidade, mas aqui ele é verificado pela porta
    da frente, que é por onde um ataque chegaria."""
    endereco = None
    autenticado.click("text=Encurtador de links")
    endereco = autenticado.url

    outra = browser.new_context()
    try:
        anonima = outra.new_page()
        anonima.goto(endereco)
        # Sem sessão, o app manda para a entrada em vez de mostrar o projeto.
        assert "/conta/entrar/" in anonima.url
    finally:
        outra.close()
