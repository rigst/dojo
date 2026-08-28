"""Entrega de arquivos estáticos em desenvolvimento.

Existe por um motivo específico: a view padrão do Django manda só
`Last-Modified`, sem `Cache-Control`. Sem essa diretiva, o navegador aplica
cache heurístico por conta própria. Costuma guardar o arquivo por uma fração
do tempo desde a última modificação. Na prática, você edita o CSS, recarrega, e
continua vendo a folha antiga sem nenhum aviso de que está vendo o passado.

Em produção nada disso se aplica: lá o `ManifestStaticFilesStorage` põe o hash
do conteúdo no nome do arquivo, que é a forma correta de invalidar cache.
"""

from django.contrib.staticfiles.views import serve


def servir_sem_cache(request, path, **kwargs):
    resposta = serve(request, path, **kwargs)
    resposta["Cache-Control"] = "no-store"
    return resposta
