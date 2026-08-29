from django.urls import path

from projetos import views

urlpatterns = [
    path("novo/", views.novo, name="projeto_novo"),
    path("<int:pk>/", views.detalhe, name="projeto_detalhe"),
    path("<int:pk>/editar/", views.editar, name="projeto_editar"),
    path("<int:pk>/arquivar/", views.arquivar, name="projeto_arquivar"),
    path("<int:pk>/excluir/", views.excluir, name="projeto_excluir"),
    path("<int:pk>/planejar/", views.planejar, name="projeto_planejar"),
    path("<int:pk>/planejar/stream/", views.planejar_stream, name="projeto_planejar_stream"),
    path("<int:pk>/planejar/briefing/", views.briefing_stream, name="projeto_briefing_stream"),
    path("<int:pk>/planejar/passo/", views.passo_gerando, name="projeto_passo_gerando"),
    path("<int:pk>/planejar/passo/stream/", views.passo_gerar_stream, name="projeto_passo_gerar_stream"),
    path("<int:pk>/plano.md", views.exportar_markdown, name="projeto_markdown"),
    path("<int:pk>/plano/editar/", views.plano_editar, name="plano_editar"),
    path("<int:pk>/plano/v<int:versao>/", views.plano_versao, name="plano_versao"),
    path("passo/<int:pk>/revisoes/", views.passo_revisoes, name="passo_revisoes"),
    path("etapa/<int:pk>/editar/", views.etapa_editar, name="etapa_editar"),
    path("etapa/<int:pk>/passo/novo/", views.passo_novo, name="passo_novo"),
    path("passo/<int:pk>/editar/", views.passo_editar, name="passo_editar"),
    path("passo/<int:pk>/mover/", views.passo_mover, name="passo_mover"),
    path("passo/<int:pk>/remover/", views.passo_remover, name="passo_remover"),
    path("passo/<int:pk>/", views.passo_detalhe, name="passo_detalhe"),
    path("passo/<int:pk>/concluir/", views.passo_concluir, name="passo_concluir"),
]
