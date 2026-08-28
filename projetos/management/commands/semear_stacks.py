from django.core.management.base import BaseCommand

from projetos.models import Stack

# Lista curta de propósito: é ponto de partida para o autocompletar, não um
# catálogo. O usuário pode digitar qualquer outra na hora de criar o projeto.
STACKS = [
    ("Python", Stack.Categoria.LINGUAGEM),
    ("JavaScript", Stack.Categoria.LINGUAGEM),
    ("TypeScript", Stack.Categoria.LINGUAGEM),
    ("Go", Stack.Categoria.LINGUAGEM),
    ("Rust", Stack.Categoria.LINGUAGEM),
    ("Java", Stack.Categoria.LINGUAGEM),
    ("C#", Stack.Categoria.LINGUAGEM),
    ("Django", Stack.Categoria.FRAMEWORK),
    ("FastAPI", Stack.Categoria.FRAMEWORK),
    ("Flask", Stack.Categoria.FRAMEWORK),
    ("Express", Stack.Categoria.FRAMEWORK),
    ("Spring Boot", Stack.Categoria.FRAMEWORK),
    ("Rails", Stack.Categoria.FRAMEWORK),
    ("PostgreSQL", Stack.Categoria.BANCO),
    ("SQLite", Stack.Categoria.BANCO),
    ("MySQL", Stack.Categoria.BANCO),
    ("MongoDB", Stack.Categoria.BANCO),
    ("Redis", Stack.Categoria.BANCO),
    ("React", Stack.Categoria.FRONT),
    ("Vue", Stack.Categoria.FRONT),
    ("HTMX", Stack.Categoria.FRONT),
    ("Tailwind CSS", Stack.Categoria.FRONT),
    ("Docker", Stack.Categoria.INFRA),
    ("Linux", Stack.Categoria.INFRA),
    ("Git", Stack.Categoria.INFRA),
    ("Nginx", Stack.Categoria.INFRA),
]


class Command(BaseCommand):
    help = "Cria as stacks conhecidas. Rodar de novo não duplica nada."

    def handle(self, *args, **opcoes):
        criadas = 0
        for nome, categoria in STACKS:
            _, nova = Stack.objects.get_or_create(nome=nome, defaults={"categoria": categoria})
            criadas += int(nova)
        self.stdout.write(self.style.SUCCESS(f"{criadas} stack(s) criada(s); {len(STACKS)} no total."))
