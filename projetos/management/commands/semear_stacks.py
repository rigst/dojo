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
    ("Kotlin", Stack.Categoria.LINGUAGEM),
    ("Swift", Stack.Categoria.LINGUAGEM),
    ("C#", Stack.Categoria.LINGUAGEM),
    ("C", Stack.Categoria.LINGUAGEM),
    ("C++", Stack.Categoria.LINGUAGEM),
    ("PHP", Stack.Categoria.LINGUAGEM),
    ("Ruby", Stack.Categoria.LINGUAGEM),
    ("Elixir", Stack.Categoria.LINGUAGEM),
    ("Dart", Stack.Categoria.LINGUAGEM),
    ("Django", Stack.Categoria.FRAMEWORK),
    ("FastAPI", Stack.Categoria.FRAMEWORK),
    ("Flask", Stack.Categoria.FRAMEWORK),
    ("Express", Stack.Categoria.FRAMEWORK),
    ("NestJS", Stack.Categoria.FRAMEWORK),
    ("Next.js", Stack.Categoria.FRAMEWORK),
    ("Spring Boot", Stack.Categoria.FRAMEWORK),
    ("Rails", Stack.Categoria.FRAMEWORK),
    ("Laravel", Stack.Categoria.FRAMEWORK),
    ("ASP.NET", Stack.Categoria.FRAMEWORK),
    ("Phoenix", Stack.Categoria.FRAMEWORK),
    ("Flutter", Stack.Categoria.FRAMEWORK),
    ("React Native", Stack.Categoria.FRAMEWORK),
    ("PostgreSQL", Stack.Categoria.BANCO),
    ("SQLite", Stack.Categoria.BANCO),
    ("MySQL", Stack.Categoria.BANCO),
    ("MariaDB", Stack.Categoria.BANCO),
    ("MongoDB", Stack.Categoria.BANCO),
    ("Redis", Stack.Categoria.BANCO),
    ("SQL Server", Stack.Categoria.BANCO),
    ("Firebase", Stack.Categoria.BANCO),
    ("Supabase", Stack.Categoria.BANCO),
    ("React", Stack.Categoria.FRONT),
    ("Vue", Stack.Categoria.FRONT),
    ("Svelte", Stack.Categoria.FRONT),
    ("Angular", Stack.Categoria.FRONT),
    ("HTMX", Stack.Categoria.FRONT),
    ("Alpine.js", Stack.Categoria.FRONT),
    ("Tailwind CSS", Stack.Categoria.FRONT),
    ("Bootstrap", Stack.Categoria.FRONT),
    ("Docker", Stack.Categoria.INFRA),
    ("Kubernetes", Stack.Categoria.INFRA),
    ("Linux", Stack.Categoria.INFRA),
    ("Git", Stack.Categoria.INFRA),
    ("Nginx", Stack.Categoria.INFRA),
    ("GitHub Actions", Stack.Categoria.INFRA),
    ("AWS", Stack.Categoria.INFRA),
    ("Google Cloud", Stack.Categoria.INFRA),
    ("Terraform", Stack.Categoria.INFRA),
    ("RabbitMQ", Stack.Categoria.INFRA),
    ("Celery", Stack.Categoria.INFRA),
    ("GraphQL", Stack.Categoria.OUTRO),
    ("gRPC", Stack.Categoria.OUTRO),
    ("Electron", Stack.Categoria.OUTRO),
]


# O slug automático (`slugify`) descarta símbolo, e "C", "C++" e "C#" caem
# todos em "c" — a segunda dessas a salvar bateria na `unique=True` de
# `Stack.slug`. Só essas três precisam de slug escrito à mão.
SLUGS_MANUAIS = {
    "C": "c-linguagem",
    "C++": "cpp",
    "C#": "csharp",
}


class Command(BaseCommand):
    help = "Cria as stacks conhecidas. Rodar de novo não duplica nada."

    def handle(self, *args, **opcoes):
        criadas = 0
        for nome, categoria in STACKS:
            defaults = {"categoria": categoria}
            if nome in SLUGS_MANUAIS:
                defaults["slug"] = SLUGS_MANUAIS[nome]
            _, nova = Stack.objects.get_or_create(nome=nome, defaults=defaults)
            criadas += int(nova)
        self.stdout.write(self.style.SUCCESS(f"{criadas} stack(s) criada(s); {len(STACKS)} no total."))
