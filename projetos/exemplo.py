"""O projeto que já está lá quando o visitante entra.

Sem isto, quem clica em "Entrar como visitante" para ver o Dojo cai num painel
vazio e precisa inventar um projeto, escrever um briefing e esperar o plano ser
gerado antes de ver qualquer coisa. É bastante trabalho para quem só queria
olhar.

O plano abaixo é escrito à mão, não gerado. Duas razões: ele aparece na hora,
sem espera, e não custa nada de API para quem hospeda o app, que é exatamente o
gasto que a conta de visitante existe para conter. O chat, a revisão de código e
o replanejamento continuam sendo o mentor de verdade.
"""

from ia.schemas import EtapaGerada, PassoGerado, PlanoGerado, RecursoGerado
from projetos.models import Projeto, Stack
from projetos.servicos import salvar_plano

TITULO = "Encurtador de links"

OBJETIVO = (
    "Um serviço web onde eu colo uma URL longa e recebo um endereço curto que "
    "redireciona para ela. Quero ver quantas vezes cada link foi aberto e "
    "poder rodar tudo na minha máquina, com um banco em arquivo."
)

STACKS = ["Python", "Flask", "SQLite"]

RESUMO = (
    "Você vai construir um encurtador de links do zero, em Flask com SQLite. "
    "Ele cabe em poucas centenas de linhas e mesmo assim passa por quase tudo "
    "que um serviço web tem: rota que recebe dado de fora, validação do que "
    "chegou, escrita e leitura no banco, redirecionamento com o código HTTP "
    "certo, contagem de acessos e um punhado de testes. A ordem dos passos "
    "segue o caminho do dado: primeiro o servidor responde, depois ele guarda, "
    "depois ele devolve, e só no fim ele fica bonito."
)

ETAPAS = [
    EtapaGerada(
        titulo="O servidor de pé",
        objetivo="Ter uma aplicação Flask que responde, com ambiente isolado e teste rodando.",
        passos=[
            PassoGerado(
                titulo="Ambiente virtual e primeira rota",
                o_que_fazer=(
                    "Crie a pasta do projeto, um ambiente virtual próprio, instale o Flask "
                    "e escreva uma aplicação de um arquivo com uma única rota GET em `/` "
                    "que devolva a palavra que você quiser. Suba o servidor e abra no navegador."
                ),
                como_fazer=(
                    "Use o `venv` que já vem com o Python: `python -m venv .venv` e depois "
                    "ative. Instale com `pip install flask` e congele o que você instalou num "
                    "`requirements.txt`. O arquivo principal pode se chamar `app.py`; nele você "
                    "cria a instância do Flask e decora uma função com a rota. Para subir, "
                    "prefira `flask --app app run --debug` a chamar o `app.run()` dentro do "
                    "arquivo: o modo debug recarrega sozinho quando você salva."
                ),
                teoria=(
                    "O ambiente virtual não é burocracia. Sem ele, cada projeto instala "
                    "bibliotecas na mesma pasta do sistema, e dois projetos que precisam de "
                    "versões diferentes da mesma biblioteca passam a brigar. O `.venv` dá a "
                    "cada projeto sua própria árvore de dependências, e o `requirements.txt` é "
                    "o que permite reconstruí-la em outra máquina. Já o decorador de rota é a "
                    "sua primeira tabela de despacho: o Flask guarda o par caminho/função e, "
                    "quando chega uma requisição, procura nessa tabela quem responde."
                ),
                o_que_enviar="O app.py com a rota / e o requirements.txt.",
                criterios_aceite=[
                    "`python -m flask --version` funciona dentro do ambiente ativado.",
                    "Abrir http://127.0.0.1:5000/ no navegador mostra o texto da sua rota.",
                    "O `requirements.txt` existe e lista o Flask com versão.",
                    "A pasta `.venv` está no `.gitignore`.",
                ],
                armadilhas=[
                    "Instalar o Flask fora do ambiente ativado. Confira com `which python` (ou `where python` no Windows) antes do `pip install`.",
                    "Chamar o arquivo de `flask.py`. O Python importa o seu arquivo no lugar da biblioteca e o erro que aparece não tem relação nenhuma com a causa.",
                    "Versionar o `.venv`. São milhares de arquivos que não servem em outra máquina.",
                ],
                recursos=[
                    RecursoGerado(titulo="Flask: guia de início rápido", url="https://flask.palletsprojects.com/en/stable/quickstart/"),
                    RecursoGerado(titulo="Python: ambientes virtuais", url="https://docs.python.org/pt-br/3/library/venv.html"),
                ],
                estimativa_min=45,
            ),
            PassoGerado(
                titulo="O primeiro teste",
                o_que_fazer=(
                    "Instale o pytest e escreva um teste que faz uma requisição à rota `/` e "
                    "verifica o código de status e o corpo da resposta, sem subir o servidor à mão."
                ),
                como_fazer=(
                    "O Flask tem um cliente de teste: `app.test_client()` devolve um objeto que "
                    "faz requisições direto na aplicação, sem rede. Coloque o teste em "
                    "`tests/test_app.py` e monte o cliente numa fixture do pytest, para não "
                    "repetir a montagem em cada teste. Rode com `pytest -q`."
                ),
                teoria=(
                    "Testar agora, com uma rota só, parece exagero. É o contrário: o teste que "
                    "vale a pena é o que já existe quando o código quebra, e o momento barato de "
                    "montar a infraestrutura de teste é quando ainda não há nada para testar. O "
                    "cliente de teste também empurra o desenho na direção certa, porque ele só "
                    "consegue chamar o que estiver acessível pela aplicação, e não por variáveis "
                    "globais espalhadas."
                ),
                o_que_enviar="O arquivo tests/test_app.py com o teste e a fixture do cliente.",
                criterios_aceite=[
                    "`pytest -q` roda e passa, sem o servidor estar no ar.",
                    "O teste verifica o status 200 e algo do corpo da resposta.",
                    "O cliente de teste vem de uma fixture, não de código repetido em cada função.",
                ],
                armadilhas=[
                    "Testar batendo em http://127.0.0.1:5000 com `requests`. Isso exige o servidor no ar e transforma um teste rápido num teste frágil.",
                    "Esquecer o `__init__.py` ou a configuração de caminho e ver `ModuleNotFoundError: app` ao rodar o pytest de outra pasta.",
                ],
                recursos=[
                    RecursoGerado(titulo="Flask: testando aplicações", url="https://flask.palletsprojects.com/en/stable/testing/"),
                ],
                estimativa_min=40,
            ),
        ],
    ),
    EtapaGerada(
        titulo="Guardar e redirecionar",
        objetivo="O miolo do produto: encurtar de verdade, persistir e levar o visitante ao destino.",
        passos=[
            PassoGerado(
                titulo="A tabela de links no SQLite",
                o_que_fazer=(
                    "Crie o banco SQLite com uma tabela de links contendo, no mínimo, o código "
                    "curto, a URL de destino, a data de criação e um contador de acessos. "
                    "Escreva uma função que abre a conexão e outra que cria o esquema."
                ),
                como_fazer=(
                    "O módulo `sqlite3` já vem no Python, não instale nada. Guarde o esquema num "
                    "arquivo `schema.sql` e execute-o com `executescript`, em vez de deixar o "
                    "`CREATE TABLE` como string no meio do código. O código curto deve ser "
                    "`PRIMARY KEY` ou ter índice `UNIQUE`. Use `sqlite3.Row` como `row_factory` "
                    "para poder ler as colunas pelo nome."
                ),
                teoria=(
                    "O índice único no código curto não é otimização, é regra de negócio "
                    "escrita no lugar mais confiável: o banco. Se ela morasse só no Python, "
                    "duas requisições simultâneas poderiam checar 'esse código já existe?' ao "
                    "mesmo tempo, ambas concluírem que não, e ambas inserirem. O banco é o "
                    "único ponto que vê as duas escritas, e por isso é o único lugar onde a "
                    "garantia realmente se sustenta."
                ),
                o_que_enviar="O schema.sql e as funções que abrem a conexão e criam o esquema.",
                criterios_aceite=[
                    "O arquivo do banco é criado por um comando seu, não à mão.",
                    "Rodar a criação duas vezes não quebra nem duplica tabela.",
                    "Tentar inserir o mesmo código curto duas vezes levanta `IntegrityError`.",
                    "As linhas lidas permitem acesso por nome de coluna.",
                ],
                armadilhas=[
                    "Deixar a conexão aberta como variável global do módulo. Conexão do sqlite3 é presa à thread que a criou.",
                    "Esquecer o `commit`. A inserção parece funcionar e some quando o processo termina.",
                    "Montar SQL com f-string a partir do que veio do usuário. É injeção de SQL; use parâmetros com `?`.",
                ],
                recursos=[
                    RecursoGerado(titulo="Python: módulo sqlite3", url="https://docs.python.org/pt-br/3/library/sqlite3.html"),
                ],
                estimativa_min=60,
            ),
            PassoGerado(
                titulo="Encurtar: a rota que recebe a URL",
                o_que_fazer=(
                    "Faça a rota POST que recebe uma URL, valida, gera um código curto único, "
                    "grava no banco e devolve o link encurtado. Recusar entrada inválida faz "
                    "parte do passo."
                ),
                como_fazer=(
                    "Gere o código com `secrets.token_urlsafe` cortado em 6 ou 7 caracteres, ou "
                    "sorteie de um alfabeto seu. Trate a colisão tentando de novo, num laço com "
                    "número máximo de tentativas, em vez de confiar na sorte. Para validar, "
                    "`urllib.parse.urlparse` já resolve o essencial: exija esquema `http` ou "
                    "`https` e um domínio não vazio. Responda 400 com uma mensagem útil quando "
                    "recusar, e 201 quando criar."
                ),
                teoria=(
                    "Aqui aparece a diferença entre validar e sanitizar. Você não conserta a URL "
                    "do usuário: você aceita ou recusa, e diz por quê. Aceitar qualquer esquema "
                    "abriria a porta para `javascript:` num redirecionamento, que é um ataque de "
                    "verdade. Sobre os códigos de status, eles não são decoração: 201 diz "
                    "'criei um recurso novo', e é o que cliente, proxy e navegador leem para "
                    "decidir o que fazer sem entender nada do seu domínio."
                ),
                o_que_enviar="A rota POST que recebe a URL, valida e grava no banco.",
                criterios_aceite=[
                    "Enviar uma URL válida devolve 201 com o link curto no corpo.",
                    "Enviar `nao-e-url` ou `javascript:alert(1)` devolve 400 e não grava nada.",
                    "Duas chamadas com a mesma URL geram códigos diferentes e ambos funcionam.",
                    "Há teste automatizado para o caminho feliz e para pelo menos uma recusa.",
                ],
                armadilhas=[
                    "Devolver 200 para erro de validação, com a mensagem de erro no corpo. Quem consome não tem como distinguir sucesso de falha.",
                    "Gerar o código com `random`. Ele é previsível; para identificadores públicos use `secrets`.",
                    "Confiar que a colisão nunca acontece. Em 6 caracteres ela acontece, e o `IntegrityError` vira erro 500 na cara do usuário.",
                ],
                recursos=[
                    RecursoGerado(titulo="MDN: códigos de status HTTP", url="https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Status"),
                    RecursoGerado(titulo="Python: módulo secrets", url="https://docs.python.org/pt-br/3/library/secrets.html"),
                ],
                estimativa_min=75,
            ),
            PassoGerado(
                titulo="Redirecionar e contar o acesso",
                o_que_fazer=(
                    "Faça a rota GET `/<codigo>` que busca o destino, incrementa o contador de "
                    "acessos e redireciona. Código inexistente devolve 404 com uma página sua."
                ),
                como_fazer=(
                    "O `redirect` do Flask aceita o status. Use 302, não 301: o 301 é permanente "
                    "e o navegador guarda para sempre, o que faria seu contador parar de subir e "
                    "impediria você de corrigir um destino errado depois. O incremento deve ser "
                    "feito no próprio SQL (`UPDATE ... SET acessos = acessos + 1`), não lendo em "
                    "Python, somando um e escrevendo de volta."
                ),
                teoria=(
                    "O incremento no SQL é uma operação atômica: o banco lê e escreve como um só "
                    "ato, e duas requisições simultâneas somam duas. O `ler, somar, gravar` em "
                    "Python tem uma janela entre a leitura e a escrita, e nela cabe a leitura da "
                    "outra requisição. As duas leem 10, as duas gravam 11, e um acesso "
                    "desapareceu. Esse padrão tem nome, atualização perdida, e você vai reencontrá-lo "
                    "em saldo de conta, estoque e curtida."
                ),
                o_que_enviar="A rota GET /<codigo> com o redirecionamento e o incremento do contador.",
                criterios_aceite=[
                    "Abrir o link curto leva à URL original.",
                    "O contador sobe exatamente um por acesso.",
                    "Um código que não existe devolve 404, e não 500.",
                    "O incremento é feito em uma única instrução SQL.",
                ],
                armadilhas=[
                    "Usar 301. O navegador guarda o redirecionamento em cache e a rota deixa de ser chamada.",
                    "Ler o contador, somar em Python e gravar de volta.",
                    "Devolver a página de 404 padrão do Flask, que expõe mais do que precisa em modo debug.",
                ],
                recursos=[
                    RecursoGerado(titulo="MDN: redirecionamentos HTTP", url="https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Redirections"),
                ],
                estimativa_min=60,
            ),
        ],
    ),
    EtapaGerada(
        titulo="Uma cara e um fim",
        objetivo="Tornar o serviço usável por alguém que não seja você, e deixá-lo pronto para rodar fora da sua máquina.",
        passos=[
            PassoGerado(
                titulo="A página de encurtar",
                o_que_fazer=(
                    "Monte a página inicial com um formulário que envia a URL e mostra o link "
                    "curto pronto para copiar, além de uma lista dos links já criados com o "
                    "número de acessos de cada um."
                ),
                como_fazer=(
                    "Use os templates Jinja que já vêm com o Flask, em `templates/`. Comece por "
                    "um `base.html` com o esqueleto e estenda-o, em vez de repetir o HTML em "
                    "cada página. O formulário pode postar na mesma rota que você já escreveu, "
                    "distinguindo pelo `Accept` ou expondo uma rota separada para o navegador; "
                    "decida e anote a razão. Sempre imprima a URL do usuário pelo template, "
                    "nunca concatenando string, para o escape automático agir."
                ),
                teoria=(
                    "O escape automático do Jinja é o que separa seu app de um XSS. Se alguém "
                    "encurtar uma URL com aspas e uma tag `<script>` dentro e você imprimir isso "
                    "cru na listagem, o script roda no navegador de quem abrir a página. O "
                    "template escapa por padrão, e é justamente por isso que o `|safe` merece "
                    "desconfiança sempre que aparecer."
                ),
                o_que_enviar="O template da página inicial com o formulário e a listagem.",
                criterios_aceite=[
                    "A página inicial tem o formulário e funciona sem JavaScript.",
                    "Depois de encurtar, o link curto aparece na tela.",
                    "A listagem mostra destino, código e número de acessos.",
                    "Uma URL com `<script>` no meio aparece como texto na página, sem executar.",
                ],
                armadilhas=[
                    "Responder ao POST com HTML direto, sem redirecionar. Recarregar a página reenvia o formulário e cria um link duplicado.",
                    "Marcar a saída com `|safe` para 'consertar' um caractere escapado.",
                ],
                recursos=[
                    RecursoGerado(titulo="Jinja: templates", url="https://jinja.palletsprojects.com/en/stable/templates/"),
                    RecursoGerado(titulo="OWASP: XSS", url="https://owasp.org/www-community/attacks/xss/"),
                ],
                estimativa_min=70,
            ),
            PassoGerado(
                titulo="Configuração e empacotamento",
                o_que_fazer=(
                    "Tire da mão do código o que muda entre a sua máquina e um servidor: caminho "
                    "do banco, chave secreta e domínio base do link curto. Escreva um README com "
                    "o que é preciso para rodar do zero."
                ),
                como_fazer=(
                    "Leia a configuração de variáveis de ambiente com valores padrão para o "
                    "desenvolvimento, e deixe um `.env.example` versionado com os nomes das "
                    "variáveis e nenhum valor real. Troque a criação direta do `app` por uma "
                    "função `create_app()` que recebe a configuração: isso é o que vai permitir "
                    "ao teste montar a aplicação apontando para um banco temporário."
                ),
                teoria=(
                    "A fábrica de aplicação parece um rodeio até o primeiro teste que precisa de "
                    "um banco limpo. Com o `app` criado no momento em que o módulo é importado, "
                    "a configuração fica congelada na importação e o teste herda o banco de "
                    "desenvolvimento. Com a fábrica, cada contexto monta a sua. É a mesma ideia "
                    "de injeção de dependência que você vai encontrar em qualquer framework "
                    "maior, só que sem o nome pomposo."
                ),
                o_que_enviar="A função create_app(), o .env.example e o README.",
                criterios_aceite=[
                    "Nenhum caminho, chave ou domínio fixo sobrou no código.",
                    "O `.env.example` está versionado e o `.env` de verdade está ignorado.",
                    "Os testes montam a aplicação com um banco temporário e não tocam no de desenvolvimento.",
                    "Alguém consegue rodar o projeto seguindo só o README.",
                ],
                armadilhas=[
                    "Versionar o `.env` com a chave real dentro. Uma vez no histórico do Git, trocar a chave é a única saída.",
                    "Deixar a chave secreta com um valor padrão em produção. Sirva um padrão só quando estiver em desenvolvimento e falhe alto no resto.",
                ],
                recursos=[
                    RecursoGerado(titulo="Flask: fábrica de aplicação", url="https://flask.palletsprojects.com/en/stable/patterns/appfactories/"),
                    RecursoGerado(titulo="The Twelve-Factor App: configuração", url="https://12factor.net/pt_br/config"),
                ],
                estimativa_min=55,
            ),
        ],
    ),
]


def montar_plano():
    return PlanoGerado(resumo=RESUMO, etapas=ETAPAS)


def criar_projeto_exemplo(usuario):
    """Deixa o projeto pronto na conta, com o plano já na versão 1.

    O `modelo` do plano fica como "exemplo" em vez de um nome de modelo da API,
    porque nenhuma chamada foi feita: é o registro honesto de onde este plano
    veio.
    """
    projeto = Projeto.objects.create(
        usuario=usuario,
        titulo=TITULO,
        objetivo=OBJETIVO,
        nivel=Projeto.Nivel.INICIANTE,
        horas_por_semana=6,
        preferencia_didatica=Projeto.Didatica.SOCRATICO,
    )

    # get_or_create e não um filter: numa base sem `semear_stacks` rodado (um
    # ambiente novo, um banco de teste) o projeto ficaria sem stack nenhuma.
    for nome in STACKS:
        stack, _ = Stack.objects.get_or_create(nome=nome)
        projeto.stacks.add(stack)

    salvar_plano(projeto, montar_plano(), modelo="exemplo")
    return projeto
