from django.urls import path

from mentoria import views

urlpatterns = [
    path("<int:pk>/chat/", views.chat, name="chat"),
    path("<int:pk>/chat/stream/", views.stream, name="chat_stream"),
]
