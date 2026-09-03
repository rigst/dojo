import asyncio

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core import sse
from core.mixins import obter_do_usuario
from ia.contabilidade import QuotaExcedida
from mentoria import servicos as servicos_mentoria
from projetos.forms import EtapaForm, PassoForm, ProjetoForm
from projetos.models import Etapa, Passo, Projeto
from projetos.servicos import (
    atualizar_status_do_projeto,
    etapa_pendente,
    gerar_briefing,
    gerar_e_salvar_plano,
    gerar_e_salvar_proximo_passo,
    normalizar_fila,
    passo_atual,
)

# Referências fortes às tasks de fundo, para o coletor não recolher uma no
# meio da execução. Ver o comentário no create_task correspondente.
_TAREFAS_EM_VOO: set[asyncio.Task] = set()


@login_required
def lista(request):
    arquivados = request.GET.get("arquivados") == "1"
    consulta = Projeto.objects.do_usuario(request.user).prefetch_related("stacks")
    consulta = (
        consulta.filter(status=Projeto.Status.ARQUIVADO) if arquivados else consulta.ativos()
    )
    projetos = list(consulta)

    # "Onde eu parei": o passo aberto do projeto mexido por último. É a primeira
    # pergunta de quem volta depois de dois dias, e sem isto a resposta exige
    # três cliques até achar de novo a linha destacada no plano.
    retomar = None
    if projetos:
        retomar = (
            Passo.objects.do_usuario(request.user)
            .filter(
                etapa__plano__ativo=True,
                etapa__plano__projeto=projetos[0],
                status__in=[Passo.Status.DISPONIVEL, Passo.Status.EM_ANDAMENTO, Passo.Status.EM_REVISAO],
            )
            .select_related("etapa__plano__projeto")
            .first()
        )

    return render(
        request,
        "projetos/lista.html",
        {
            "projetos": projetos,
            "retomar": None if arquivados else retomar,
            "arquivados": arquivados,
            "tem_arquivados": Projeto.objects.do_usuario(request.user)
            .filter(status=Projeto.Status.ARQUIVADO)
            .exists(),
        },
    )


@login_required
def novo(request):
    formulario = ProjetoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        projeto = formulario.save(commit=False)
        projeto.usuario = request.user
        # Sem campo de título na criação (ver _form_projeto.html), fica um
        # nome provisório até o mentor gerar o plano e escolher o de verdade.
        projeto.titulo = projeto.titulo.strip() or "Novo projeto"
        projeto.save()
        formulario.save_m2m()
        return redirect("projeto_planejar", pk=projeto.pk)

    return render(request, "projetos/novo.html", {"formulario": formulario})


@login_required
def editar(request, pk):
    """Corrigir o projeto depois de criado.

    Objetivo mal escrito é a causa mais comum de plano ruim, e até aqui não
    havia como consertar: o texto que gerou o plano ficava congelado para
    sempre. Editar não regera nada sozinho. Quem decide refazer o plano é você.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    formulario = ProjetoForm(request.POST or None, instance=projeto)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Projeto atualizado.")
        return redirect("projeto_detalhe", pk=projeto.pk)

    return render(request, "projetos/editar.html", {"formulario": formulario, "projeto": projeto})


@login_required
def arquivar(request, pk):
    """Tira o projeto do painel sem apagar nada.

    Abandonar um projeto é normal, o que não pode é ele ficar cobrando espaço
    na tela para sempre. Arquivar é reversível; excluir é que não é.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    if request.method == "POST":
        arquivado = projeto.status == Projeto.Status.ARQUIVADO
        if arquivado:
            # Ao desarquivar, o status volta a ser calculado pela fila.
            projeto.status = Projeto.Status.EM_ANDAMENTO
            projeto.save(update_fields=["status", "atualizado_em"])
            atualizar_status_do_projeto(projeto.plano_ativo)
            messages.success(request, "Projeto de volta ao painel.")
        else:
            projeto.status = Projeto.Status.ARQUIVADO
            projeto.save(update_fields=["status", "atualizado_em"])
            messages.success(request, "Projeto arquivado. Ele continua na aba de arquivados.")
            return redirect("painel")

    return redirect("projeto_detalhe", pk=projeto.pk)


@login_required
def excluir(request, pk):
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)

    if request.method == "POST":
        if request.POST.get("confirmacao") != projeto.titulo:
            messages.error(request, "Digite o título do projeto para confirmar.")
            return redirect("projeto_excluir", pk=projeto.pk)

        # Cascata: planos, etapas, passos, conversa e submissões vão junto.
        projeto.delete()
        messages.success(request, "Projeto excluído.")
        return redirect("painel")

    return render(request, "projetos/excluir.html", {"projeto": projeto})


@login_required
def detalhe(request, pk):
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    plano = projeto.plano_ativo
    if not plano:
        # Sem plano: pode estar gerando o inicial ou re-planejando
        return redirect("projeto_planejar", pk=projeto.pk)

    feitos, total, pct = projeto.progresso()
    etapas = plano.etapas.prefetch_related("passos")

    # O passo em aberto. É ele que vira o botão principal da tela: sem isso, a
    # ação central do app fica escondida numa linha de lista, e quem chega aqui
    # depois de gerar o plano não sabe por onde começar.
    atual = passo_atual(plano)

    # Sem passo aberto mas o plano ainda não acabou: o mentor está gerando o
    # próximo (ou precisa gerar), e a tela certa é a de espera, não esta com o
    # botão principal faltando.
    if atual is None and (projeto.gerando or etapa_pendente(plano)):
        return redirect("projeto_passo_gerando", pk=projeto.pk)

    return render(
        request,
        "projetos/detalhe.html",
        {"projeto": projeto, "plano": plano, "etapas": etapas,
         "feitos": feitos, "total": total, "pct": pct, "atual": atual,
         "concluido": total > 0 and feitos == total,
         # Só as duas últimas: a lista de ações cresceria sem fim num projeto
         # replanejado muitas vezes, e quem quer a v1 de dez versões atrás
         # está fazendo arqueologia, não navegando.
         "versoes_anteriores": projeto.planos.filter(ativo=False)[:2]},
    )


@login_required
def planejar(request, pk):
    """Tela que dispara a geração do plano. O trabalho acontece no stream.

    Serve os dois casos, o primeiro plano e o replanejamento, e é por isso
    que o plano atual vai no contexto: refazer descarta o roteiro em curso, e a
    tela precisa dizer isso antes, não depois.

    Se `projeto.gerando` estiver marcado, uma geração já está em curso (ou
    ficou em curso até a última vez que a aba desta pessoa esteve aberta): a
    tela pula direto para a espera e retoma sozinha, em vez de perguntar de
    novo o que já foi respondido.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    return render(
        request,
        "projetos/planejar.html",
        {
            "projeto": projeto,
            "plano_atual": projeto.plano_ativo,
            "gerando": projeto.gerando,
            "briefing_pendente": projeto.briefing_pendente,
            "erro_geracao": projeto.erro_geracao,
        },
    )


async def briefing_stream(request, pk):
    """Entrega as perguntas do mentor para a tela de planejamento.

    Stream, e não uma view comum, pelo mesmo motivo do plano: a chamada leva
    alguns segundos e a tela precisa mostrar que está esperando, não travar.
    """
    usuario = await request.auser()
    if not usuario.is_authenticated:
        raise Http404

    projeto = await sync_to_async(get_object_or_404)(Projeto, pk=pk, usuario=usuario)

    async def eventos():
        tarefa = asyncio.create_task(gerar_briefing(projeto, usuario))
        try:
            while True:
                pronto, _ = await asyncio.wait({tarefa}, timeout=sse.INTERVALO_BATIMENTO)
                if pronto:
                    break
                yield sse.comentario("perguntando")

            briefing, _uso = tarefa.result()
            yield sse.quadro(
                "perguntas",
                {"perguntas": [p.model_dump() for p in briefing.perguntas]},
            )
        except asyncio.CancelledError:
            tarefa.cancel()
            raise
        except Exception as erro:
            tarefa.cancel()
            # O briefing é um extra: se falhar, a tela cai no campo livre e a
            # pessoa segue para o plano. Não vale interromper o fluxo por ele.
            yield sse.quadro("erro", {"mensagem": str(erro)})

    return sse.resposta(eventos())


async def planejar_stream(request, pk):
    """Gera o plano e informa o progresso enquanto isso.

    A geração leva um a dois minutos. Sem stream, a página ficaria branca todo
    esse tempo e o usuário recarregaria. Disparando uma segunda geração paga.
    O batimento também é o que mantém o proxy de pé (ver core/sse.py).
    """
    usuario = await request.auser()
    if not usuario.is_authenticated:
        raise Http404

    projeto = await sync_to_async(get_object_or_404)(Projeto, pk=pk, usuario=usuario)
    briefing = request.GET.get("briefing", "")[:8000]

    async def eventos():
        tarefa = asyncio.create_task(gerar_e_salvar_plano(projeto, usuario, briefing))
        try:
            while True:
                pronto, _ = await asyncio.wait({tarefa}, timeout=sse.INTERVALO_BATIMENTO)
                if pronto:
                    break
                yield sse.comentario("pensando")

            _plano, uso = tarefa.result()
            yield sse.quadro(
                "fim",
                {"url": projeto.get_absolute_url(), "custo": str(uso.custo_usd)},
            )
        except QuotaExcedida as erro:
            yield sse.quadro("erro", {"mensagem": str(erro)})
        except asyncio.CancelledError:
            # A aba fechou. Cancelar a tarefa evita gravar um plano para uma
            # tela que não existe mais.
            tarefa.cancel()
            raise
        except Exception as erro:
            tarefa.cancel()
            yield sse.quadro("erro", {"mensagem": f"Não deu para gerar o plano: {erro}"})

    return sse.resposta(eventos())


@login_required
def passo_gerando(request, pk):
    """Tela de espera enquanto o mentor prepara o próximo passo.

    Mesmo papel que `planejar` tem para o plano: se `projeto.gerando` estiver
    marcado (inclusive depois de um F5), a tela retoma sozinha em vez de
    mandar a pessoa de volta para o projeto sem passo nenhum aberto.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    plano = projeto.plano_ativo

    # Nada para gerar: nem está gerando, nem sobrou etapa pendente. Só chega
    # aqui por um link direto ou um F5 tardio; o lugar certo é o projeto.
    if not projeto.gerando and not etapa_pendente(plano):
        return redirect("projeto_detalhe", pk=projeto.pk)

    return render(request, "projetos/passo_gerando.html", {"projeto": projeto})


async def passo_pre_gerar(request, pk):
    """Dispara a geração do próximo passo em background quando o aluno abre um passo.

    Retorna 204 imediatamente; a geração corre como task asyncio independente.
    Só dispara se não houver geração em curso e se ainda existir etapa pendente
    sem passo bloqueado já materializado esperando.
    """
    if request.method != "POST":
        return HttpResponse(status=405)
    usuario = await request.auser()
    if not usuario.is_authenticated:
        return HttpResponse(status=204)

    projeto = await sync_to_async(get_object_or_404)(Projeto, pk=pk, usuario=usuario)

    if projeto.gerando:
        return HttpResponse(status=204)

    plano = await sync_to_async(lambda: projeto.plano_ativo)()
    if not plano:
        return HttpResponse(status=204)

    tem_bloqueado = await sync_to_async(
        lambda: Passo.objects.filter(etapa__plano=plano, status=Passo.Status.BLOQUEADO).exists()
    )()
    if tem_bloqueado:
        return HttpResponse(status=204)

    etapa = await sync_to_async(etapa_pendente)(plano)
    if not etapa:
        return HttpResponse(status=204)

    # O loop de eventos guarda só referência fraca à task: sem manter uma
    # forte, o coletor pode recolhê-la no meio da geração e o passo some
    # sem erro nenhum. Diferente dos outros create_task deste arquivo, que
    # são aguardados dentro do gerador SSE, este é fire-and-forget — a view
    # responde 204 na hora. O descarte no callback evita o vazamento.
    tarefa = asyncio.create_task(gerar_e_salvar_proximo_passo(projeto, usuario))
    _TAREFAS_EM_VOO.add(tarefa)
    tarefa.add_done_callback(_TAREFAS_EM_VOO.discard)
    return HttpResponse(status=204)


async def passo_gerar_stream(request, pk):
    """Gera o próximo passo e informa o progresso, no mesmo padrão do plano."""
    usuario = await request.auser()
    if not usuario.is_authenticated:
        raise Http404

    projeto = await sync_to_async(get_object_or_404)(Projeto, pk=pk, usuario=usuario)

    async def eventos():
        tarefa = asyncio.create_task(gerar_e_salvar_proximo_passo(projeto, usuario))
        try:
            while True:
                pronto, _ = await asyncio.wait({tarefa}, timeout=sse.INTERVALO_BATIMENTO)
                if pronto:
                    break
                yield sse.comentario("pensando")

            passo, _uso = tarefa.result()
            if passo is None:
                # A etapa pendente foi fechada por outra requisição enquanto
                # esta rodava (duas abas, por exemplo): nada a abrir, volta
                # para o projeto, que decide o que mostrar a partir daí.
                url = await sync_to_async(lambda: projeto.get_absolute_url())()
            else:
                url = passo.get_absolute_url()
            yield sse.quadro("fim", {"url": url})
        except QuotaExcedida as erro:
            yield sse.quadro("erro", {"mensagem": str(erro)})
        except asyncio.CancelledError:
            tarefa.cancel()
            raise
        except Exception as erro:
            tarefa.cancel()
            yield sse.quadro("erro", {"mensagem": f"Não deu para preparar o próximo passo: {erro}"})

    return sse.resposta(eventos())


@login_required
def plano_versao(request, pk, versao):
    """Um plano antigo, só leitura.

    Replanejar guarda a versão anterior desde sempre, mas até aqui ela não
    aparecia em lugar nenhum. O histórico existia só no banco. Serve para
    comparar o que mudou de entendimento entre uma versão e outra.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    plano = get_object_or_404(projeto.planos, versao=versao)
    return render(
        request,
        "projetos/plano_versao.html",
        {
            "projeto": projeto,
            "plano": plano,
            "etapas": plano.etapas.prefetch_related("passos"),
        },
    )


@login_required
def passo_revisoes(request, pk):
    """Todas as revisões de um passo, da mais recente para a mais antiga."""
    passo = get_object_or_404(
        Passo.objects.do_usuario(request.user).select_related("etapa__plano__projeto"), pk=pk
    )
    paginas = Paginator(passo.submissoes.select_related("revisao"), 10)
    return render(
        request,
        "projetos/passo_revisoes.html",
        {
            "passo": passo,
            "projeto": passo.projeto,
            "pagina": paginas.get_page(request.GET.get("p")),
        },
    )


# ---------------------------------------------------------------------------
# Edição manual do plano
#
# O plano sai de um modelo de linguagem, e modelo de linguagem erra: passo
# grande demais, critério vago, etapa fora de ordem. Até aqui a única saída era
# refazer tudo e perder o progresso. Estas views deixam corrigir o que está
# errado sem jogar fora o que está certo.
# ---------------------------------------------------------------------------


def _plano_editavel(usuario, projeto_pk):
    """Só o plano ativo é editável: versão antiga é registro, não rascunho."""
    projeto = obter_do_usuario(Projeto, usuario, pk=projeto_pk)
    plano = projeto.plano_ativo
    if not plano:
        raise Http404
    return projeto, plano


@login_required
def plano_editar(request, pk):
    projeto, plano = _plano_editavel(request.user, pk)
    return render(
        request,
        "projetos/plano_editar.html",
        {"projeto": projeto, "plano": plano, "etapas": plano.etapas.prefetch_related("passos")},
    )


@login_required
def etapa_editar(request, pk):
    etapa = get_object_or_404(
        Etapa.objects.filter(plano__projeto__usuario=request.user, plano__ativo=True), pk=pk
    )
    formulario = EtapaForm(request.POST or None, instance=etapa)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Etapa atualizada.")
    return redirect("plano_editar", pk=etapa.plano.projeto_id)


@login_required
def passo_editar(request, pk):
    passo = get_object_or_404(
        Passo.objects.do_usuario(request.user).select_related("etapa__plano__projeto"), pk=pk
    )
    formulario = PassoForm(request.POST or None, instance=passo)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Passo atualizado.")
        return redirect("plano_editar", pk=passo.projeto.pk)

    return render(
        request,
        "projetos/passo_editar.html",
        {"formulario": formulario, "passo": passo, "projeto": passo.projeto},
    )


@login_required
def passo_novo(request, pk):
    """Acrescenta um passo ao fim de uma etapa."""
    etapa = get_object_or_404(
        Etapa.objects.filter(plano__projeto__usuario=request.user, plano__ativo=True), pk=pk
    )
    formulario = PassoForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        passo = formulario.save(commit=False)
        passo.etapa = etapa
        ultima = etapa.passos.order_by("-ordem").values_list("ordem", flat=True).first() or 0
        passo.ordem = ultima + 1
        # Nasce na fila; normalizar_fila abre se não houver nenhum aberto.
        passo.status = Passo.Status.BLOQUEADO
        formulario.save()
        normalizar_fila(etapa.plano)
        messages.success(request, "Passo criado.")
        return redirect("plano_editar", pk=etapa.plano.projeto_id)

    return render(
        request,
        "projetos/passo_editar.html",
        {"formulario": formulario, "etapa": etapa, "projeto": etapa.plano.projeto},
    )


@login_required
def passo_mover(request, pk):
    """Troca de lugar com o vizinho dentro da mesma etapa.

    Só dentro da etapa: mover um passo para outra etapa muda o sentido do
    agrupamento, e quem quer isso quer mesmo é reescrever o passo.
    """
    passo = get_object_or_404(Passo.objects.do_usuario(request.user), pk=pk)
    if request.method != "POST":
        return redirect("plano_editar", pk=passo.projeto.pk)

    irmaos = passo.etapa.passos
    if request.POST.get("direcao") == "cima":
        vizinho = irmaos.filter(ordem__lt=passo.ordem).order_by("-ordem").first()
    else:
        vizinho = irmaos.filter(ordem__gt=passo.ordem).order_by("ordem").first()

    if vizinho:
        passo.ordem, vizinho.ordem = vizinho.ordem, passo.ordem
        passo.save(update_fields=["ordem"])
        vizinho.save(update_fields=["ordem"])

    return redirect("plano_editar", pk=passo.projeto.pk)


@login_required
def passo_remover(request, pk):
    passo = get_object_or_404(
        Passo.objects.do_usuario(request.user).select_related("etapa__plano__projeto"), pk=pk
    )
    if request.method == "POST":
        plano = passo.etapa.plano
        projeto_pk = passo.projeto.pk
        passo.delete()
        normalizar_fila(plano)
        messages.success(request, "Passo removido.")
        return redirect("plano_editar", pk=projeto_pk)

    return redirect("plano_editar", pk=passo.projeto.pk)


@login_required
def passo_detalhe(request, pk):
    passo = get_object_or_404(
        Passo.objects.do_usuario(request.user).select_related("etapa__plano__projeto"), pk=pk
    )

    # Bloqueado é inacessível de verdade: nem o link nem a URL direta mostram o
    # conteúdo. Só abre quando o anterior passar na revisão (atende ou
    # atende_com_ressalvas contam, ver Revisao.aprovado), ou for concluído à
    # mão. Passos são criados adiantados (ver passo_pre_gerar) só para não
    # esperar o mentor no meio da fila, não para virarem leitura antecipada.
    if passo.status == Passo.Status.BLOQUEADO:
        messages.info(request, "Esse passo ainda está bloqueado. Termine o anterior para abri-lo.")
        if passo.anterior:
            return redirect("passo_detalhe", pk=passo.anterior.pk)
        return redirect("projeto_detalhe", pk=passo.projeto.pk)

    # O chat ao lado é o do próprio passo, separado dos demais. Buscar aqui
    # evita que o include apareça vazio quando já há histórico.
    conversa = servicos_mentoria.obter_conversa_do_passo(passo)

    projeto = passo.projeto
    plano = projeto.plano_ativo
    pre_gerar_url = None
    if (
        passo.status == Passo.Status.DISPONIVEL
        and not projeto.gerando
        and passo.proximo is None
        and etapa_pendente(plano)
        and not Passo.objects.filter(etapa__plano=plano, status=Passo.Status.BLOQUEADO).exists()
    ):
        from django.urls import reverse
        pre_gerar_url = reverse("projeto_passo_pre_gerar", args=[projeto.pk])

    return render(
        request,
        "projetos/passo.html",
        {
            "passo": passo,
            "projeto": projeto,
            "revisoes": passo.submissoes.select_related("revisao")[:5],
            "total_revisoes": passo.submissoes.count(),
            "mensagens": conversa.mensagens.all(),
            "anterior": passo.anterior,
            "proximo": passo.proximo,
            "pre_gerar_url": pre_gerar_url,
        },
    )


@login_required
def passo_concluir(request, pk):
    """Conclusão manual: o aluno assume que fez, sem passar pela revisão."""
    passo = get_object_or_404(Passo.objects.do_usuario(request.user), pk=pk)
    if request.method == "POST":
        from django.utils import timezone

        passo.status = Passo.Status.CONCLUIDO
        passo.concluido_em = timezone.now()
        passo.concluido_manualmente = True
        passo.save(update_fields=["status", "concluido_em", "concluido_manualmente"])
        atualizar_status_do_projeto(passo.etapa.plano)

        proximo = (
            Passo.objects.do_usuario(request.user)
            .filter(etapa__plano=passo.etapa.plano, status=Passo.Status.BLOQUEADO)
            .first()
        )
        if proximo:
            proximo.status = Passo.Status.DISPONIVEL
            proximo.save(update_fields=["status"])
            messages.success(request, f"Passo concluído. Liberado: {proximo.titulo}.")
            return redirect("passo_detalhe", pk=proximo.pk)

        # Sem passo já materializado esperando: se o plano ainda tem etapa em
        # aberto, é hora do mentor preparar o próximo, um de cada vez.
        if etapa_pendente(passo.etapa.plano):
            messages.success(request, "Passo concluído. Preparando o próximo…")
            return redirect("projeto_passo_gerando", pk=passo.projeto.pk)

        messages.success(request, "Passo concluído. Era o último da fila.")
    return redirect("projeto_detalhe", pk=passo.projeto.pk)


@login_required
def exportar_markdown(request, pk):
    """O plano em Markdown, para levar para fora do app.

    Sem isto, o roteiro do próprio projeto fica preso aqui dentro, e um plano
    que não pode virar issue, README ou anotação vale menos do que poderia.
    """
    projeto = obter_do_usuario(Projeto, request.user, pk=pk)
    plano = projeto.plano_ativo
    if not plano:
        raise Http404

    linhas = [f"# {projeto.titulo}", "", projeto.objetivo, "", f"**Stack:** {projeto.stacks_texto}", "",
              f"## Plano (versão {plano.versao})", "", plano.resumo, ""]

    for etapa in plano.etapas.prefetch_related("passos"):
        linhas += [f"### {etapa.ordem}. {etapa.titulo}", ""]
        if etapa.objetivo:
            linhas += [etapa.objetivo, ""]
        for passo in etapa.passos.all():
            marca = "x" if passo.status == Passo.Status.CONCLUIDO else " "
            linhas += [f"- [{marca}] **{passo.numero} {passo.titulo}**", ""]
            linhas += [f"  - O que fazer: {passo.o_que_fazer}"]
            linhas += [f"  - Como fazer: {passo.como_fazer}"]
            linhas += [f"  - Por quê: {passo.teoria}"]
            if passo.o_que_enviar:
                linhas += [f"  - O que mandar para revisão: {passo.o_que_enviar}"]
            for criterio in passo.criterios_aceite:
                linhas.append(f"  - [ ] {criterio}")
            linhas.append("")

    resposta = HttpResponse("\n".join(linhas), content_type="text/markdown; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="plano-{projeto.pk}.md"'
    return resposta
