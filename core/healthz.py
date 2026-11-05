"""Sonda de saúde: `/healthz/` (smoke-test do CD) e `/saude/` (nginx, monitor).

Responde 200 só quando o processo consegue usar o que precisa para servir uma
página: o banco e o cache. Qualquer falha vira 503, que o deploy/cd-deploy.sh
trata como deploy quebrado e reverte (rigst/ci RUNBOOK.md, seção 7.8).

O cache entra porque é nele que moram as travas de força bruta da entrada e de
criação de visitantes: com o Redis fora, o app responde mas os controles de
segurança deixam de valer.

Sem checagem de broker: o Dojo não usa Celery (ver config/settings.py).

O corpo é só "ok" ou "indisponivel": a rota é pública, e qual componente caiu
fica no log, não na resposta. Nenhum middleware do app exige login, então a
rota não precisa de isenção.
"""

import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def _banco():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _cache():
    chave = f"healthz:{uuid.uuid4().hex}"
    cache.set(chave, "1", 10)
    if cache.get(chave) != "1":
        raise RuntimeError("cache não devolveu o valor gravado")
    cache.delete(chave)


VERIFICACOES = (("banco", _banco), ("cache", _cache))


@never_cache
@require_GET
def healthz(request):
    falhas = []
    for nome, verificar in VERIFICACOES:
        try:
            verificar()
        except Exception:  # sonda: qualquer falha é "indisponível", e vai para o log
            logger.exception("healthz: %s indisponível", nome)
            falhas.append(nome)
    if falhas:
        return HttpResponse("indisponivel\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")
