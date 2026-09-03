"""Renderização do que o mentor escreve.

Duas coisas acontecem aqui, nesta ordem, e a ordem importa:

1. o markdown vira HTML e passa pelo nh3. O texto vem de um modelo de
   linguagem, então tratá-lo como confiável seria XSS com passos extras;
2. bloco de código longo demais é dobrado. O mentor não deve escrever a
   implementação do aluno; quando escapa, quem decide ver é o aluno.
"""

import re

import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Acima disto, o bloco deixa de ser ilustração e vira solução pronta.
LIMITE_LINHAS = 6

TAGS_PERMITIDAS = {
    "p",
    "br",
    "strong",
    "em",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "details",
    "summary",
    "span",
}
ATRIBUTOS_PERMITIDOS = {"a": {"href", "title"}, "details": {"class"}, "summary": {"class"}}


def _dobrar_blocos_longos(texto):
    """Troca o bloco cercado longo por um <details> fechado.

    Feito no markdown, antes da conversão: mexer no HTML depois exigiria
    parsear de novo o que o nh3 já validou.
    """

    def trocar(casamento):
        cerca, linguagem, corpo = casamento.group(1), casamento.group(2), casamento.group(3)
        linhas = corpo.strip("\n").count("\n") + 1
        if linhas <= LIMITE_LINHAS:
            return casamento.group(0)
        return (
            f'<details class="codigo-guardado">'
            f"<summary>o mentor escreveu {linhas} linhas de código. Mostrar mesmo assim?</summary>\n\n"
            f"{cerca}{linguagem}\n{corpo}{cerca}\n\n"
            f"</details>"
        )

    return re.sub(r"(`{3,})(\w*)\n(.*?)\1", trocar, texto, flags=re.DOTALL)


@register.filter
def prosa(texto):
    if not texto:
        return ""
    html = md.markdown(
        _dobrar_blocos_longos(texto),
        extensions=["fenced_code", "tables", "sane_lists", "md_in_html"],
    )
    return mark_safe(nh3.clean(html, tags=TAGS_PERMITIDAS, attributes=ATRIBUTOS_PERMITIDOS))


@register.filter
def prosa_curta(texto):
    """O mesmo tratamento, para um trecho de uma linha só.

    Critério de aceite e armadilha vêm do mentor com a mesma marcação do resto
    (`crase` para nome de arquivo e comando), mas eram impressos crus, e a
    crase aparecia na tela como sujeira. Aqui o markdown é aplicado e o
    parágrafo que o conversor envolve em volta é removido, porque o texto já
    está dentro de um `<li>`.
    """
    if not texto:
        return ""
    html = str(prosa(texto)).strip()
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return mark_safe(html)
