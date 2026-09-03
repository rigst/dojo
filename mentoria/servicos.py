"""Montagem do histórico e persistência das mensagens do chat."""

from ia import prompts
from mentoria.models import Conversa, Mensagem

# Quantas mensagens do histórico vão junto da pergunta. O plano inteiro já vai
# no bloco de contexto (cacheado); o histórico só precisa dar continuidade à
# conversa, e mandar tudo desde o começo cresce o custo a cada turno.
JANELA_MENSAGENS = 20


def obter_conversa_geral(projeto):
    """A conversa sobre o projeto como um todo, fora do foco de um passo."""
    conversa, _ = Conversa.objects.get_or_create(projeto=projeto, passo=None)
    return conversa


def obter_conversa_do_passo(passo):
    """A conversa deste passo, separada da de qualquer outro.

    Nasce vazia na primeira pergunta feita ali: sem histórico de outro passo
    para carregar, e sem o histórico deste vazar para o próximo.
    """
    conversa, _ = Conversa.objects.get_or_create(passo=passo, defaults={"projeto": passo.projeto})
    return conversa


def historico_para_api(conversa):
    """Últimas mensagens no formato da API, da mais antiga para a mais nova.

    Mensagem interrompida entra igual: para o modelo, texto parcial do próprio
    turno anterior é contexto legítimo, e omiti-la faria a conversa dar um salto
    inexplicável.
    """
    mensagens = list(conversa.mensagens.order_by("-criado_em")[:JANELA_MENSAGENS])
    mensagens.reverse()
    return [{"role": m.papel, "content": m.conteudo} for m in mensagens if m.conteudo.strip()]


def registrar_pergunta(conversa, texto, passo=None):
    return Mensagem.objects.create(
        conversa=conversa, papel=Mensagem.Papel.ALUNO, conteudo=texto, passo=passo
    )


def registrar_resposta(conversa, texto, passo=None, uso=None, stop_reason="", erro=""):
    """Grava a resposta do mentor com o que ela custou.

    Chamada também quando a resposta foi interrompida no meio: o que já foi
    gerado foi cobrado, e some da tela se não for gravado.
    """
    dados = {
        "conversa": conversa,
        "papel": Mensagem.Papel.MENTOR,
        "conteudo": texto,
        "passo": passo,
        "stop_reason": stop_reason,
        "erro": erro[:200],
        "versao_prompt": prompts.VERSAO_PROMPT,
    }
    if uso is not None:
        dados.update(
            modelo=uso.modelo,
            tokens_entrada=uso.entrada,
            tokens_saida=uso.saida,
            tokens_cache_leitura=uso.cache_leitura,
            tokens_cache_escrita=uso.cache_escrita,
            custo_usd=uso.custo_usd,
            request_id=uso.request_id,
        )
    return Mensagem.objects.create(**dados)
