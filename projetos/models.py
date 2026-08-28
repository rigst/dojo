from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.models import Registro


class Stack(models.Model):
    """Tecnologia que o projeto usa.

    Existe como tabela, e não como texto solto no projeto, para o mentor
    receber sempre o mesmo nome ("PostgreSQL", não "postgres"/"psql"/"pg") e
    para a semeadura dar autocompletar decente já na primeira tela.
    """

    class Categoria(models.TextChoices):
        LINGUAGEM = "linguagem", "Linguagem"
        FRAMEWORK = "framework", "Framework"
        BANCO = "banco", "Banco de dados"
        FRONT = "front", "Front-end"
        INFRA = "infra", "Infraestrutura"
        OUTRO = "outro", "Outro"

    nome = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    categoria = models.CharField(max_length=12, choices=Categoria.choices, default=Categoria.OUTRO)

    class Meta:
        ordering = ["categoria", "nome"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ProjetoQuerySet(models.QuerySet):
    def do_usuario(self, usuario):
        return self.filter(usuario=usuario)

    def ativos(self):
        return self.exclude(status=Projeto.Status.ARQUIVADO)


class Projeto(Registro):
    class Nivel(models.TextChoices):
        INICIANTE = "iniciante", "Iniciante"
        INTERMEDIARIO = "intermediario", "Intermediário"
        AVANCADO = "avancado", "Avançado"

    class Didatica(models.TextChoices):
        # O socrático pergunta antes de afirmar; o direto explica e manda fazer.
        # Muda o system prompt, não a interface.
        SOCRATICO = "socratico", "Socrático: me faça pensar antes"
        DIRETO = "direto", "Direto: me diga o que fazer"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PLANEJADO = "planejado", "Planejado"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDO = "concluido", "Concluído"
        ARQUIVADO = "arquivado", "Arquivado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projetos"
    )
    titulo = models.CharField("título", max_length=120)
    objetivo = models.TextField(
        "o que você quer construir",
        help_text="Quanto mais concreto, melhor o plano. Diga o que o programa faz e para quem.",
    )
    stacks = models.ManyToManyField(Stack, related_name="projetos", blank=True)
    nivel = models.CharField("nível", max_length=14, choices=Nivel.choices, default=Nivel.INICIANTE)
    horas_por_semana = models.PositiveSmallIntegerField(default=5)
    preferencia_didatica = models.CharField(
        "como você quer ser ensinado", max_length=10, choices=Didatica.choices, default=Didatica.SOCRATICO
    )
    status = models.CharField(max_length=13, choices=Status.choices, default=Status.RASCUNHO)

    objects = ProjetoQuerySet.as_manager()

    class Meta:
        ordering = ["-atualizado_em"]

    def get_absolute_url(self):
        return reverse("projeto_detalhe", args=[self.pk])

    @property
    def plano_ativo(self):
        return self.planos.filter(ativo=True).first()

    @property
    def stacks_texto(self):
        return ", ".join(s.nome for s in self.stacks.all()) or "sem stack definida"

    def progresso(self):
        """(concluídos, total, percentual) do plano ativo."""
        plano = self.plano_ativo
        if not plano:
            return 0, 0, 0
        passos = Passo.objects.filter(etapa__plano=plano)
        total = passos.count()
        if not total:
            return 0, 0, 0
        feitos = passos.filter(status=Passo.Status.CONCLUIDO).count()
        return feitos, total, round(feitos * 100 / total)

    def __str__(self):
        return self.titulo


class Plano(models.Model):
    """Uma versão do roteiro do projeto.

    Versionado de propósito: replanejar depois de o aluno travar é normal, e
    perder o roteiro anterior apagaria o registro de como o entendimento do
    projeto mudou. Só um plano fica `ativo` por projeto.
    """

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="planos")
    versao = models.PositiveSmallIntegerField(default=1)
    resumo = models.TextField(blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    ativo = models.BooleanField(default=True)
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-versao"]
        constraints = [
            models.UniqueConstraint(fields=["projeto", "versao"], name="versao_unica_por_projeto"),
            models.UniqueConstraint(
                fields=["projeto"], condition=models.Q(ativo=True), name="um_plano_ativo_por_projeto"
            ),
        ]

    def __str__(self):
        return f"{self.projeto} · plano v{self.versao}"


class Etapa(models.Model):
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name="etapas")
    ordem = models.PositiveSmallIntegerField(default=1)
    titulo = models.CharField("título", max_length=120)
    objetivo = models.TextField(blank=True)

    class Meta:
        ordering = ["ordem"]

    def __str__(self):
        return f"{self.ordem}. {self.titulo}"


class PassoQuerySet(models.QuerySet):
    def do_usuario(self, usuario):
        return self.filter(etapa__plano__projeto__usuario=usuario)


class Passo(models.Model):
    class Status(models.TextChoices):
        BLOQUEADO = "bloqueado", "Bloqueado"
        DISPONIVEL = "disponivel", "Disponível"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        EM_REVISAO = "em_revisao", "Em revisão"
        CONCLUIDO = "concluido", "Concluído"

    etapa = models.ForeignKey(Etapa, on_delete=models.CASCADE, related_name="passos")
    ordem = models.PositiveSmallIntegerField(default=1)
    titulo = models.CharField("título", max_length=150)

    # As três camadas da orientação. Separadas em campos, e não num texto só,
    # porque a tela as apresenta em hierarquias diferentes, e porque um campo
    # vazio denuncia plano mal gerado, o que um blocão de markdown esconderia.
    o_que_fazer = models.TextField(blank=True)
    como_fazer = models.TextField(blank=True)
    teoria = models.TextField("por que é assim", blank=True)

    criterios_aceite = models.JSONField(default=list, blank=True)
    armadilhas = models.JSONField(default=list, blank=True)
    recursos = models.JSONField(default=list, blank=True)
    estimativa_min = models.PositiveSmallIntegerField(null=True, blank=True)

    status = models.CharField(max_length=13, choices=Status.choices, default=Status.BLOQUEADO)
    concluido_em = models.DateTimeField(null=True, blank=True)
    # Registra quando o aluno marcou o passo como feito sem passar pela revisão.
    concluido_manualmente = models.BooleanField(default=False)

    objects = PassoQuerySet.as_manager()

    class Meta:
        ordering = ["etapa__ordem", "ordem"]

    @property
    def projeto(self):
        return self.etapa.plano.projeto

    @property
    def numero(self):
        return f"{self.etapa.ordem}.{self.ordem}"

    def _fila(self):
        """Os passos do mesmo plano, na ordem em que devem ser feitos.

        Uma consulta só, resolvida em memória: um plano tem dezenas de passos,
        não milhares, e comparar (etapa, ordem) em SQL para achar "o seguinte"
        exigiria uma janela que não paga o próprio custo de leitura.
        """
        if not hasattr(self, "_fila_cache"):
            self._fila_cache = list(
                Passo.objects.filter(etapa__plano_id=self.etapa.plano_id).select_related("etapa")
            )
        return self._fila_cache

    def _indice(self):
        return next((i for i, p in enumerate(self._fila()) if p.pk == self.pk), 0)

    @property
    def posicao(self):
        """Qual passo é este, contando o plano inteiro. Começa em 1."""
        return self._indice() + 1

    @property
    def total_no_plano(self):
        return len(self._fila())

    @property
    def anterior(self):
        i = self._indice()
        return self._fila()[i - 1] if i > 0 else None

    @property
    def proximo(self):
        fila = self._fila()
        i = self._indice()
        return fila[i + 1] if i + 1 < len(fila) else None

    def get_absolute_url(self):
        return reverse("passo_detalhe", args=[self.pk])

    def __str__(self):
        return f"{self.numero} {self.titulo}"
