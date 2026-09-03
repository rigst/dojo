#!/usr/bin/env python
"""Uma chamada real de cada tipo, para conferir chave, custo e cache.

Roda fora do servidor e não grava nada: serve para responder "a integração está
de pé?" sem subir o app nem criar dado de teste no banco de produção.

    DOJO_IA_BACKEND=anthropic .venv/bin/python scripts/smoke_ia.py

O que olhar na saída: `cache_lido` maior que zero na SEGUNDA chamada. Se ficar
zerado nas duas, algo no prefixo está mudando entre requisições (ver o comentário
no topo de ia/prompts.py) e o custo está multiplicado sem nada denunciar na tela.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from asgiref.sync import async_to_sync  # noqa: E402
from django.conf import settings  # noqa: E402

from ia import motor  # noqa: E402
from ia.preparo import Pedido  # noqa: E402
from ia.prompts import MENTOR  # noqa: E402

CONTEXTO = (
    "CONTEXTO DO PROJETO\nTítulo: Lista de tarefas\n"
    "Objetivo: um app web de tarefas com login.\nStack: Python, Django, SQLite\n"
    "Nível declarado: Iniciante"
)


def pedido(pergunta):
    return Pedido(
        sistema=[
            {"type": "text", "text": MENTOR, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": CONTEXTO, "cache_control": {"type": "ephemeral"}},
        ],
        mensagens=[{"role": "user", "content": pergunta}],
        chave_api=settings.ANTHROPIC_API_KEY,
        titulo_projeto="Lista de tarefas",
    )


def mostrar(rotulo, uso):
    print(
        f"{rotulo:12} entrada={uso.entrada:6} saída={uso.saida:6} "
        f"cache_lido={uso.cache_leitura:6} cache_escrito={uso.cache_escrita:6} "
        f"US$ {uso.custo_usd} req={uso.request_id}"
    )


def main():
    print(f"backend={settings.IA_BACKEND} modelo={motor.modelo_em_uso()}\n")

    tokens = async_to_sync(motor.contar_tokens)(pedido("teste"))
    print(f"tamanho do pedido: {tokens} tokens\n")

    plano, uso = async_to_sync(motor.gerar_plano)(pedido("Monte o plano deste projeto."))
    mostrar("plano", uso)
    print(f"  {len(plano.etapas)} etapa(s), {sum(len(e.passos) for e in plano.etapas)} passo(s)")

    async def conversar():
        pedacos = 0
        final = None
        async for evento in motor.conversar(pedido("Por que preciso de migration?"), None):
            if evento["tipo"] == "delta":
                pedacos += 1
            elif evento["tipo"] == "fim":
                final = evento
        return pedacos, final

    pedacos, final = async_to_sync(conversar)()
    mostrar("conversa", final["uso"])
    print(f"  {pedacos} pedaço(s) de texto; mais de um significa streaming de verdade")


if __name__ == "__main__":
    main()
