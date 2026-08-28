import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render

from ia.contabilidade import uso_do_mes
from usuarios.forms import CadastroForm
from usuarios.models import Usuario
from usuarios.seguranca import bloqueado, ip_do_pedido, limpar, registrar_falha
from usuarios.visitantes import (
    criar_visitante,
    excedeu_limite_de_criacao,
    limpar_expirados,
    registrar_tentativa,
)

logger = logging.getLogger(__name__)


class Entrar(auth_views.LoginView):
    """A tela de entrada, com trava de força bruta.

    O Django não traz uma: sem isto, a tela aceita quantas tentativas vierem,
    e é o alvo óbvio de quem varre a internet testando senha.
    """

    template_name = "usuarios/entrar.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = ip_do_pedido(request)

        if bloqueado(ip):
            logger.warning("Entrada bloqueada por excesso de tentativas", extra={"ip": ip})
            messages.error(
                request,
                "Muitas tentativas de entrada deste endereço. Espere alguns "
                "minutos antes de tentar de novo.",
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()), status=429)

        resposta = super().post(request, *args, **kwargs)

        # Redirecionou significa que entrou. Qualquer outra coisa é falha.
        if 300 <= resposta.status_code < 400:
            limpar(ip)
        else:
            registrar_falha(ip)
        return resposta


def entrar_como_visitante(request):
    """Cria a conta descartável e entra com ela.

    POST porque cria dado. A limpeza dos expirados roda aqui, de carona: é o
    único momento em que se sabe que o app está sendo usado, e evita depender
    só do cron para o banco não acumular contas mortas.
    """
    if request.method != "POST":
        return redirect("login")

    if request.user.is_authenticated:
        return redirect("painel")

    ip = ip_do_pedido(request)
    if excedeu_limite_de_criacao(ip):
        logger.warning("Limite de criação de visitante excedido", extra={"ip": ip})
        messages.error(
            request,
            "Muitos acessos de visitante deste endereço em pouco tempo. "
            "Espere alguns minutos ou crie uma conta.",
        )
        return redirect("login")

    registrar_tentativa(ip)
    limpar_expirados()

    usuario = criar_visitante()
    login(request, usuario)
    messages.success(
        request,
        f"Você entrou como visitante. Já deixamos um projeto de exemplo pronto "
        f"para você abrir. Esta conta e tudo o que você criar nela são apagados "
        f"em {settings.VISITANTE_TTL_HORAS} horas.",
    )
    return redirect("painel")


def cadastrar(request):
    if request.user.is_authenticated:
        return redirect("painel")

    formulario = CadastroForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        login(request, usuario)
        return redirect("painel")

    return render(request, "usuarios/cadastrar.html", {"formulario": formulario})


@login_required
def conta(request):
    usuario = request.user

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "tema":
            usuario.tema = request.POST.get("tema", usuario.Tema.AUTO)
            usuario.save(update_fields=["tema"])
            messages.success(request, "Tema atualizado.")

        return redirect("conta")

    uso = uso_do_mes(usuario)
    limite = usuario.limite_mensal_usd
    return render(
        request,
        "usuarios/conta.html",
        {
            "uso": uso,
            "limite": limite,
            "pct_uso": min(100, round(float(uso.custo_usd) * 100 / float(limite))) if limite else 0,
        },
    )


@login_required
def tema(request):
    """Grava a troca feita pelo botão do shell.

    Responde 204 porque não há nada a renderizar: a tela já trocou de cor antes
    de esta requisição sair.
    """
    escolhido = request.POST.get("tema")
    if request.method != "POST" or escolhido not in Usuario.Tema.values:
        return HttpResponseBadRequest("tema inválido")

    request.user.tema = escolhido
    request.user.save(update_fields=["tema"])
    return HttpResponse(status=204)


@login_required
def exportar_dados(request):
    """Tudo que é seu, em JSON.

    Existe por obrigação legal e por decência: dado de aprendizado é registro
    pessoal, e quem escreveu tem de poder levar embora.
    """
    usuario = request.user
    dados = {
        "usuario": {
            "username": usuario.get_username(),
            "email": usuario.email,
            "criado_em": usuario.date_joined.isoformat(),
        },
        "projetos": [],
        "uso_mensal": list(usuario.usos.values("ano_mes", "custo_usd", "mensagens")),
    }

    for projeto in usuario.projetos.prefetch_related("stacks", "planos__etapas__passos"):
        dados["projetos"].append(
            {
                "titulo": projeto.titulo,
                "objetivo": projeto.objetivo,
                "stacks": [s.nome for s in projeto.stacks.all()],
                "status": projeto.status,
                "planos": [
                    {
                        "versao": plano.versao,
                        "resumo": plano.resumo,
                        "ativo": plano.ativo,
                        "etapas": [
                            {
                                "titulo": etapa.titulo,
                                "passos": [
                                    {
                                        "titulo": passo.titulo,
                                        "o_que_fazer": passo.o_que_fazer,
                                        "como_fazer": passo.como_fazer,
                                        "teoria": passo.teoria,
                                        "criterios_aceite": passo.criterios_aceite,
                                        "status": passo.status,
                                    }
                                    for passo in etapa.passos.all()
                                ],
                            }
                            for etapa in plano.etapas.all()
                        ],
                    }
                    for plano in projeto.planos.all()
                ],
                "conversa": [
                    {"papel": m.papel, "conteudo": m.conteudo, "em": m.criado_em.isoformat()}
                    for m in getattr(projeto, "conversa", None).mensagens.all()
                ]
                if hasattr(projeto, "conversa")
                else [],
            }
        )

    resposta = HttpResponse(
        json.dumps(dados, ensure_ascii=False, indent=2, default=str),
        content_type="application/json",
    )
    resposta["Content-Disposition"] = 'attachment; filename="dojo-meus-dados.json"'
    return resposta


@login_required
def excluir_conta(request):
    if request.method != "POST":
        return redirect("conta")

    if request.POST.get("confirmacao") != request.user.get_username():
        messages.error(request, "Digite seu nome de usuário para confirmar.")
        return redirect("conta")

    usuario = request.user
    logout(request)
    # Cascata: projetos, planos, passos, conversas e submissões vão junto.
    usuario.delete()
    messages.success(request, "Conta excluída. Seus dados foram apagados.")
    return redirect("login")
