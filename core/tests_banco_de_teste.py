"""Qual banco a suíte usa: nunca o do .env, e o Postgres do CI só quando pedido.

Roda o settings num subprocesso com o pytest importado, que é o que liga o
IS_TEST, para não recarregar o módulo de settings já em uso pela suíte.
"""

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRODUCAO = "postgres://dojo@banco-de-producao:5432/dojo"
CI = "postgres://postgres@localhost:5432/postgres"


def _banco_da_suite(**extra):
    ambiente = {
        k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "DOJO_TEST_DATABASE_URL"}
    }
    ambiente.update(DJANGO_ENV_FILE=os.devnull, DATABASE_URL=PRODUCAO, **extra)
    codigo = (
        "import pytest, config.settings as s; d = s.DATABASES['default']; "
        "print(d['ENGINE'], d.get('HOST', ''), d['NAME'])"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env=ambiente,
        capture_output=True,
        text=True,
        check=True,
    )
    return saida.stdout.split()


def test_suite_ignora_o_database_url_de_producao():
    motor, *_ = _banco_da_suite()
    assert motor == "django.db.backends.sqlite3"


def test_suite_usa_o_postgres_do_ci_quando_pedido_explicitamente():
    motor, host, nome = _banco_da_suite(DOJO_TEST_DATABASE_URL=CI)
    assert motor == "django.db.backends.postgresql"
    assert (host, nome) == ("localhost", "postgres")
