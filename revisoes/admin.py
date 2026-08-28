from django.contrib import admin

from revisoes.models import Revisao, Submissao


@admin.register(Submissao)
class SubmissaoAdmin(admin.ModelAdmin):
    list_display = ("passo", "usuario", "criado_em")
    search_fields = ("passo__titulo", "usuario__username")


@admin.register(Revisao)
class RevisaoAdmin(admin.ModelAdmin):
    list_display = ("submissao", "veredito", "modelo", "custo_usd", "criado_em")
    list_filter = ("veredito",)
