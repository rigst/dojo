from django.db import models


class Registro(models.Model):
    """Base de tudo que é criado e editado por gente."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
