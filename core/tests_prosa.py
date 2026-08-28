from core.templatetags.prosa import prosa


def test_markdown_vira_html():
    assert "<strong>o quê</strong>" in prosa("**o quê**")


def test_script_no_texto_do_modelo_nao_passa():
    """O texto vem de um modelo de linguagem: tratá-lo como confiável seria XSS
    com passos extras."""
    saida = prosa("antes <script>alert(1)</script> depois")
    assert "<script>" not in saida
    assert "alert(1)" not in saida


def test_bloco_curto_continua_visivel():
    curto = "```python\nreturn x + 1\n```"
    saida = prosa(curto)
    assert "codigo-guardado" not in saida
    assert "<pre>" in saida


def test_bloco_longo_fica_dobrado():
    """A guarda anti-spoiler: se o mentor escreveu a implementação, ela não
    aparece pronta na tela. O aluno decide se quer ver."""
    corpo = "\n".join(f"linha_{i} = {i}" for i in range(12))
    saida = prosa(f"```python\n{corpo}\n```")
    assert "codigo-guardado" in saida
    assert "Mostrar mesmo assim" in saida
    # O código continua lá dentro; o que muda é estar fechado.
    assert "linha_11" in saida


def test_prosa_curta_marca_codigo_sem_envolver_em_paragrafo():
    """Critério e armadilha vêm do mentor com crase, e eram impressos crus: a
    crase aparecia na tela como sujeira no meio da palavra."""
    from core.templatetags.prosa import prosa_curta

    saida = str(prosa_curta("A pasta `.venv` está no `.gitignore`."))
    assert "<code>.venv</code>" in saida
    assert "`" not in saida
    assert not saida.startswith("<p>")


def test_prosa_curta_sanitiza_como_a_prosa_inteira():
    from core.templatetags.prosa import prosa_curta

    saida = str(prosa_curta("olhe <script>alert(1)</script> aqui"))
    assert "<script>" not in saida


def test_prosa_curta_aguenta_texto_de_varios_paragrafos():
    """Se o mentor mandar duas frases separadas, o parágrafo tem de ficar: só
    o caso de um parágrafo só é desembrulhado."""
    from core.templatetags.prosa import prosa_curta

    saida = str(prosa_curta("Primeira.\n\nSegunda."))
    assert saida.count("<p>") == 2
