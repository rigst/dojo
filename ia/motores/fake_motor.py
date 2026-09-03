"""Dublê do motor: responde sem tocar a rede.

É o padrão na suíte de testes. Teste que depende de chave de API não roda no
CI de ninguém, e uma resposta de modelo real não é determinística o bastante
para servir de asserção. Também dá para usar em desenvolvimento (DOJO_IA_BACKEND
=fake) quando se está mexendo na tela e não no prompt.

As respostas são fixas mas plausíveis: têm as três camadas, critérios de aceite
e o formato exato que os templates esperam.
"""

import asyncio

from ia.contabilidade import Uso
from ia.schemas import (
    BriefingGerado,
    CriterioAvaliado,
    EtapaEsboco,
    PassoGerado,
    PassoSeguinteGerado,
    PerguntaBriefing,
    PlanoInicialGerado,
    ProblemaEncontrado,
    RevisaoCodigo,
)

MODELO = "fake"

RESPOSTA_CHAT = (
    "**O que fazer.** Crie o modelo `Tarefa` com os campos mínimos: título, "
    "concluída e data de criação.\n\n"
    "**Como fazer.** Abra `models.py` do app, declare a classe herdando de "
    "`models.Model` e rode `makemigrations` para ver o que o Django gerou antes "
    "de aplicar.\n\n"
    "**Por que é assim.** A migration é o registro versionado do schema: ela "
    "existe para que o banco de produção chegue ao mesmo estado que o seu, na "
    "mesma ordem. Olhar o arquivo gerado antes de aplicar é o hábito que evita "
    "descobrir uma coluna errada só no deploy.\n\n"
    "Você saberá que funcionou quando `makemigrations` gerar um arquivo com uma "
    "operação `CreateModel`. O que você espera que aconteça se rodar o comando "
    "duas vezes seguidas?"
)


def _uso():
    # Números pequenos e estáveis: o teste de custo compara valor exato.
    return Uso(modelo=MODELO, entrada=1000, saida=500, cache_leitura=0, cache_escrita=0)


async def contar_tokens(pedido):
    # Aproximação grosseira e determinística: 4 caracteres por token. Serve
    # para o teste exercitar o caminho do limite sem depender da rede.
    caracteres = sum(len(str(b.get("text", ""))) for b in pedido.sistema)
    caracteres += sum(len(str(m.get("content", ""))) for m in pedido.mensagens)
    return caracteres // 4


async def gerar_briefing(pedido):
    return (
        BriefingGerado(
            perguntas=[
                PerguntaBriefing(
                    pergunta="Os dados ficam só na sua máquina ou precisam ir para um servidor?",
                    porque="Muda se o plano inclui deploy e banco de verdade desde cedo.",
                    opcoes=["Só na minha máquina", "Precisa ir para um servidor", "Ainda não sei"],
                ),
                PerguntaBriefing(
                    pergunta="Você já usou um ORM antes, ou seria a primeira vez?",
                    porque="Define se o passo do modelo de dados vira um passo ou três.",
                    opcoes=["Já usei", "Seria a primeira vez", "Usei um pouco, sem confiança"],
                ),
                PerguntaBriefing(
                    pergunta="Tem alguma tecnologia que você quer evitar neste projeto?",
                    porque="Evita um plano inteiro em cima de algo que você não quer aprender agora.",
                    opcoes=[
                        "Não, pode usar o que fizer sentido",
                        "Sim, tem uma ou mais para evitar",
                    ],
                ),
            ]
        ),
        _uso(),
    )


def _primeiro_passo():
    return PassoGerado(
        titulo="Subir o projeto vazio",
        o_que_fazer=(
            "Crie o projeto com o comando de scaffold da stack e faça a "
            "página inicial responder no navegador. Nada de modelo, nada "
            "de formulário: só o servidor de pé."
        ),
        como_fazer=(
            "Em ordem:\n\n"
            "1. Rode o comando que cria o esqueleto do projeto.\n"
            "2. Logo em seguida, suba o **servidor de desenvolvimento**.\n"
            "3. Abra o endereço que ele imprimir no terminal.\n\n"
            "Se a porta padrão estiver ocupada, passe outra em vez de matar o "
            "processo que está lá. Antes de seguir, abra os arquivos gerados e "
            "leia os nomes: você vai voltar a eles em todos os passos "
            "seguintes."
        ),
        teoria=(
            "Um esqueleto que roda é um ponto de retorno. A partir daqui, "
            "sempre que algo quebrar você consegue responder à pergunta "
            "mais útil da depuração: o que mudou desde a última vez que "
            "funcionou? Quem começa escrevendo a funcionalidade primeiro "
            "perde essa referência e passa a depurar duas coisas ao mesmo "
            "tempo, o próprio código e a montagem do projeto."
        ),
        o_que_enviar="O arquivo principal do projeto, com a rota da página inicial.",
        criterios_aceite=[
            "O servidor sobe sem erro no terminal.",
            "A página inicial responde 200 em localhost.",
            "Você consegue parar e subir o servidor de novo sem consultar nada.",
        ],
        armadilhas=[
            "Rodar o comando dentro da pasta errada e criar um projeto aninhado dentro do outro.",
            "Confundir a porta ocupada com erro do projeto; a mensagem diz qual é o caso.",
        ],
        estimativa_min=45,
    )


async def gerar_plano(pedido):
    return (
        PlanoInicialGerado(
            # Fixo e não derivado de `pedido.titulo_projeto`: esse campo, na
            # geração de verdade, ainda carrega o nome provisório da criação
            # ("Novo projeto"), e ecoá-lo aqui esconderia que o mentor é quem
            # escolhe o nome de verdade a partir do objetivo.
            titulo="Lista de tarefas guiada",
            subtitulo="Do esqueleto que roda até uma versão que você usa de verdade.",
            resumo=(
                f"O plano leva {pedido.titulo_projeto} de um esqueleto que roda até uma "
                "versão que você usa de verdade. A primeira etapa existe para você ter um "
                "ponto de retorno seguro antes de qualquer funcionalidade; as seguintes "
                "acrescentam uma ideia nova por vez."
            ),
            etapas=[
                EtapaEsboco(
                    titulo="Esqueleto que roda",
                    objetivo=(
                        "Ter o projeto de pé, servindo uma página, antes de escrever "
                        "qualquer regra de negócio."
                    ),
                ),
                EtapaEsboco(
                    titulo="Primeiro modelo de dados",
                    objetivo="Ter a entidade central do projeto persistida e visível no admin.",
                ),
            ],
            primeiro_passo=_primeiro_passo(),
        ),
        _uso(),
    )


async def gerar_proximo_passo(pedido):
    return (
        PassoSeguinteGerado(
            passo=PassoGerado(
                titulo="Primeiro modelo de dados",
                o_que_fazer=(
                    "Modele a entidade central do projeto com os campos mínimos "
                    "para ela existir, gere a migration e aplique."
                ),
                como_fazer=(
                    "Declare a classe no arquivo de modelos do app, com os campos "
                    "que você não consegue descrever a entidade sem eles. Gere a "
                    "migration e abra o arquivo gerado antes de aplicar: ele é "
                    "legível, e é ali que dá para ver se o que você escreveu virou "
                    "o que você queria. Depois registre o modelo no admin para "
                    "conseguir criar registros sem escrever formulário nenhum."
                ),
                teoria=(
                    "A migration é o registro versionado do schema. Ela existe "
                    "para que o banco de produção chegue ao mesmo estado que o "
                    "seu, na mesma ordem, sem ninguém rodar SQL à mão. Olhar o "
                    "arquivo gerado antes de aplicar é o hábito que evita "
                    "descobrir uma coluna errada só no deploy, quando corrigir "
                    "custa uma migration de correção em vez de uma tecla."
                ),
                o_que_enviar="O arquivo de modelos com a classe nova e a migration gerada.",
                criterios_aceite=[
                    "A migration aplica sem erro.",
                    "O admin lista o modelo e permite criar um registro.",
                    "Você sabe dizer o que cada campo guarda e por que ele existe.",
                ],
                armadilhas=[
                    "Colocar todos os campos que talvez sejam úteis um dia; campo sem uso hoje é dívida.",
                    "Aplicar a migration sem ler o arquivo gerado.",
                ],
                estimativa_min=60,
            ),
            etapa_concluida=True,
        ),
        _uso(),
    )


async def revisar(pedido):
    # O veredito depende do que veio: código com "TODO" não passa. É grosseiro
    # de propósito. Serve para o teste distinguir os dois caminhos sem depender
    # de um modelo de verdade.
    tem_pendencia = "TODO" in pedido.codigo or "pass" in pedido.codigo
    criterios = [
        CriterioAvaliado(criterio=c, atende=not tem_pendencia, comentario="")
        for c in (pedido.criterios or ["Sem critérios declarados"])
    ]
    return (
        RevisaoCodigo(
            veredito="nao_atende" if tem_pendencia else "atende",
            resumo="Ainda há trecho não implementado." if tem_pendencia else "Atende ao passo.",
            criterios_avaliados=criterios,
            pontos_fortes=[] if tem_pendencia else ["Nomes claros."],
            problemas=(
                [
                    ProblemaEncontrado(
                        severidade="bloqueia",
                        onde="o trecho enviado",
                        o_que="Há código não implementado.",
                        por_que="O passo só termina quando o comportamento existe de fato.",
                    )
                ]
                if tem_pendencia
                else []
            ),
            proximo_passo_sugerido="",
        ),
        _uso(),
    )


async def conversar(pedido, usuario):
    # Em pedaços, para o teste de streaming ver mais de um delta chegar.
    for pedaco in RESPOSTA_CHAT.split("\n\n"):
        await asyncio.sleep(0)
        yield {"tipo": "delta", "texto": pedaco + "\n\n"}
    yield {
        "tipo": "fim",
        "texto": RESPOSTA_CHAT,
        "uso": _uso(),
        "stop_reason": "end_turn",
    }
