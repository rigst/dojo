"""Trava de força bruta na tela de entrada.

A porta de visita deixou o Dojo mais visível, e a tela de entrada é o alvo
óbvio de quem varre a internet testando senha. A trava conta tentativas
fracassadas por IP e recusa depois do teto, devolvendo 429.

Mora no cache, que em produção é compartilhado entre os workers (o settings
recusa subir sem isso). Com o cache padrão do Django, que vive dentro de um
processo, o limite valeria uma vez por worker, ou seja, quase não valeria.
"""

from django.conf import settings
from django.core.cache import cache


def _chave(ip):
    return f"login:falhas:{ip or 'desconhecido'}"


def ip_do_pedido(request):
    """O IP de quem pede.

    Atrás de proxy, o REMOTE_ADDR é o do proxy e todo mundo vira o mesmo
    cliente; por isso o X-Forwarded-For é lido, mas só quando a configuração
    diz que existe um proxy confiável na frente. Confiar nesse cabeçalho sem
    isso é deixar qualquer um escolher o próprio identificador e escapar da
    trava trocando de valor a cada tentativa.
    """
    if settings.CONFIA_NO_X_FORWARDED_FOR:
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def bloqueado(ip):
    return int(cache.get(_chave(ip), 0)) >= settings.LOGIN_TENTATIVAS


def registrar_falha(ip):
    chave = _chave(ip)
    if cache.add(chave, 1, timeout=settings.LOGIN_JANELA_SEGUNDOS):
        return
    try:
        cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, timeout=settings.LOGIN_JANELA_SEGUNDOS)


def limpar(ip):
    """Entrou: o contador zera, para não punir quem só errou a senha antes."""
    cache.delete(_chave(ip))
