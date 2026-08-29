"""Porta de entrada da mentoria.

Nenhuma view importa `anthropic`: importa daqui. Isso mantém a escolha do
backend num lugar só e deixa a suíte inteira rodar contra o dublê.

Todas as funções recebem um `ia.preparo.Pedido`, montado do lado síncrono: o
motor não toca o ORM (ver ia/preparo.py).
"""

from django.conf import settings

from ia.motores import anthropic_motor, fake_motor


def _motor():
    # Lido a cada chamada, e não no import: `settings.IA_BACKEND` é trocado por
    # teste, e um motor amarrado no import ignoraria a troca.
    return fake_motor if settings.IA_BACKEND == "fake" else anthropic_motor


async def contar_tokens(pedido):
    return await _motor().contar_tokens(pedido)


async def gerar_briefing(pedido):
    return await _motor().gerar_briefing(pedido)


async def gerar_plano(pedido):
    return await _motor().gerar_plano(pedido)


async def gerar_proximo_passo(pedido):
    return await _motor().gerar_proximo_passo(pedido)


async def revisar(pedido):
    return await _motor().revisar(pedido)


def conversar(pedido, usuario):
    """Devolve o gerador assíncrono de eventos (não é awaitable)."""
    return _motor().conversar(pedido, usuario)


def modelo_em_uso():
    return fake_motor.MODELO if settings.IA_BACKEND == "fake" else settings.IA_MODELO
