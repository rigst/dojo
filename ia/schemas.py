"""Formato do que o mentor devolve quando a resposta não é conversa.

Plano e revisão voltam como JSON validado por schema, não como texto para o app
interpretar depois: assim um campo faltando falha na hora, e não três telas
adiante com uma tela em branco.
"""

from typing import Literal

from pydantic import BaseModel, Field


class RecursoGerado(BaseModel):
    titulo: str
    url: str = ""


class PassoGerado(BaseModel):
    titulo: str = Field(description="O que este passo entrega, em uma linha.")
    o_que_fazer: str = Field(description="A tarefa concreta, sem código pronto.")
    como_fazer: str = Field(description="O caminho: onde mexer, em que ordem, o que consultar.")
    teoria: str = Field(description="Por que é assim: o conceito e o trade-off por trás.")
    o_que_enviar: str = Field(
        description="O que colar na revisão deste passo especificamente: qual arquivo, função ou "
        "trecho, em uma frase. Não 'o código deste passo', e sim algo como 'o método save() do "
        "modelo Tarefa' ou 'a rota POST /tarefas e o handler dela'."
    )
    criterios_aceite: list[str] = Field(
        default_factory=list,
        description="Como o aluno sabe que terminou. Verificáveis, não vagos.",
    )
    armadilhas: list[str] = Field(default_factory=list)
    recursos: list[RecursoGerado] = Field(default_factory=list)
    estimativa_min: int | None = None


class EtapaGerada(BaseModel):
    titulo: str
    objetivo: str = ""
    passos: list[PassoGerado]


class PlanoGerado(BaseModel):
    resumo: str = Field(
        description="O projeto em um parágrafo, do jeito que o aluno vai construí-lo."
    )
    etapas: list[EtapaGerada]


class EtapaEsboco(BaseModel):
    """Etapa sem os passos ainda: só o suficiente para desenhar o roteiro.

    Usado na primeira chamada de geração, que devolve o plano inteiro numa
    resposta bem menor que a de `PlanoGerado`. É essa resposta menor que evita
    o corte no meio do JSON quando o plano tem muitas etapas e passos.
    """

    titulo: str
    objetivo: str = ""


class PlanoInicialGerado(BaseModel):
    """O que a primeira chamada de planejamento devolve: o roteiro geral e só o
    primeiro passo, pronto para o aluno começar. Os demais passos são gerados
    um de cada vez, à medida que o aluno avança (ver `PassoSeguinteGerado`).

    Também batiza o projeto: o título que a pessoa digitou na criação é só um
    rascunho (ou nem existe), então o mentor escolhe o nome de verdade aqui,
    a partir do objetivo real.
    """

    titulo: str = Field(
        description="Nome curto do projeto, até uns 6 palavras, que a pessoa reconheça de relance "
        "numa lista. Não é o objetivo resumido, é um nome."
    )
    subtitulo: str = Field(
        description="Uma frase curta dizendo o que o projeto faz e para quem. Não repete o título."
    )
    resumo: str = Field(
        description="O projeto em um parágrafo, do jeito que o aluno vai construí-lo."
    )
    etapas: list[EtapaEsboco]
    primeiro_passo: PassoGerado = Field(description="O primeiro passo da primeira etapa, completo.")


class PassoSeguinteGerado(BaseModel):
    """O que cada chamada incremental devolve: um passo e se ele fecha a etapa."""

    passo: PassoGerado
    etapa_concluida: bool = Field(
        description="true se, depois deste passo, a etapa já entrega o objetivo dela e não precisa de mais passos."
    )


class PerguntaBriefing(BaseModel):
    pergunta: str = Field(description="Curta e concreta, respondível em uma frase.")
    porque: str = Field(description="O que muda no plano conforme a resposta.")
    opcoes: list[str] = Field(
        description="3 a 5 alternativas curtas para escolher, da mais provável à mais rara. "
        "Sem campo de texto livre: a pessoa escolhe a que mais se encaixa."
    )


class BriefingGerado(BaseModel):
    perguntas: list[PerguntaBriefing] = Field(description="Entre 3 e 5.")


class ProblemaEncontrado(BaseModel):
    severidade: Literal["bloqueia", "importante", "detalhe"]
    onde: str = Field(description="Arquivo, função ou trecho. Sem reescrever o código.")
    o_que: str
    por_que: str = Field(description="O conceito por trás, o que o aluno leva daqui.")


class CriterioAvaliado(BaseModel):
    criterio: str
    atende: bool
    comentario: str = ""


class RevisaoCodigo(BaseModel):
    veredito: Literal["atende", "atende_com_ressalvas", "nao_atende"]
    resumo: str
    criterios_avaliados: list[CriterioAvaliado] = Field(default_factory=list)
    pontos_fortes: list[str] = Field(default_factory=list)
    problemas: list[ProblemaEncontrado] = Field(default_factory=list)
    proximo_passo_sugerido: str = ""
