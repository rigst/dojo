from django.urls import path

from revisoes import views

urlpatterns = [
    path("passo/<int:pk>/submeter/", views.submeter, name="revisao_submeter"),
    path("aguardar/<int:pk>/", views.aguardar, name="revisao_aguardar"),
    path("aguardar/<int:pk>/stream/", views.revisar_stream, name="revisao_stream"),
    path("<int:pk>/", views.detalhe, name="revisao_detalhe"),
]
