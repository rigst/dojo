"""Formatação e ciclo de vida dos eventos SSE.

Um lugar só para as três coisas que todo stream do app precisa acertar: o
formato do quadro, o cabeçalho que impede o proxy de segurar o buffer, e o
batimento que mantém a conexão viva enquanto o modelo pensa.
"""

import json

from django.http import StreamingHttpResponse

# Intervalo do batimento. Precisa ser menor que o read timeout do nginx (60s
# por padrão): sem tráfego nenhum, o proxy derruba a conexão no meio de uma
# resposta longa e o navegador vê um erro que não existiu.
INTERVALO_BATIMENTO = 15


def quadro(evento, dados):
    """Um evento SSE. `dados` vai em JSON: texto do modelo tem quebra de linha,
    e quebra de linha crua dentro de `data:` encerraria o quadro no meio."""
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def comentario(texto=""):
    """Linha ignorada pelo cliente. É assim que o batimento não vira evento."""
    return f": {texto}\n\n"


def resposta(gerador):
    resposta = StreamingHttpResponse(gerador, content_type="text/event-stream")
    resposta["Cache-Control"] = "no-cache"
    # Sem isto o nginx acumula a resposta inteira antes de repassar, e o
    # streaming vira uma espera longa seguida de um bloco de texto.
    resposta["X-Accel-Buffering"] = "no"
    return resposta
