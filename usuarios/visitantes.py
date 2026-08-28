"""A conta de visitante: entrar sem cadastro e sumir sozinho depois.

Serve para quem quer ver o Dojo funcionando antes de decidir se cria conta. É
uma conta de verdade, com projetos, plano e chat de verdade, e com duas
diferenças que a tornam segura de oferecer a qualquer um:

  · teto de gasto próprio, menor que o da conta comum, porque quem paga a API é
    quem hospeda o app e a conta de visitante é anônima;
  · prazo de validade. Passado o TTL, ela é apagada com tudo o que produziu.

A limpeza roda em dois momentos: oportunisticamente, quando um novo visitante
entra, e pelo comando `manage.py limpar_visitantes`, que é o que se põe no cron.
Sem fila de tarefas: o app não tem uma, e criar uma só para isto seria trocar um
problema pequeno por um serviço a mais para manter de pé.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def _chave_limite(ip):
    return f"visitante:tentativas:{ip or 'desconhecido'}"


def excedeu_limite_de_criacao(ip):
    """Trava por IP.

    Sem ela, um laço de requisições cria contas até encher a tabela de usuários
    e torrar a cota do provedor, e cada conta nova vem com cota nova.
    """
    return int(cache.get(_chave_limite(ip), 0)) >= settings.VISITANTE_LIMITE_POR_JANELA


def registrar_tentativa(ip):
    chave = _chave_limite(ip)
    if cache.add(chave, 1, timeout=settings.VISITANTE_JANELA_SEGUNDOS):
        return
    try:
        cache.incr(chave)
    except ValueError:
        # A chave expirou entre o add e o incr.
        cache.set(chave, 1, timeout=settings.VISITANTE_JANELA_SEGUNDOS)


@transaction.atomic
def criar_visitante():
    """Cria a conta descartável, já com um projeto dentro.

    Sem senha utilizável: só se entra pelo botão. O projeto de exemplo vem
    junto porque um painel vazio é a pior primeira tela possível para quem
    entrou justamente para ver o app funcionando. Ele é escrito à mão, então
    aparece na hora e não gasta um centavo de API.

    O import é local para não amarrar `usuarios` a `projetos` na importação: a
    conta de visitante é um conceito de usuário, e o exemplo é um detalhe de
    boas-vindas.
    """
    from projetos.exemplo import criar_projeto_exemplo

    usuario = get_user_model().objects.create_user(
        username=f"visitante-{secrets.token_hex(4)}",
        password=None,
        eh_visitante=True,
    )
    usuario.set_unusable_password()
    usuario.save(update_fields=["password"])

    criar_projeto_exemplo(usuario)
    return usuario


def limpar_expirados():
    """Apaga os visitantes que passaram do prazo.

    O `delete()` leva junto projetos, planos, passos, conversas, submissões e o
    registro de uso, tudo por cascata das FKs. Não há nada guardado fora dessa
    árvore, e é por isso que a limpeza cabe em uma linha.
    """
    limite = timezone.now() - timedelta(hours=settings.VISITANTE_TTL_HORAS)
    expirados = get_user_model().objects.filter(eh_visitante=True, date_joined__lt=limite)

    total = expirados.count()
    if total:
        expirados.delete()
        logger.info("Visitantes expirados removidos", extra={"total": total})
    return total
