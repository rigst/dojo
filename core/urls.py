from django.urls import path

from projetos import views as projetos_views

from .healthz import healthz

urlpatterns = [
    path("", projetos_views.lista, name="painel"),
    # As duas rotas servem a mesma sonda. `/saude/` é a antiga, que o nginx de
    # produção e o provisionar.md usam; `/healthz/` é o nome padrão da frota,
    # que o smoke-test do cd-deploy.sh consulta.
    path("saude/", healthz, name="saude"),
    path("healthz/", healthz, name="healthz"),
]
