"""Monta o pedido antes de ele sair para o modelo.

Existe por um motivo concreto: o motor roda dentro de uma view assíncrona, e
qualquer acesso ao ORM lá dentro estoura com "you cannot call this from an
async context". Em vez de espalhar `sync_to_async` por dentro do motor, todo o
trabalho que depende do banco acontece aqui, de uma vez, do lado síncrono, e
o motor recebe texto pronto.

O efeito colateral é bom: o motor fica sem dependência de modelo nenhum, e o
dublê de testes não precisa de banco para responder.
"""

from dataclasses import dataclass, field

from django.conf import settings

from ia import contexto as ctx
from ia import prompts


@dataclass
class Pedido:
    """Tudo que a chamada precisa, sem nenhuma referência a objeto do Django."""

    sistema: list
    mensagens: list
    chave_api: str = ""
    # Usados só pelo dublê, para ele responder algo plausível sem consultar nada.
    criterios: list = field(default_factory=list)
    titulo_projeto: str = ""
    codigo: str = ""


def _chave(usuario):
    """A chave é uma só, do provedor do app.

    O parâmetro `usuario` continua na assinatura porque a cota é por pessoa e
    quem chama já tem o objeto em mãos; o que sumiu foi a chave por usuário.
    """
    return settings.ANTHROPIC_API_KEY


def _sistema(projeto, extra="", passo=None):
    """Blocos do system, do mais estável para o mais volátil.

    O primeiro bloco é o prompt congelado e leva um ponto de cache; o segundo é
    o contexto do projeto, que só muda quando o plano muda de versão. A pergunta
    do turno vem depois, em `messages`, para não invalidar nada disso.
    """
    partes = [ctx.do_projeto(projeto)]
    if passo is not None:
        partes.append(ctx.do_passo(passo))
    if extra:
        partes.append(extra)

    estilo = prompts.DIDATICA.get(projeto.preferencia_didatica, "")
    return [
        {"type": "text", "text": prompts.MENTOR, "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": "\n\n".join(filter(None, [estilo] + partes)),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def para_plano(projeto, usuario, respostas_briefing=""):
    pedido = (
        "Monte o plano deste projeto. O título que aparece em CONTEXTO DO PROJETO "
        "é só um rascunho (às vezes nem isso); escolha o título e o subtítulo de "
        "verdade a partir do objetivo."
    )
    if respostas_briefing:
        pedido += "\n\nO aluno respondeu ao briefing:\n" + respostas_briefing

    return Pedido(
        sistema=_sistema(projeto, extra=prompts.PLANEJADOR),
        mensagens=[{"role": "user", "content": pedido}],
        chave_api=_chave(usuario),
        titulo_projeto=projeto.titulo,
    )


def para_proximo_passo(projeto, etapa, usuario):
    pedido = (
        f"Gere o próximo passo da etapa {etapa.ordem} ({etapa.titulo}). O contexto "
        "do projeto já mostra quais passos essa etapa tem até agora; não repita "
        "nenhum. Diga também se, depois deste passo, a etapa já entrega o "
        "objetivo dela."
    )
    return Pedido(
        sistema=_sistema(projeto, extra=prompts.PLANEJADOR_PASSO),
        mensagens=[{"role": "user", "content": pedido}],
        chave_api=_chave(usuario),
        titulo_projeto=projeto.titulo,
    )


def para_briefing(projeto, usuario):
    return Pedido(
        sistema=_sistema(projeto, extra=prompts.ENTREVISTADOR),
        mensagens=[{"role": "user", "content": "O que você precisa saber antes de montar o plano?"}],
        chave_api=_chave(usuario),
        titulo_projeto=projeto.titulo,
    )


def para_revisao(submissao, usuario):
    # `submissao.passo` é uma consulta: ela precisa acontecer aqui dentro, do
    # lado síncrono. Receber o passo pronto por parâmetro só empurraria a mesma
    # consulta para a view assíncrona, que é onde ela estoura.
    passo = submissao.passo
    corpo = "\n\n".join(
        [
            "Revise o código deste passo contra os critérios de aceite.",
            ctx.codigo_do_aluno(submissao.conteudo),
        ]
    )
    return Pedido(
        sistema=_sistema(passo.etapa.plano.projeto, extra=prompts.REVISOR, passo=passo),
        mensagens=[{"role": "user", "content": corpo}],
        chave_api=_chave(usuario),
        criterios=list(passo.criterios_aceite or []),
        codigo=submissao.conteudo,
    )


def para_conversa(projeto, passo, historico, usuario):
    return Pedido(
        sistema=_sistema(projeto, passo=passo),
        mensagens=list(historico),
        chave_api=_chave(usuario),
        titulo_projeto=projeto.titulo,
    )
