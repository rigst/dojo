from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from usuarios.models import UsoMensal, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "eh_visitante",
        "limite_proprio_usd",
        "date_joined",
        "is_staff",
    )
    list_filter = (*UserAdmin.list_filter, "eh_visitante")
    fieldsets = (
        *(UserAdmin.fieldsets or ()),
        ("Dojo", {"fields": ("tema", "eh_visitante", "limite_proprio_usd")}),
    )


@admin.register(UsoMensal)
class UsoMensalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "ano_mes", "custo_usd", "mensagens")
    list_filter = ("ano_mes",)
    search_fields = ("usuario__username",)
