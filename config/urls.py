from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from core.estaticos import servir_sem_cache

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("conta/", include("usuarios.urls")),
    path("projetos/", include("projetos.urls")),
    path("projetos/", include("mentoria.urls")),
    path("revisoes/", include("revisoes.urls")),
    path("", include("legal.urls")),
]

if settings.DEBUG:
    # O `runserver` serve os estáticos sozinho, mas o app roda sob uvicorn (é
    # o servidor que aguenta o SSE) e ele não serve arquivo nenhum. Sem esta
    # rota, a tela de desenvolvimento aparece sem CSS.
    #
    # A view é nossa e não a do Django por causa do cabeçalho de cache;
    # a razão está em core/estaticos.py.
    urlpatterns += [re_path(r"^static/(?P<path>.*)$", servir_sem_cache)]
