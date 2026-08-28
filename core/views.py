from django.db import connection
from django.http import HttpResponse


def saude(request):
    """Sonda de saúde para o nginx e para o systemd.

    Toca o banco de propósito: um processo que responde mas perdeu a conexão
    com o Postgres está de pé e inútil, e é justamente esse estado que uma
    sonda que só devolve 200 deixa passar.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("banco indisponivel\n", status=503, content_type="text/plain")

    return HttpResponse("ok\n", content_type="text/plain")
