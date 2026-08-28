"""Quanto custou, e quem pode continuar gastando.

Duas responsabilidades que andam juntas: converter o `usage` que a API devolve
em dólar, e barrar quem estourou a cota do mês antes de a chamada sair.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import F

from usuarios.models import UsoMensal

# Preço por milhão de tokens, por modelo. Leitura de cache custa ~0,1x a
# entrada; escrita custa ~1,25x. Números daqui viram dinheiro na tela do
# usuário, então mudança de tabela de preço é mudança de código, com teste.
PRECOS = {
    "claude-opus-5": {"entrada": Decimal("5"), "saida": Decimal("25")},
    "claude-sonnet-5": {"entrada": Decimal("3"), "saida": Decimal("15")},
    "claude-haiku-4-5": {"entrada": Decimal("1"), "saida": Decimal("5")},
}
PRECO_PADRAO = PRECOS["claude-opus-5"]

FATOR_CACHE_LEITURA = Decimal("0.1")
FATOR_CACHE_ESCRITA = Decimal("1.25")
MILHAO = Decimal("1000000")


class QuotaExcedida(RuntimeError):
    """O usuário passou do teto do mês. A chamada nem sai."""


@dataclass
class Uso:
    """O que uma resposta consumiu. Vira campos da Mensagem e soma na cota."""

    modelo: str = ""
    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0
    request_id: str = ""
    # Quando a API é chamada em rodadas (loop de ferramentas), o custo é a soma.
    rodadas: int = field(default=1)

    @classmethod
    def da_resposta(cls, resposta, modelo):
        u = resposta.usage
        return cls(
            modelo=modelo,
            entrada=u.input_tokens or 0,
            saida=u.output_tokens or 0,
            cache_leitura=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_escrita=getattr(u, "cache_creation_input_tokens", 0) or 0,
            request_id=getattr(resposta, "_request_id", "") or "",
        )

    def __add__(self, outro):
        return Uso(
            modelo=self.modelo or outro.modelo,
            entrada=self.entrada + outro.entrada,
            saida=self.saida + outro.saida,
            cache_leitura=self.cache_leitura + outro.cache_leitura,
            cache_escrita=self.cache_escrita + outro.cache_escrita,
            # O último request_id é o que interessa para rastrear a falha final.
            request_id=outro.request_id or self.request_id,
            rodadas=self.rodadas + outro.rodadas,
        )

    @property
    def custo_usd(self):
        preco = PRECOS.get(self.modelo, PRECO_PADRAO)
        entrada = Decimal(self.entrada) * preco["entrada"]
        saida = Decimal(self.saida) * preco["saida"]
        leitura = Decimal(self.cache_leitura) * preco["entrada"] * FATOR_CACHE_LEITURA
        escrita = Decimal(self.cache_escrita) * preco["entrada"] * FATOR_CACHE_ESCRITA
        return ((entrada + saida + leitura + escrita) / MILHAO).quantize(Decimal("0.000001"))


def uso_do_mes(usuario):
    registro, _ = UsoMensal.objects.get_or_create(
        usuario=usuario, ano_mes=UsoMensal.competencia_atual()
    )
    return registro


def verificar_quota(usuario):
    """Levanta QuotaExcedida quando não há orçamento para mais uma resposta.

    O teto vem do `.env`, definido por quem hospeda o app: a chave de API é uma
    só, do provedor, e é a conta dele que a resposta consome. O visitante tem um
    teto menor, porque a conta dele é anônima e qualquer um cria uma.
    """
    limite = usuario.limite_mensal_usd
    if limite <= 0:
        return

    if uso_do_mes(usuario).custo_usd >= limite:
        if usuario.eh_visitante:
            raise QuotaExcedida(
                "A conta de visitante chegou ao limite de uso deste mês. "
                "Crie uma conta para continuar praticando."
            )
        raise QuotaExcedida(
            f"Você chegou ao limite de US$ {limite} neste mês. "
            "Ele volta a zero na virada do mês; se precisar de mais, fale com quem administra o app."
        )


def registrar_uso(usuario, uso):
    """Soma o consumo no mês. Chamado depois de TODA resposta, inclusive as que
    falharam no meio, o que já foi gerado foi cobrado."""
    UsoMensal.objects.filter(pk=uso_do_mes(usuario).pk).update(
        custo_usd=F("custo_usd") + uso.custo_usd,
        mensagens=F("mensagens") + 1,
    )
