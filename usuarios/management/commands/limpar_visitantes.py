from django.core.management.base import BaseCommand

from usuarios.visitantes import limpar_expirados


class Command(BaseCommand):
    help = "Apaga as contas de visitante que passaram do prazo, com tudo o que produziram."

    def handle(self, *args, **opcoes):
        total = limpar_expirados()
        self.stdout.write(self.style.SUCCESS(f"{total} visitante(s) removido(s)."))
