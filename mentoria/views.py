import asyncio

from asgiref.sync import sync_to_async
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render

from core import sse
from core.mixins import obter_do_usuario
from ia import motor, preparo
from ia.contabilidade import QuotaExcedida, registrar_uso, verificar_quota
from mentoria import servicos
from projetos.models import Passo, Projeto

# Teto do que cabe numa pergunta. Não é sobre custo. É sobre o aluno colar um
# arquivo inteiro no chat, que é o que a tela de revisão existe para receber.
MAX_PERGUNTA = 6000


@login_required
def chat(request, pk):
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    conversa = servicos.obter_conversa(projeto)
    return render(
        request,
        "mentoria/chat.html",
        {"projeto": projeto, "mensagens": conversa.mensagens.all()},
    )


async def stream(request, pk):
    """Responde à pergunta do aluno, token a token.

    A view é `async` de ponta a ponta: cada conversa aberta é uma conexão
    parada esperando o modelo, e em WSGI isso prenderia um worker inteiro por
    conversa.
    """
    usuario = await request.auser()
    if not usuario.is_authenticated:
        raise Http404

    pergunta = (request.GET.get("pergunta") or "").strip()[:MAX_PERGUNTA]
    if not pergunta:
        return HttpResponseBadRequest("pergunta vazia")

    projeto = await sync_to_async(get_object_or_404)(Projeto, pk=pk, usuario=usuario)
    conversa = await sync_to_async(servicos.obter_conversa)(projeto)

    passo = None
    passo_id = request.GET.get("passo")
    if passo_id:
        passo = await sync_to_async(
            lambda: Passo.objects.do_usuario(usuario).filter(pk=passo_id).first()
        )()

    async def eventos():
        try:
            await sync_to_async(verificar_quota)(usuario)
        except QuotaExcedida as erro:
            yield sse.quadro("erro", {"mensagem": str(erro)})
            return

        await sync_to_async(servicos.registrar_pergunta)(conversa, pergunta, passo)
        historico = await sync_to_async(servicos.historico_para_api)(conversa)
        pedido = await sync_to_async(preparo.para_conversa)(projeto, passo, historico, usuario)

        partes = []
        uso = None
        stop_reason = ""
        erro_texto = ""

        try:
            async for evento in motor.conversar(pedido, usuario):
                if evento["tipo"] == "delta":
                    partes.append(evento["texto"])
                    yield sse.quadro("delta", {"texto": evento["texto"]})
                elif evento["tipo"] == "ferramenta":
                    yield sse.quadro("ferramenta", {"nome": evento["nome"]})
                elif evento["tipo"] == "fim":
                    uso = evento["uso"]
                    stop_reason = evento.get("stop_reason", "")
        except asyncio.CancelledError:
            # A aba fechou no meio da resposta. O que já veio foi gerado e
            # cobrado: gravar o parcial é o que impede o gasto invisível.
            await sync_to_async(servicos.registrar_resposta)(
                conversa, "".join(partes), passo, uso, stop_reason, erro="cancelado"
            )
            raise
        except Exception as falha:  # noqa: BLE001
            erro_texto = str(falha)

        mensagem = await sync_to_async(servicos.registrar_resposta)(
            conversa, "".join(partes), passo, uso, stop_reason, erro_texto
        )
        if uso is not None:
            await sync_to_async(registrar_uso)(usuario, uso)

        if erro_texto:
            yield sse.quadro("erro", {"mensagem": erro_texto})
        else:
            yield sse.quadro(
                "fim",
                {"id": mensagem.pk, "custo": str(mensagem.custo_usd)},
            )

    return sse.resposta(eventos())
