from django.contrib import admin

from mentoria.models import Conversa, Mensagem


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ("projeto", "passo", "criado_em")


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("conversa", "papel", "modelo", "custo_usd", "erro", "criado_em")
    list_filter = ("papel", "modelo")
    # O conteúdo é longo e a listagem serve para achar a mensagem cara ou a que
    # falhou, não para ler a conversa.
    search_fields = ("conteudo",)
