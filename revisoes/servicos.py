from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from ia import motor, preparo
from ia.contabilidade import registrar_uso, verificar_quota
from projetos.models import Passo
from projetos.servicos import atualizar_status_do_projeto
from revisoes.models import Revisao


class SubmissaoGrandeDemais(RuntimeError):
    """O que foi colado não cabe numa revisão útil."""


def salvar_revisao(submissao, avaliada, modelo, uso):
    revisao = Revisao.objects.create(
        submissao=submissao,
        veredito=avaliada.veredito,
        resumo=avaliada.resumo,
        criterios_avaliados=[c.model_dump() for c in avaliada.criterios_avaliados],
        pontos_fortes=avaliada.pontos_fortes,
        problemas=[p.model_dump() for p in avaliada.problemas],
        proximo_passo_sugerido=avaliada.proximo_passo_sugerido,
        modelo=modelo,
        custo_usd=uso.custo_usd,
        request_id=uso.request_id,
    )

    passo = submissao.passo
    if revisao.aprovado:
        passo.status = Passo.Status.CONCLUIDO
        passo.concluido_em = timezone.now()
        passo.concluido_manualmente = False
        passo.save(update_fields=["status", "concluido_em", "concluido_manualmente"])

        # O próximo da fila abre. Só aqui e na ferramenta do chat: é a única
        # regra que faz o plano andar.
        proximo = (
            Passo.objects.filter(etapa__plano=passo.etapa.plano, status=Passo.Status.BLOQUEADO)
            .order_by("etapa__ordem", "ordem")
            .first()
        )
        if proximo:
            proximo.status = Passo.Status.DISPONIVEL
            proximo.save(update_fields=["status"])
    else:
        # Reprovado não volta a "disponível": ficou em revisão e o aluno sabe
        # exatamente o que falta pela lista de critérios.
        passo.status = Passo.Status.EM_REVISAO
        passo.save(update_fields=["status"])

    atualizar_status_do_projeto(passo.etapa.plano)
    return revisao


async def revisar_submissao(submissao, usuario):
    await sync_to_async(verificar_quota)(usuario)
    pedido = await sync_to_async(preparo.para_revisao)(submissao, usuario)

    # O limite de verdade é em tokens, não em caracteres: a view corta o
    # exagero óbvio, e aqui se confere o tamanho real antes de gastar a chamada.
    tokens = await motor.contar_tokens(pedido)
    if tokens > settings.IA_MAX_TOKENS_SUBMISSAO:
        raise SubmissaoGrandeDemais(
            f"São {tokens} tokens, mais do que cabe numa revisão útil. "
            "Mande só os arquivos que este passo pediu."
        )

    avaliada, uso = await motor.revisar(pedido)
    revisao = await sync_to_async(salvar_revisao)(submissao, avaliada, motor.modelo_em_uso(), uso)
    await sync_to_async(registrar_uso)(usuario, uso)
    return revisao
