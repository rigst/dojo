from decimal import Decimal

from django.db import models

from projetos.models import Passo, Projeto


class Conversa(models.Model):
    """Um chat por projeto, com as mensagens ancoradas ao passo em foco.

    Uma conversa por passo fragmentaria o histórico e faria o mentor esquecer o
    que já explicou duas telas atrás; uma conversa global perderia o foco. A
    âncora resolve os dois: o histórico é contínuo, o contexto é do passo.
    """

    projeto = models.OneToOneField(Projeto, on_delete=models.CASCADE, related_name="conversa")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversa de {self.projeto}"


class Mensagem(models.Model):
    class Papel(models.TextChoices):
        ALUNO = "user", "Aluno"
        MENTOR = "assistant", "Mentor"

    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="mensagens")
    papel = models.CharField(max_length=10, choices=Papel.choices)
    conteudo = models.TextField()
    passo = models.ForeignKey(Passo, null=True, blank=True, on_delete=models.SET_NULL)

    modelo = models.CharField(max_length=60, blank=True)
    versao_prompt = models.PositiveSmallIntegerField(null=True, blank=True)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    tokens_cache_leitura = models.PositiveIntegerField(default=0)
    tokens_cache_escrita = models.PositiveIntegerField(default=0)
    custo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))
    stop_reason = models.CharField(max_length=30, blank=True)
    # Guardado para rastrear uma resposta estranha junto ao suporte da API.
    request_id = models.CharField(max_length=64, blank=True)
    # Preenchido quando a resposta não terminou: "cancelado" (a aba fechou) ou
    # o erro que interrompeu. O texto parcial fica no conteúdo.
    erro = models.CharField(max_length=200, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]

    @property
    def do_mentor(self):
        return self.papel == self.Papel.MENTOR

    def __str__(self):
        return f"{self.get_papel_display()}: {self.conteudo[:60]}"
