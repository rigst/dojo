"""As telas, pixel a pixel, contra as referências versionadas.

Não roda no `pytest` pelado nem na integração contínua: a renderização de texto
depende das fontes instaladas na máquina, e uma referência gravada aqui não
bate com a de outro sistema. É uma rede para quem mexe no CSS, rodada de
propósito antes de commitar o CSS.

    pytest -m visual                     compara
    pytest -m visual --atualizar-telas   regrava as referências
"""

import pytest

from testes_navegador.conftest import definir_tema

pytestmark = pytest.mark.visual

# O relógio e o dinheiro são o que muda sozinho entre duas execuções. Ficam
# cobertos, e não fora da captura: o espaço que ocupam também é layout.
MASCARA_DATA = ".ds-muted:has-text('há')"


@pytest.fixture(autouse=True)
def tema_claro(request, servidor):
    """Toda captura parte do tema claro.

    Quem quer o escuro pede por ele; assim nenhuma referência depende de qual
    teste rodou antes.
    """
    if "autenticado" in request.fixturenames:
        definir_tema(request.getfixturevalue("autenticado"), servidor, "claro")


def test_tela_de_entrada(pagina, servidor, comparar_tela):
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.wait_for_selector("#id_username")
    comparar_tela(pagina, "entrada")


def test_tela_de_entrada_no_celular(pagina, servidor, comparar_tela):
    """A largura em que a barra lateral vira menu. É onde as regras de cascata
    do CSS costumam se atropelar."""
    pagina.set_viewport_size({"width": 390, "height": 844})
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.wait_for_selector("#id_username")
    comparar_tela(pagina, "entrada-celular")


def test_painel(autenticado, servidor, comparar_tela):
    autenticado.goto(f"{servidor}/")
    autenticado.wait_for_selector("text=Seus projetos")
    comparar_tela(autenticado, "painel", mascarar=[MASCARA_DATA])


def test_painel_no_celular(autenticado, servidor, comparar_tela):
    autenticado.set_viewport_size({"width": 390, "height": 844})
    autenticado.goto(f"{servidor}/")
    autenticado.wait_for_selector("text=Seus projetos")
    comparar_tela(autenticado, "painel-celular", mascarar=[MASCARA_DATA])


def test_projeto(autenticado, servidor, comparar_tela):
    autenticado.goto(f"{servidor}/")
    autenticado.click("text=Encurtador de links")
    autenticado.wait_for_selector("text=O servidor de pé")
    comparar_tela(autenticado, "projeto", mascarar=[MASCARA_DATA])


def test_passo(autenticado, servidor, comparar_tela):
    """A tela mais densa do app, e a que mais se mexe."""
    autenticado.goto(f"{servidor}/")
    autenticado.click("text=Encurtador de links")
    autenticado.click("text=Ambiente virtual e primeira rota")
    autenticado.wait_for_selector("#codigo")
    comparar_tela(autenticado, "passo", mascarar=[MASCARA_DATA])


def test_passo_no_escuro(autenticado, servidor, comparar_tela):
    """O tema escuro tem seu próprio jogo de tokens, e nada além de olhar
    garante que uma cor nova foi definida nos dois."""
    definir_tema(autenticado, servidor, "escuro")

    autenticado.goto(f"{servidor}/")
    autenticado.click("text=Encurtador de links")
    autenticado.click("text=Ambiente virtual e primeira rota")
    autenticado.wait_for_selector("#codigo")
    comparar_tela(autenticado, "passo-escuro", mascarar=[MASCARA_DATA])


def test_chat(autenticado, servidor, comparar_tela):
    # A tela dedicada, e nao o chat ao lado do passo: o compositor muda de
    # largura e a dica de teclado so aparece aqui, entao e outra tela.
    autenticado.goto(f"{servidor}/")
    autenticado.click("text=Encurtador de links")
    autenticado.click("text=Conversar")
    autenticado.wait_for_selector(".chat--inteiro .chat-caixa")
    comparar_tela(autenticado, "chat", mascarar=[MASCARA_DATA])


def test_conta(autenticado, servidor, comparar_tela):
    autenticado.goto(f"{servidor}/conta/")
    autenticado.wait_for_selector("text=Aparência")
    comparar_tela(autenticado, "conta", mascarar=[".num", MASCARA_DATA])
