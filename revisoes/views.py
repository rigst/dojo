import asyncio

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from core import sse
from ia.contabilidade import QuotaExcedida
from projetos.models import Passo
from revisoes.models import Submissao
from revisoes.servicos import SubmissaoGrandeDemais, revisar_submissao

# Teto do que dá para colar de uma vez. Medido em caracteres na entrada da
# view; a conversão para tokens (que é o limite de verdade) acontece antes da
# chamada, em revisoes/servicos.py.
MAX_CARACTERES = 60000


@login_required
def submeter(request, pk):
    """Recebe o código e devolve a tela de espera da revisão."""
    passo = get_object_or_404(Passo.objects.do_usuario(request.user), pk=pk)

    if request.method != "POST":
        return redirect("passo_detalhe", pk=passo.pk)

    conteudo = (request.POST.get("conteudo") or "").strip()
    if not conteudo:
        messages.error(request, "Cole o código antes de pedir a revisão.")
        return redirect("passo_detalhe", pk=passo.pk)

    if len(conteudo) > MAX_CARACTERES:
        messages.error(
            request,
            "Isso é grande demais para uma revisão útil. Mande só os arquivos "
            "que este passo pediu.",
        )
        return redirect("passo_detalhe", pk=passo.pk)

    submissao = Submissao.objects.create(passo=passo, usuario=request.user, conteudo=conteudo)
    return redirect("revisao_aguardar", pk=submissao.pk)


@login_required
def aguardar(request, pk):
    submissao = get_object_or_404(Submissao, pk=pk, usuario=request.user)
    if hasattr(submissao, "revisao"):
        return redirect("revisao_detalhe", pk=submissao.revisao.pk)
    return render(request, "revisoes/aguardar.html", {"submissao": submissao})


async def revisar_stream(request, pk):
    usuario = await request.auser()
    if not usuario.is_authenticated:
        raise Http404

    submissao = await sync_to_async(get_object_or_404)(Submissao, pk=pk, usuario=usuario)

    async def eventos():
        tarefa = asyncio.create_task(revisar_submissao(submissao, usuario))
        try:
            while True:
                pronto, _ = await asyncio.wait({tarefa}, timeout=sse.INTERVALO_BATIMENTO)
                if pronto:
                    break
                yield sse.comentario("lendo")

            revisao = tarefa.result()
            yield sse.quadro("fim", {"id": revisao.pk})
        except (QuotaExcedida, SubmissaoGrandeDemais) as erro:
            yield sse.quadro("erro", {"mensagem": str(erro)})
        except asyncio.CancelledError:
            tarefa.cancel()
            raise
        except Exception as erro:  # noqa: BLE001
            tarefa.cancel()
            yield sse.quadro("erro", {"mensagem": f"A revisão falhou: {erro}"})

    return sse.resposta(eventos())


@login_required
def detalhe(request, pk):
    from revisoes.models import Revisao

    revisao = get_object_or_404(Revisao, pk=pk, submissao__usuario=request.user)
    return render(
        request,
        "revisoes/detalhe.html",
        {"revisao": revisao, "passo": revisao.submissao.passo},
    )
