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

# Tetos do anexo, separados do teto de caracteres acima: aquele é sobre o
# conteúdo já lido, estes são sobre o que aceitar ler antes de sequer tentar.
# Sem eles, um arquivo de 50MB (uma imagem batizada de ".py", por exemplo)
# travaria a requisição decodificando bytes que nunca iam virar texto.
MAX_ARQUIVOS = 6
MAX_BYTES_POR_ARQUIVO = 300_000


def _texto_do_arquivo(arquivo):
    """O conteúdo do arquivo enviado, ou None se ele não serve para revisão.

    Só texto: um binário decodificado errado não vira erro aqui, vira lixo que
    o mentor tentaria revisar como se fosse código.
    """
    if arquivo.size > MAX_BYTES_POR_ARQUIVO:
        return None
    try:
        return arquivo.read().decode("utf-8")
    except UnicodeDecodeError:
        return None


@login_required
def submeter(request, pk):
    """Recebe o código (colado, anexado, ou os dois) e devolve a tela de
    espera da revisão."""
    passo = get_object_or_404(Passo.objects.do_usuario(request.user), pk=pk)

    if request.method != "POST":
        return redirect("passo_detalhe", pk=passo.pk)

    arquivos = request.FILES.getlist("arquivos")
    if len(arquivos) > MAX_ARQUIVOS:
        messages.error(request, f"São muitos arquivos de uma vez. Envie até {MAX_ARQUIVOS}.")
        return redirect("passo_detalhe", pk=passo.pk)

    partes = []
    texto_colado = (request.POST.get("conteudo") or "").strip()
    if texto_colado:
        partes.append(texto_colado)

    for arquivo in arquivos:
        texto = _texto_do_arquivo(arquivo)
        if texto is None:
            messages.error(
                request,
                f"“{arquivo.name}” não deu para ler como texto (grande demais ou não é código).",
            )
            return redirect("passo_detalhe", pk=passo.pk)
        # O nome do arquivo faz parte da revisão: é o que diz ao mentor qual
        # arquivo é qual quando vem mais de um.
        partes.append(f"--- arquivo: {arquivo.name} ---\n{texto}")

    conteudo = "\n\n".join(partes).strip()

    if not conteudo:
        messages.error(request, "Cole o código ou anexe um arquivo antes de pedir a revisão.")
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
