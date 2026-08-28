"""Formato do que o mentor devolve quando a resposta não é conversa.

Plano e revisão voltam como JSON validado por schema, não como texto para o app
interpretar depois: assim um campo faltando falha na hora, e não três telas
adiante com uma tela em branco.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RecursoGerado(BaseModel):
    titulo: str
    url: str = ""


class PassoGerado(BaseModel):
    titulo: str = Field(description="O que este passo entrega, em uma linha.")
    o_que_fazer: str = Field(description="A tarefa concreta, sem código pronto.")
    como_fazer: str = Field(description="O caminho: onde mexer, em que ordem, o que consultar.")
    teoria: str = Field(description="Por que é assim: o conceito e o trade-off por trás.")
    criterios_aceite: List[str] = Field(
        default_factory=list,
        description="Como o aluno sabe que terminou. Verificáveis, não vagos.",
    )
    armadilhas: List[str] = Field(default_factory=list)
    recursos: List[RecursoGerado] = Field(default_factory=list)
    estimativa_min: Optional[int] = None


class EtapaGerada(BaseModel):
    titulo: str
    objetivo: str = ""
    passos: List[PassoGerado]


class PlanoGerado(BaseModel):
    resumo: str = Field(description="O projeto em um parágrafo, do jeito que o aluno vai construí-lo.")
    etapas: List[EtapaGerada]


class PerguntaBriefing(BaseModel):
    pergunta: str = Field(description="Curta e concreta, respondível em uma frase.")
    porque: str = Field(description="O que muda no plano conforme a resposta.")


class BriefingGerado(BaseModel):
    perguntas: List[PerguntaBriefing] = Field(description="Entre 3 e 5.")


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
    criterios_avaliados: List[CriterioAvaliado] = Field(default_factory=list)
    pontos_fortes: List[str] = Field(default_factory=list)
    problemas: List[ProblemaEncontrado] = Field(default_factory=list)
    proximo_passo_sugerido: str = ""
