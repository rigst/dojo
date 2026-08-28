"""Enche o banco temporário que os testes de navegador usam.

Roda como script dentro do processo do servidor de teste, antes de ele subir.
O conteúdo é o projeto de exemplo, o mesmo que o visitante recebe: já é escrito
à mão, então é idêntico a cada execução, que é exatamente o que a comparação de
telas precisa.
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from projetos.exemplo import criar_projeto_exemplo  # noqa: E402

USUARIO = "aluno"
SENHA = "dojo-navegador-1234"


def main():
    Usuario = get_user_model()
    if Usuario.objects.filter(username=USUARIO).exists():
        return

    aluno = Usuario.objects.create_user(username=USUARIO, password=SENHA, email="aluno@exemplo.com")
    criar_projeto_exemplo(aluno)


if __name__ == "__main__":
    main()
