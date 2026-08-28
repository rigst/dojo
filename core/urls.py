from django.urls import path

from projetos import views as projetos_views

from . import views

urlpatterns = [
    path("", projetos_views.lista, name="painel"),
    path("saude/", views.saude, name="saude"),
]
