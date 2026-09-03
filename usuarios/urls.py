from django.contrib.auth import views as auth_views
from django.urls import path

from usuarios import views

urlpatterns = [
    # A view é nossa por causa da trava de força bruta e do
    # redirect_authenticated_user, que o Django não liga sozinho: sem ele, quem
    # já entrou e volta a esta URL vê o formulário renderizado DENTRO do shell
    # do app, com barra lateral e tudo.
    path("entrar/", views.Entrar.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("criar/", views.cadastrar, name="cadastrar"),
    path("visitante/", views.entrar_como_visitante, name="entrar_visitante"),
    # Trocar e recuperar senha. Não existiam: quem esquecesse a senha ficava
    # sem conta, e quem quisesse trocá-la só conseguia pelo admin do Django.
    # As views são as do próprio Django; o que é nosso são os templates.
    path(
        "senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="usuarios/senha_trocar.html", success_url="/conta/senha/pronto/"
        ),
        name="senha_trocar",
    ),
    path(
        "senha/pronto/",
        auth_views.PasswordChangeDoneView.as_view(template_name="usuarios/senha_pronto.html"),
        name="password_change_done",
    ),
    path(
        "senha/recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="usuarios/senha_recuperar.html",
            email_template_name="usuarios/senha_email.txt",
            subject_template_name="usuarios/senha_email_assunto.txt",
            success_url="/conta/senha/recuperar/enviado/",
        ),
        name="password_reset",
    ),
    path(
        "senha/recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="usuarios/senha_enviado.html"),
        name="password_reset_done",
    ),
    path(
        "senha/nova/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="usuarios/senha_nova.html", success_url="/conta/senha/nova/pronto/"
        ),
        name="password_reset_confirm",
    ),
    path(
        "senha/nova/pronto/",
        auth_views.PasswordResetCompleteView.as_view(template_name="usuarios/senha_concluida.html"),
        name="password_reset_complete",
    ),
    path("", views.conta, name="conta"),
    path("tema/", views.tema, name="tema"),
    path("meus-dados.json", views.exportar_dados, name="exportar_dados"),
    path("excluir/", views.excluir_conta, name="excluir_conta"),
]
