from django.urls import path

from legal import views

urlpatterns = [
    path("termos/", views.termos, name="termos"),
    path("privacidade/", views.privacidade, name="privacidade"),
]
