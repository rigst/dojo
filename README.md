# Dojo

[![CI](https://github.com/rigst/dojo/actions/workflows/ci.yml/badge.svg)](https://github.com/rigst/dojo/actions/workflows/ci.yml)
[![Cobertura](https://codecov.io/gh/rigst/dojo/branch/main/graph/badge.svg)](https://codecov.io/gh/rigst/dojo)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=rigst_dojo&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=rigst_dojo)
[![Licença: AGPL v3](https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Django 6](https://img.shields.io/badge/django-6.1-092E20.svg)](https://www.djangoproject.com/)

Mentoria de programação passo a passo. Você escolhe um projeto e uma stack; o
mentor monta um plano em etapas e passos e vai guiando: **o que fazer, como
fazer e por que é assim**, sem escrever o código por você.

O motor é a Claude API (`claude-opus-5`). A interface deriva do sistema visual
do `sistema_arq`.

## Como funciona

1. **Novo projeto**: o que você quer construir, stack, nível, tempo por semana
   e o estilo de ensino (socrático ou direto).
2. **Plano**: etapas e passos, cada passo com as três camadas e critérios de
   aceite verificáveis. O plano é versionado: replanejar cria a v2, não apaga a v1.
3. **Passo a passo**: só o primeiro passo nasce aberto. O próximo abre quando
   o atual é dado por concluído.
4. **Chat**: um por projeto, ancorado no passo em foco, com a resposta
   chegando token a token (SSE).
5. **Revisão**: você cola o código; o mentor avalia critério por critério e
   aponta problemas com o porquê, sem reescrever o trecho certo. Veredito
   `atende` conclui o passo e libera o seguinte.

O plano é editável a qualquer momento (`Editar o plano`): dá para corrigir o
texto de um passo, mover, remover e acrescentar. É o antídoto para o plano que
saiu quase certo, sem ele, a única saída seria refazer tudo e perder o
progresso. Refazer também existe, e guarda a versão anterior para consulta.

## Rodar em desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # e preencha ANTHROPIC_API_KEY
.venv/bin/python manage.py migrate
.venv/bin/python manage.py semear_stacks
.venv/bin/python -m uvicorn config.asgi:application --reload \
    --reload-include "*.html" --reload-include "*.css" --reload-include "*.js"
```

Os `--reload-include` não são luxo: sozinho, o `--reload` observa só arquivos
`.py`. Sem eles o processo continua servindo o template antigo depois de você
editá-lo, e o sintoma é uma mudança que "não aparece" nem com recarga forçada
do navegador.

**Use uvicorn, não `runserver`.** O chat, a geração do plano e a revisão são
servidos por SSE; sob WSGI cada conversa aberta prenderia um worker inteiro até
a resposta terminar.

Sem chave de API? `DOJO_IA_BACKEND=fake` responde com um plano e uma conversa de
exemplo, sem tocar a rede. Dá para mexer nas telas sem gastar nada.

## Atalhos

Na tela de um passo, `J` vai para o próximo e `K` volta ao anterior. Ignorados
enquanto se digita.

## Testes

```bash
.venv/bin/python -m pytest
```

A suíte roda contra o dublê (`ia/motores/fake_motor.py`) por padrão: teste que
depende de chave de API não roda no CI de ninguém. Os poucos testes que batem na
API de verdade têm o marcador `ia_real` e ficam de fora por padrão.

### De ponta a ponta e de tela

Em `testes_navegador/` há duas suítes que abrem um navegador de verdade. Elas
sobem o mesmo uvicorn do desenvolvimento contra um banco temporário, e não o
`live_server` do pytest-django, que é WSGI: o chat, o plano e a revisão são
todos SSE, e sob WSGI chegariam em bloco no fim. Testar contra um servidor
diferente do de produção testaria outro app.

Precisam do Chromium, que se instala uma vez:

```bash
.venv/bin/playwright install chromium
```

```bash
.venv/bin/python -m pytest -m e2e       # os caminhos inteiros, como uma pessoa percorre
.venv/bin/python -m pytest -m visual    # compara as telas com as referências
```

Ficam de fora do `pytest` pelado por serem lentas e dependerem do navegador.

As referências de tela vivem em `testes_navegador/referencia/` e são
versionadas. Quando uma comparação falha, a captura nova e a imagem das
diferenças ficam em `testes_navegador/diferencas/`. Falhar ali não quer dizer
"está errado", quer dizer "mudou": olhe a imagem e, se a mudança era a que você
queria, regrave com `--atualizar-telas`. É a rede que pega o dano que nenhum
teste de Python percebe, quando o servidor responde 200, o HTML está certo e a
tela está destruída. O CSS deste app tem regras que dependem da posição na
cascata, e o arquivo de origem registra que fundi-las quebra dezenas de telas.

As de tela não rodam no CI: a renderização de texto depende das fontes
instaladas na máquina, e a referência gravada aqui não bate com a do runner.
Rode-as à mão antes de commitar mudança de CSS.

O CI (`.github/workflows/ci.yml`) chama o pipeline compartilhado do
[rigst/ci](https://github.com/rigst/ci), o mesmo dos outros sete projetos:
suíte com cobertura, ponta a ponta, `check --deploy`, migrações sem pendência,
ruff, mypy, bandit, gitleaks e SonarCloud. O pyflakes saiu — o ruff cobre o
mesmo e mais.

`ruff` e `mypy` estão em `soft-fail` por enquanto: são 42 e 13 achados
pré-existentes de antes da migração. Saem de lá conforme forem zerados.
`run-lock`, `licenças` e `SBOM` esperam um `requirements.lock`, que este repo
ainda não tem.

## Identidade

A direção visual sai das duas obras que o app usa: o bambu de Hokusai e a
paisagem de Sesshū. Nanquim sobre papel, e é isso que a interface é, não uma
interface "inspirada" neles.

| | |
|---|---|
| **sumi** 墨 | a tinta. Texto e botão principal: no vocabulário original, tinta é tinta, e o botão cheio é preto sobre papel. |
| **washi** 和紙 | o papel. Off-white frio, levemente esverdeado, com a fibra visível por uma textura de ruído em SVG. Não é creme. |
| **shu** 朱 | o vermelhão do carimbo. Aprovação e agora: o selo, o passo em curso, o item ativo na lateral, o anel de foco. Nunca preenche área. |
| **ai** 藍 | o índigo. Explicação: a voz do mentor no chat e a camada de teoria (“por que é assim”). Shu e ai são o par clássico do artesanato japonês, o selo vermelho e o pano de índigo, e aqui dividem a tela por significado: o que foi aprovado e o que foi explicado. |
| **rokushō** 緑青 | o verdete do bronze. Critério cumprido. |

O movimento é um gesto só, repetido: tinta sendo depositada. O ensō da marca se
desenha ao carregar (entra carregado, corre, sai seco), os blocos da folha
assentam em cascata curta, a régua de cada seção é puxada, e o traço do passo em
curso pulsa devagar. Nada pisca, nada desliza de lado. Sob `prefers-reduced-motion`
as durações zeram e os laços são desligados, e como todo quadro final é o estado
visível, a tela nunca fica em branco se a animação não rodar.

Tipografia: **Zen Old Mincho** (só em título, e pouco), **Zen Kaku Gothic New**
(texto) e **M PLUS 1 Code** (rótulo, número, código). As três são famílias
japonesas com latim próprio. O latim delas herda a proporção do desenho dos
kana, que é o que dá o sotaque sem precisar de nenhum ornamento por cima.

Espaçamento: tudo sai de um módulo de 8px, como na carpintaria japonesa, em que
o 間 (ken) dimensiona o tatame, o vão entre pilares e o cômodo inteiro. São oito
degraus (`--ma-1` a `--ma-8`, de 4px a 72px) e nenhum valor solto: antes da
escala a folha usava 41 medidas diferentes de espaçamento, todas fazendo o mesmo
trabalho e nenhuma concordando com a outra. Escolher espaçamento agora é
escolher o degrau.

Corpo em 16px com entrelinha 1,75, e um piso: **nada de texto abaixo de 12px**,
e 12px só para rótulo em maiúscula. O piso é mais alto do que a web costuma usar
porque a M PLUS 1 Code tem altura-x baixa. A mesma medida em mono parece menor
do que em sans, e é justamente o mono que carrega os rótulos de campo aqui.

**A assinatura é o carimbo.** Passo aprovado recebe 済 ("encerrado") em
vermelhão, torto como carimbo de verdade sai. É a única cor da interface, e ela
aparece onde significa exatamente o que significa. Em japonês, aprovar é
estampar. O resto ser sumi e papel é o que faz o carimbo ser um acontecimento.

## Onde as coisas estão

| Pasta | O que faz |
|---|---|
| `core/` | base do shell, CSP, SSE, filtro que renderiza e sanitiza o markdown |
| `usuarios/` | conta, cota mensal, conta de visitante e sua expiração |
| `projetos/` | projeto, plano versionado, etapas, passos |
| `mentoria/` | conversa e mensagens; a view de streaming do chat |
| `revisoes/` | submissão de código e veredito por critério |
| `ia/` | prompts, schemas, ferramentas, contabilidade, motores |

A regra de ouro: **nenhuma view importa `anthropic`**. Tudo passa por `ia/motor.py`,
e o motor não toca o ORM, o que depende do banco é montado em `ia/preparo.py`,
do lado síncrono.

## Contas e custo

A chave da Anthropic é **uma só, de quem hospeda o app**, e serve a todas as
contas. Ninguém cadastra chave própria e ninguém é cobrado pelas respostas.

Como quem hospeda paga a conta, o teto de gasto também é dele: sai do `.env`
(`DOJO_IA_LIMITE_MENSAL_USD`) e a página da conta o mostra em leitura, não em
formulário. O gasto é gravado por mensagem e somado no mês
(`usuarios.UsoMensal`); ao bater o limite, o mentor para de responder até a
virada.

Uma conta pode ter teto próprio: o campo `limite mensal próprio` no admin do
Django vale mais que o do `.env` para aquela pessoa. Serve para o caso pontual
de alguém precisar de mais sem que o limite suba para todo mundo. Vazio
significa "usa o do sistema", que é o caso da esmagadora maioria.

**Conta de visitante.** A tela de entrada tem um botão que cria uma conta
descartável, sem cadastro e sem senha utilizável. Ela tem teto próprio e menor
(`DOJO_IA_LIMITE_VISITANTE_USD`), porque é anônima e qualquer um cria uma com um
clique, e é apagada depois de `DOJO_VISITANTE_TTL_HORAS` com tudo o que
produziu. A criação tem trava por IP, senão um laço de requisições enche a
tabela de usuários e torra a cota do provedor, com cota nova a cada conta.

Ela nasce com um projeto pronto dentro (`projetos/exemplo.py`, um encurtador de
links em Flask), porque um painel vazio é a pior primeira tela para quem entrou
justamente para ver o app funcionando. Esse plano é escrito à mão, e não
gerado: aparece na hora e não custa nada de API, que é o gasto que a conta de
visitante existe para conter. Chat, revisão e replanejamento continuam sendo o
mentor de verdade.

**Trava de força bruta.** A tela de entrada conta as tentativas fracassadas por
IP (`DOJO_LOGIN_TENTATIVAS` numa janela de `DOJO_LOGIN_JANELA_SEGUNDOS`) e
devolve 429 ao passar do teto. O contador zera quando alguém entra. Atrás de um
proxy, ligue `DJANGO_TRUST_X_FORWARDED_FOR=1`: sem isso todos os clientes
chegam com o IP do proxy e a trava vale para o conjunto. Com isso ligado sem
proxy na frente é pior, porque aí qualquer um escolhe o próprio identificador e
escapa trocando de valor a cada tentativa.

A limpeza roda em dois momentos: de carona quando um novo visitante entra, e
pelo comando `manage.py limpar_visitantes`, que é o que o timer do systemd
chama. Sem fila
de tarefas: o app não tem uma, e criar uma só para isto seria trocar um problema
pequeno por um serviço a mais para manter de pé.

O prompt do mentor e o contexto do projeto vão com `cache_control`: são o
prefixo estável de toda chamada. Cuidado ao mexer em `ia/prompts.py` ou
`ia/contexto.py`: data, contador ou id de sessão ali dentro quebram o cache em
toda requisição e multiplicam o custo sem nada aparecer na tela. Há um teste
guardando isso (`ia/tests.py::test_prefixo_do_sistema_e_identico_entre_dois_turnos`).

## Manutenção

Um comando diário, agendado pelo `dojo-limpar-visitantes.timer`:

```
manage.py limpar_visitantes
```

Ele apaga as contas de visitante vencidas com tudo o que produziram. A limpeza
também roda de carona quando alguém entra como visitante, então o timer é a rede
de segurança para quando ninguém entra por um tempo.

## Deploy

Instalação direta no servidor, sem Docker: nginx na frente, gunicorn com
`UvicornWorker` num socket unix sob systemd, PostgreSQL e Redis do sistema. O
passo a passo está em [`deploy/provisionar.md`](deploy/provisionar.md), com os
arquivos prontos ao lado:

| | |
|---|---|
| `deploy/dojo.service` | a unidade do gunicorn |
| `deploy/dojo-limpar-visitantes.{service,timer}` | a limpeza diária das contas de visitante |
| `deploy/nginx.conf.exemplo` | o server block |
| `scripts/atualizar.sh` | atualização (código, migrations, estáticos, reinício) |
| `deploy/cd-deploy.sh` | o que o CD roda automaticamente a cada push em `main` que passar no CI |

**Desde que o CD (`.github/workflows/deploy.yml`) foi ligado**, a atualização
de rotina acontece sozinha a cada PR mesclado em `main` que passar no CI —
`deploy/cd-deploy.sh` é disparado por SSH pelo workflow reutilizável
`deploy-django.yml` do `rigst/ci` (RUNBOOK.md seção 7). A branch `main` tem
proteção ativa (checks obrigatórios, sem push direto nem pra admin); mudanças
sempre entram por PR, sem exigir aprovação de terceiros.
`scripts/atualizar.sh` continua valendo pra rodar à mão fora desse fluxo.

Quatro coisas quebram o app se forem esquecidas, e as quatro estão explicadas no
provisionamento:

- **`proxy_buffering off` nas rotas de stream.** Sem isso o nginx acumula a
  resposta inteira e o SSE vira uma espera longa seguida de um bloco de texto.
- **`collectstatic` com `DJANGO_ENV=production`.** Fora de produção o
  `staticfiles.json` não é escrito, e cada página estoura na primeira tag
  `{% static %}`.
- **`DJANGO_USE_X_FORWARDED_PROTO=1`.** O TLS termina no nginx; sem o cabeçalho
  o Django vê http e redireciona para https em laço.
- **`DJANGO_TRUST_X_FORWARDED_FOR=1` atrás do proxy.** Sem ela todo request
  chega como `127.0.0.1` e as travas por IP passam a contar uma máquina só: oito
  senhas erradas de qualquer um fecham a entrada para todo mundo.

Produção também exige um cache compartilhado entre os workers
(`DOJO_REDIS_CACHE_URL`, ou `DOJO_CACHE_NO_BANCO=1` mais `createcachetable`): é
nele que moram as duas travas, e o cache padrão do Django vive dentro de um
processo, o que faria os limites valerem uma vez por worker. O settings recusa
subir sem isso.

O log vai para stderr, que sob systemd é o journal: `journalctl -u dojo -f`. E
há uma sonda em `/saude/`, que toca o banco antes de responder, porque um
processo de pé com a conexão perdida é o estado que uma sonda estática deixa
passar.

## Licença

[**AGPL-3.0**](LICENSE) — Copyright (C) 2026 Rodrigo Caballero Stölben.

Você pode usar, estudar, modificar e redistribuir. A cláusula que caracteriza a
AGPL: se você rodar uma versão modificada como serviço acessível pela rede, os
usuários desse serviço têm direito ao código-fonte correspondente.

O uso da instância hospedada em dojo.stolben.com continua regido pelos Termos de
Uso publicados lá — a licença cobre o software, não o serviço operado pelo autor.

As bibliotecas de terceiros permanecem sob suas próprias licenças; o inventário está
em [docs/LICENCAS-TERCEIROS.md](docs/LICENCAS-TERCEIROS.md), regenerável com:

```bash
./venv/bin/python scripts/licencas_terceiros.py
```

As fontes em `static/fonts/` (Zen Old Mincho, Zen Kaku Gothic New, M PLUS 1 Code,
vendorizadas do Google Fonts — sem CDN, para não vazar o IP de quem visita) usam a
SIL Open Font License 1.1 (`OFL.txt` junto aos arquivos).
