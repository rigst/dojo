from django import forms
from django.contrib.auth.forms import UserCreationForm

from usuarios.models import Usuario


class CadastroForm(UserCreationForm):
    """UserCreationForm aponta para auth.User, que aqui está trocado.

    Sem este Meta o formulário estoura ao validar o nome de usuário. O erro
    aparece só no POST, então vale o teste que cobre o cadastro inteiro.
    """

    email = forms.EmailField(
        required=False,
        label="E-mail",
        help_text="Opcional. Sem ele não dá para redefinir a senha depois.",
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "email")
