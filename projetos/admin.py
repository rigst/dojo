from django.contrib import admin

from projetos.models import Etapa, Passo, Plano, Projeto, Stack


@admin.register(Stack)
class StackAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria")
    list_filter = ("categoria",)
    search_fields = ("nome",)


class EtapaInline(admin.TabularInline):
    model = Etapa
    extra = 0


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "usuario", "nivel", "status", "atualizado_em")
    list_filter = ("status", "nivel")
    search_fields = ("titulo", "objetivo", "usuario__username")
    filter_horizontal = ("stacks",)


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ("projeto", "versao", "ativo", "gerado_em", "modelo")
    list_filter = ("ativo",)
    inlines = [EtapaInline]


@admin.register(Passo)
class PassoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "etapa", "status", "concluido_em")
    list_filter = ("status",)
    search_fields = ("titulo",)
