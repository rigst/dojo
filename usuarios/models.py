from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Usuario(AbstractUser):
    class Tema(models.TextChoices):
        AUTO = "auto", "Acompanhar o sistema"
        CLARO = "claro", "Claro"
        ESCURO = "escuro", "Escuro"

    tema = models.CharField(max_length=8, choices=Tema.choices, default=Tema.AUTO)

    # Conta descartável criada pelo botão da tela de entrada. Não tem senha
    # utilizável, tem teto de gasto próprio e é apagada por idade (ver
    # usuarios/visitantes.py).
    eh_visitante = models.BooleanField(default=False)

    # Exceção ao teto do sistema, definida pela administração no admin. Vazio
    # significa "usa o do .env", que é o caso da esmagadora maioria: este campo
    # existe para o caso pontual de alguém precisar de mais sem que o limite
    # suba para todo mundo.
    limite_proprio_usd = models.DecimalField(
        "limite mensal próprio (US$)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Deixe vazio para usar o limite do sistema.",
    )

    @property
    def limite_mensal_usd(self):
        """O teto de gasto do mês, em dólar.

        Quem define é quem hospeda o app, e não cada pessoa: a chave de API é
        uma só, do provedor, e quem paga a conta é ele. Três casos, nesta
        ordem: exceção lançada no admin, conta de visitante (teto menor, porque
        é anônima e descartável) e o padrão do sistema.
        """
        if self.limite_proprio_usd is not None:
            return self.limite_proprio_usd
        if self.eh_visitante:
            return Decimal(str(settings.IA_LIMITE_VISITANTE_USD))
        return Decimal(str(settings.IA_LIMITE_MENSAL_USD))

    @property
    def limite_e_excecao(self):
        return self.limite_proprio_usd is not None

    def __str__(self):
        return self.get_full_name() or self.get_username()


class UsoMensal(models.Model):
    """Consumo de API por usuário e mês. A fonte da verdade da cota.

    Somar as mensagens a cada checagem funcionaria, mas cresce sem limite e
    coloca um agregado no caminho de toda pergunta. Um contador incrementado a
    cada resposta responde em uma leitura.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usos"
    )
    # "AAAA-MM" em texto: ordena igual à data e não depende do fuso na hora de
    # comparar dois meses.
    ano_mes = models.CharField(max_length=7)
    custo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))
    mensagens = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "ano_mes"], name="uso_unico_por_mes"),
        ]
        ordering = ["-ano_mes"]

    def __str__(self):
        return f"{self.usuario} · {self.ano_mes} · US$ {self.custo_usd}"

    @staticmethod
    def competencia_atual():
        return timezone.localdate().strftime("%Y-%m")
