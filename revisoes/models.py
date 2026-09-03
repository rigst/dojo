from decimal import Decimal

from django.conf import settings
from django.db import models

from projetos.models import Passo


class Submissao(models.Model):
    """O que o aluno colou para um passo.

    Guardada inteira e para sempre: é o registro de como o código evoluiu entre
    uma revisão e a seguinte, e é o que permite o mentor dizer "isto você já
    corrigiu" em vez de repetir a mesma observação.
    """

    passo = models.ForeignKey(Passo, on_delete=models.CASCADE, related_name="submissoes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Submissão de {self.passo} em {self.criado_em:%d/%m %H:%M}"


class Revisao(models.Model):
    class Veredito(models.TextChoices):
        ATENDE = "atende", "Atende"
        RESSALVAS = "atende_com_ressalvas", "Atende com ressalvas"
        NAO_ATENDE = "nao_atende", "Ainda não atende"

    submissao = models.OneToOneField(Submissao, on_delete=models.CASCADE, related_name="revisao")
    veredito = models.CharField(max_length=20, choices=Veredito.choices)
    resumo = models.TextField(blank=True)
    criterios_avaliados = models.JSONField(default=list, blank=True)
    pontos_fortes = models.JSONField(default=list, blank=True)
    problemas = models.JSONField(default=list, blank=True)
    proximo_passo_sugerido = models.TextField(blank=True)

    modelo = models.CharField(max_length=60, blank=True)
    custo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))
    request_id = models.CharField(max_length=64, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_veredito_display()}: {self.submissao.passo}"

    @property
    def aprovado(self):
        """Passa o passo adiante.

        Ressalva é aviso, não bloqueio: o veredito `atende_com_ressalvas` fica
        registrado (e visível na tela, com o que ajustar) mas libera o próximo
        passo do mesmo jeito que `atende`. Só `nao_atende` segura a fila, e
        mesmo assim o aluno pode seguir manualmente pelo botão de conclusão.
        """
        return self.veredito in (self.Veredito.ATENDE, self.Veredito.RESSALVAS)

    @property
    def classe_badge(self):
        # dict[str, str] e não dict[Veredito, str]: TextChoices é subclasse
        # de str, e o campo devolve str — anotar assim deixa os dois lados
        # concordarem sem converter nada em tempo de execução.
        classes: dict[str, str] = {
            self.Veredito.ATENDE: "ds-badge--ok",
            self.Veredito.RESSALVAS: "ds-badge--atencao",
            self.Veredito.NAO_ATENDE: "ds-badge--erro",
        }
        return classes[self.veredito]
