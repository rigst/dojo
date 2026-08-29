"""Motor de verdade: fala com a Claude API.

Não toca o banco. Recebe um `ia.preparo.Pedido` com o system e as mensagens já
montados. Duas formas de chamada, escolhidas pelo que cada tarefa precisa:

- plano e revisão usam `messages.parse`, que valida a resposta contra o schema
  Pydantic e devolve o objeto pronto. Não streamam: o resultado só serve inteiro;
- a conversa usa `messages.stream`, porque quem lê uma explicação longa precisa
  ver o texto aparecer, mais um laço manual por causa das ferramentas.
"""

import anthropic
from django.conf import settings

from ia import ferramentas
from ia.contabilidade import Uso
from ia.schemas import BriefingGerado, PassoSeguinteGerado, PlanoInicialGerado, RevisaoCodigo

# Plano e revisão têm resposta estruturada e limitada; o teto alto do settings é
# para a conversa, que streama.
MAX_TOKENS_ESTRUTURADO = 16000

# Teto de rodadas do laço de ferramentas. Sem ele, um par modelo/ferramenta em
# desacordo fica chamando a mesma ferramenta até o orçamento do mês acabar.
MAX_RODADAS = 6


def _cliente(pedido):
    if not pedido.chave_api:
        raise RuntimeError(
            "Nenhuma chave de API configurada. Defina ANTHROPIC_API_KEY no .env "
            "ou cadastre a sua na página da conta."
        )
    return anthropic.AsyncAnthropic(api_key=pedido.chave_api)


async def _estruturado(pedido, formato):
    resposta = await _cliente(pedido).messages.parse(
        model=settings.IA_MODELO,
        max_tokens=MAX_TOKENS_ESTRUTURADO,
        system=pedido.sistema,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        output_format=formato,
        messages=pedido.mensagens,
    )
    return resposta.parsed_output, Uso.da_resposta(resposta, settings.IA_MODELO)


async def contar_tokens(pedido):
    """Quantos tokens o pedido ocupa antes de ser enviado.

    Vale a viagem extra: ela é barata e evita mandar um arquivo gigante que
    voltaria como erro de contexto depois de já ter sido cobrado.
    """
    contagem = await _cliente(pedido).messages.count_tokens(
        model=settings.IA_MODELO,
        system=pedido.sistema,
        messages=pedido.mensagens,
    )
    return contagem.input_tokens


async def gerar_briefing(pedido):
    return await _estruturado(pedido, BriefingGerado)


async def gerar_plano(pedido):
    return await _estruturado(pedido, PlanoInicialGerado)


async def gerar_proximo_passo(pedido):
    return await _estruturado(pedido, PassoSeguinteGerado)


async def revisar(pedido):
    return await _estruturado(pedido, RevisaoCodigo)


async def conversar(pedido, usuario):
    """Gera os eventos da resposta do mentor.

    Eventos: {"tipo": "delta"|"ferramenta"|"fim", ...}. O laço de ferramentas é
    manual porque o tool runner do SDK não entrega os deltas de texto do jeito
    que o SSE precisa, e aqui o texto aparecendo é metade da experiência.
    """
    cliente = _cliente(pedido)
    mensagens = list(pedido.mensagens)
    uso_total = Uso(modelo=settings.IA_MODELO, rodadas=0)
    texto_final = []

    for _ in range(MAX_RODADAS):
        async with cliente.messages.stream(
            model=settings.IA_MODELO,
            max_tokens=settings.IA_MAX_TOKENS,
            system=pedido.sistema,
            thinking={"type": "adaptive", "display": "summarized"},
            tools=ferramentas.DEFINICOES,
            messages=mensagens,
        ) as stream:
            async for texto in stream.text_stream:
                texto_final.append(texto)
                yield {"tipo": "delta", "texto": texto}

            resposta = await stream.get_final_message()

        uso_total = uso_total + Uso.da_resposta(resposta, settings.IA_MODELO)

        if resposta.stop_reason != "tool_use":
            yield {
                "tipo": "fim",
                "texto": "".join(texto_final),
                "uso": uso_total,
                "stop_reason": resposta.stop_reason,
            }
            return

        mensagens.append({"role": "assistant", "content": resposta.content})

        # Todos os resultados voltam numa única mensagem: separá-los em várias
        # ensina o modelo a parar de pedir ferramentas em paralelo.
        resultados = []
        for bloco in resposta.content:
            if bloco.type != "tool_use":
                continue
            yield {"tipo": "ferramenta", "nome": bloco.name}
            saida = await ferramentas.executar(bloco.name, bloco.input, usuario)
            resultados.append({"type": "tool_result", "tool_use_id": bloco.id, "content": saida})
        mensagens.append({"role": "user", "content": resultados})

    yield {
        "tipo": "fim",
        "texto": "".join(texto_final),
        "uso": uso_total,
        "stop_reason": "limite_de_rodadas",
    }
