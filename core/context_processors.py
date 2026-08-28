from django.conf import settings

# A marca vive num só lugar: trocar o nome do app é trocar esta constante.
MARCA = "Dojo"
LEMA = "onde se pratica"


# Quantos projetos cabem na lateral antes de ela virar rolagem.
LIMITE_LATERAL = 6


def navegacao(request):
    """Os projetos do usuário, para a lateral.

    Uma consulta por página, de poucas linhas: é o preço de poder pular de um
    projeto para outro sem voltar ao painel. Sem isto, a lateral tem dois links
    e a navegação de verdade acontece toda pelo botão de voltar.
    """
    if not request.user.is_authenticated:
        return {}

    from projetos.models import Projeto

    return {
        "projetos_lateral": Projeto.objects.do_usuario(request.user).ativos()[:LIMITE_LATERAL],
    }


def marca(request):
    return {
        "marca": MARCA,
        "lema": LEMA,
        # A tela de entrada anuncia o prazo do visitante; lendo do settings, o
        # texto não passa a mentir quando alguém muda a variável.
        "visitante_ttl": settings.VISITANTE_TTL_HORAS,
        # O template do chat precisa saber se há chave configurada para avisar
        # antes de a pessoa escrever uma pergunta que não vai a lugar nenhum.
        "ia_disponivel": bool(settings.ANTHROPIC_API_KEY) or settings.IA_BACKEND == "fake",
    }
