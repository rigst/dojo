"""Operações de projeto que envolvem o mentor."""

from asgiref.sync import sync_to_async
from django.db import transaction

from ia import motor, preparo
from ia.contabilidade import registrar_uso, verificar_quota
from projetos.models import Etapa, Passo, Plano


@transaction.atomic
def salvar_plano(projeto, gerado, modelo):
    """Grava uma versão nova do plano e a torna a ativa.

    A anterior não é apagada: replanejar é normal quando o aluno trava, e o
    histórico é o registro de como o entendimento do projeto mudou.
    """
    anterior = projeto.planos.filter(ativo=True).first()
    if anterior:
        anterior.ativo = False
        anterior.save(update_fields=["ativo"])

    versao = (projeto.planos.order_by("-versao").values_list("versao", flat=True).first() or 0) + 1
    plano = Plano.objects.create(
        projeto=projeto, versao=versao, resumo=gerado.resumo, modelo=modelo, ativo=True
    )

    primeiro = True
    for i, etapa_gerada in enumerate(gerado.etapas, start=1):
        etapa = Etapa.objects.create(
            plano=plano, ordem=i, titulo=etapa_gerada.titulo, objetivo=etapa_gerada.objetivo
        )
        for j, passo_gerado in enumerate(etapa_gerada.passos, start=1):
            Passo.objects.create(
                etapa=etapa,
                ordem=j,
                titulo=passo_gerado.titulo,
                o_que_fazer=passo_gerado.o_que_fazer,
                como_fazer=passo_gerado.como_fazer,
                teoria=passo_gerado.teoria,
                criterios_aceite=passo_gerado.criterios_aceite,
                armadilhas=passo_gerado.armadilhas,
                recursos=[r.model_dump() for r in passo_gerado.recursos],
                estimativa_min=passo_gerado.estimativa_min,
                # Só o primeiro passo nasce aberto: a fila é o que faz o app ser
                # passo a passo em vez de uma lista de tarefas.
                status=Passo.Status.DISPONIVEL if primeiro else Passo.Status.BLOQUEADO,
            )
            primeiro = False

    projeto.status = projeto.Status.EM_ANDAMENTO
    projeto.save(update_fields=["status", "atualizado_em"])
    return plano


def normalizar_fila(plano):
    """Arruma o plano depois de uma edição manual.

    Duas coisas que só um humano quebra: numeração com buracos (removeu o passo
    2 e sobraram 1, 3, 4) e uma fila sem nenhum passo aberto (removeu justo o
    que estava em curso). Sem isto, o app fica sem "passo da vez" e o botão
    principal do projeto some.
    """
    for etapa in plano.etapas.prefetch_related("passos"):
        for i, passo in enumerate(etapa.passos.all(), start=1):
            if passo.ordem != i:
                passo.ordem = i
                passo.save(update_fields=["ordem"])

    passos = list(Passo.objects.filter(etapa__plano=plano))
    em_curso = [
        p
        for p in passos
        if p.status in (Passo.Status.DISPONIVEL, Passo.Status.EM_ANDAMENTO, Passo.Status.EM_REVISAO)
    ]
    if not em_curso:
        seguinte = next((p for p in passos if p.status != Passo.Status.CONCLUIDO), None)
        if seguinte:
            seguinte.status = Passo.Status.DISPONIVEL
            seguinte.save(update_fields=["status"])

    atualizar_status_do_projeto(plano)


def atualizar_status_do_projeto(plano):
    """Fecha ou reabre o projeto conforme a fila do plano ativo.

    Existe como função e não como três linhas repetidas nas views porque há
    quatro caminhos que concluem um passo. Revisão aprovada, ferramenta do
    chat, conclusão manual e edição do plano, e um deles esquecer de fechar
    o projeto deixaria a tela dizendo "em andamento" para sempre.
    """
    if not plano or not plano.ativo:
        return

    projeto = plano.projeto
    passos = Passo.objects.filter(etapa__plano=plano)
    total = passos.count()
    if not total:
        return

    concluidos = passos.filter(status=Passo.Status.CONCLUIDO).count()
    novo_status = (
        projeto.Status.CONCLUIDO if concluidos == total else projeto.Status.EM_ANDAMENTO
    )
    if projeto.status != novo_status and projeto.status != projeto.Status.ARQUIVADO:
        projeto.status = novo_status
        projeto.save(update_fields=["status", "atualizado_em"])


async def gerar_briefing(projeto, usuario):
    """As perguntas que o mentor faz antes de planejar.

    Chamada curta e barata, e o que ela evita é caro: plano genérico feito em
    cima de um objetivo de duas linhas. Roda antes da geração, na mesma tela.
    """
    await sync_to_async(verificar_quota)(usuario)
    pedido = await sync_to_async(preparo.para_briefing)(projeto, usuario)
    briefing, uso = await motor.gerar_briefing(pedido)
    await sync_to_async(registrar_uso)(usuario, uso)
    return briefing, uso


async def gerar_e_salvar_plano(projeto, usuario, respostas_briefing=""):
    await sync_to_async(verificar_quota)(usuario)
    pedido = await sync_to_async(preparo.para_plano)(projeto, usuario, respostas_briefing)
    gerado, uso = await motor.gerar_plano(pedido)
    plano = await sync_to_async(salvar_plano)(projeto, gerado, motor.modelo_em_uso())
    await sync_to_async(registrar_uso)(usuario, uso)
    return plano, uso
