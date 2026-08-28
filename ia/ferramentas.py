"""As ferramentas que o mentor pode acionar durante a conversa.

Poucas de propósito. Cada uma mexe no plano do aluno, então cada uma confere o
dono antes de agir. O modelo recebe ids no contexto e pode citar um id errado,
por alucinação ou porque o aluno colou algo estranho.
"""

from asgiref.sync import sync_to_async
from django.utils import timezone

from projetos.models import Passo

DEFINICOES = [
    {
        "name": "concluir_passo",
        "description": (
            "Marca um passo como concluído. Use apenas quando o aluno demonstrar "
            "que cumpriu os critérios de aceite. Não use só porque ele afirmou "
            "que terminou."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "passo_id": {"type": "integer"},
                "justificativa": {
                    "type": "string",
                    "description": "Que evidência mostrou que os critérios foram cumpridos.",
                },
            },
            "required": ["passo_id", "justificativa"],
            "additionalProperties": False,
        },
    },
    {
        "name": "quebrar_passo",
        "description": (
            "Divide um passo em passos menores quando o aluno travou. Use isto "
            "em vez de entregar a solução."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "passo_id": {"type": "integer"},
                "motivo": {"type": "string"},
                "novos_passos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "titulo": {"type": "string"},
                            "o_que_fazer": {"type": "string"},
                            "como_fazer": {"type": "string"},
                            "teoria": {"type": "string"},
                            "criterios_aceite": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["titulo", "o_que_fazer", "como_fazer", "teoria"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["passo_id", "motivo", "novos_passos"],
            "additionalProperties": False,
        },
    },
]


def _passo_do_usuario(passo_id, usuario):
    return Passo.objects.do_usuario(usuario).filter(pk=passo_id).select_related("etapa").first()


def _concluir_passo(usuario, entrada):
    passo = _passo_do_usuario(entrada.get("passo_id"), usuario)
    if not passo:
        return "Passo não encontrado neste projeto. Confira o id no plano acima."

    passo.status = Passo.Status.CONCLUIDO
    passo.concluido_em = timezone.now()
    passo.concluido_manualmente = False
    passo.save(update_fields=["status", "concluido_em", "concluido_manualmente"])

    # O próximo passo bloqueado da fila abre. Sem isto o aluno concluiria um
    # passo e não teria para onde ir.
    # Import local: `projetos.servicos` importa `ia.motor`, que importa este
    # módulo. No topo, o ciclo se fecha e nenhum dos dois carrega.
    from projetos.servicos import atualizar_status_do_projeto

    atualizar_status_do_projeto(passo.etapa.plano)

    proximo = (
        Passo.objects.do_usuario(usuario)
        .filter(etapa__plano=passo.etapa.plano, status=Passo.Status.BLOQUEADO)
        .first()
    )
    if proximo:
        proximo.status = Passo.Status.DISPONIVEL
        proximo.save(update_fields=["status"])
        return f"Passo {passo.numero} concluído. Liberado: {proximo.numero} {proximo.titulo}."
    return f"Passo {passo.numero} concluído. Era o último da fila."


def _quebrar_passo(usuario, entrada):
    passo = _passo_do_usuario(entrada.get("passo_id"), usuario)
    if not passo:
        return "Passo não encontrado neste projeto."

    novos = entrada.get("novos_passos") or []
    if not novos:
        return "Nenhum passo novo informado, então nada foi alterado."

    etapa = passo.etapa
    # Abre espaço na numeração empurrando quem vem depois, para os subpassos
    # entrarem no lugar certo em vez de irem para o fim da etapa. O empurrão é
    # do tamanho da lista inteira: o passo original continua ocupando a posição
    # dele, então os novos precisam de N lugares livres logo abaixo.
    for posterior in etapa.passos.filter(ordem__gt=passo.ordem).order_by("-ordem"):
        posterior.ordem += len(novos)
        posterior.save(update_fields=["ordem"])

    criados = []
    for i, dados in enumerate(novos):
        criados.append(
            Passo.objects.create(
                etapa=etapa,
                ordem=passo.ordem + i + 1,
                titulo=dados.get("titulo", "")[:150],
                o_que_fazer=dados.get("o_que_fazer", ""),
                como_fazer=dados.get("como_fazer", ""),
                teoria=dados.get("teoria", ""),
                criterios_aceite=dados.get("criterios_aceite", []),
                status=Passo.Status.DISPONIVEL if i == 0 else Passo.Status.BLOQUEADO,
            )
        )

    # O passo original vira o "guarda-chuva" e sai da frente: quem manda agora
    # são os filhos.
    passo.status = Passo.Status.BLOQUEADO
    passo.save(update_fields=["status"])
    return f"{len(criados)} passo(s) criados a partir de {passo.numero}: " + ", ".join(
        p.titulo for p in criados
    )


EXECUTORES = {
    "concluir_passo": _concluir_passo,
    "quebrar_passo": _quebrar_passo,
}


async def executar(nome, entrada, usuario):
    """Roda a ferramenta e devolve o texto do tool_result.

    Erro vira texto de resultado, não exceção: uma ferramenta que estoura no
    meio do laço mataria a resposta inteira, quando o certo é o modelo saber que
    a ação falhou e seguir a conversa.
    """
    executor = EXECUTORES.get(nome)
    if not executor:
        return f"Ferramenta desconhecida: {nome}"
    try:
        return await sync_to_async(executor)(usuario, entrada or {})
    except Exception as erro:  # noqa: BLE001. O modelo precisa do texto, não do traceback
        return f"A ferramenta falhou: {erro}"
