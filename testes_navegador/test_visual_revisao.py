"""A tela de revisão, num banco só dela.

Módulo à parte de propósito: pedir uma revisão muda o estado do passo, e o
fixture do servidor é por módulo. Junto das outras capturas, a ordem em que os
testes rodassem passaria a decidir o que aparece na tela do passo.
"""

import pytest

pytestmark = pytest.mark.visual


def test_revisao_com_problemas(autenticado, servidor, comparar_tela):
    """O caminho que mais tem o que mostrar: veredito negativo, critério a
    critério e o problema com a razão por trás."""
    pagina = autenticado
    pagina.click("text=Encurtador de links")
    pagina.click("text=Ambiente virtual e primeira rota")

    # O motor falso reprova o que tem `pass` solto, que é o caminho com
    # critérios reprovados e problema listado.
    pagina.fill("#codigo", "def criar_app():\n    pass\n")
    pagina.click("text=Pedir revisão")

    pagina.wait_for_selector("text=Você terminou quando", state="detached", timeout=60000)
    pagina.wait_for_selector(".criterios--avaliados", timeout=60000)
    comparar_tela(pagina, "revisao", mascarar=[".ds-muted:has-text('há')"])
