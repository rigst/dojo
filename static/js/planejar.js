/* Geração do plano: dispara o stream e acompanha a espera.
 *
 * O servidor manda batimentos enquanto o modelo pensa (ver core/sse.py). Aqui
 * eles não geram evento nenhum. A única coisa que a tela precisa saber é que a
 * conexão continua viva, e isso o próprio EventSource já garante ao não
 * disparar `error`. O contador de tempo existe para a espera não parecer travada.
 *
 * Se a página carrega com `data-gerando`, uma geração já está em curso (o
 * projeto foi marcado como "gerando" no servidor, ver projetos/views.py) e a
 * tela pula direto para a espera e retoma sozinha: isso é o que faz um F5 no
 * meio da geração não voltar para as perguntas do briefing.
 */
(function () {
    "use strict";

    var caixa = document.querySelector("[data-planejar]");
    if (!caixa) return;

    var espera = caixa.querySelector("[data-espera]");
    var estado = caixa.querySelector("[data-estado]");
    var decorrido = caixa.querySelector("[data-decorrido]");
    var erro = caixa.querySelector("[data-erro]");
    var campo = caixa.querySelector("[data-briefing-campo]");
    var acoes = caixa.querySelector("[data-briefing-acoes]");
    var botaoGerar = caixa.querySelector("[data-gerar]");

    function mostrarErro(mensagem) {
        espera.hidden = true;
        // Numa retomada (F5 no meio da geração), o briefing nem está na
        // página: o jeito mais simples de voltar a um estado consistente é
        // recarregar. O servidor já marcou `erro_geracao`, então a tela que
        // volta mostra o erro e libera o botão de novo.
        if (!campo) {
            window.location.reload();
            return;
        }
        erro.hidden = false;
        erro.textContent = mensagem;
        acoes.hidden = false;
        campo.hidden = false;
        botaoGerar.disabled = false;
    }

    /* As perguntas do mentor, carregadas ao abrir a tela.
     *
     * Se a chamada falhar, a seção some e o botão libera direto: o briefing
     * melhora o plano, mas não pode ser condição para existir um. */
    var esperaBriefing = campo && caixa.querySelector("[data-briefing-espera]");
    var listaPerguntas = campo && caixa.querySelector("[data-briefing-perguntas]");

    function carregarPerguntas() {
        var fonte = new EventSource(caixa.dataset.briefing);

        fonte.addEventListener("perguntas", function (e) {
            fonte.close();
            esperaBriefing.hidden = true;
            var perguntas = JSON.parse(e.data).perguntas || [];
            if (perguntas.length) {
                perguntas.forEach(function (p, i) {
                    var grupo = document.createElement("fieldset");
                    grupo.className = "grupo";

                    var legenda = document.createElement("legend");
                    legenda.textContent = p.pergunta;
                    grupo.appendChild(legenda);

                    var opcoes = document.createElement("div");
                    opcoes.className = "escolhas";

                    (p.opcoes || []).forEach(function (texto) {
                        var rotulo = document.createElement("label");
                        rotulo.className = "escolha escolha--compacta";

                        var entrada = document.createElement("input");
                        entrada.type = "radio";
                        entrada.name = "pergunta-" + i;
                        entrada.value = texto;
                        entrada.dataset.pergunta = p.pergunta;
                        rotulo.appendChild(entrada);

                        var span = document.createElement("span");
                        span.textContent = texto;
                        rotulo.appendChild(span);

                        opcoes.appendChild(rotulo);
                    });
                    grupo.appendChild(opcoes);

                    if (p.porque) {
                        var ajuda = document.createElement("span");
                        ajuda.className = "campo-ajuda";
                        ajuda.textContent = p.porque;
                        grupo.appendChild(ajuda);
                    }
                    listaPerguntas.appendChild(grupo);
                });
                listaPerguntas.hidden = false;
            }
            botaoGerar.disabled = false;
        });

        function desistir() {
            fonte.close();
            esperaBriefing.hidden = true;
            botaoGerar.disabled = false;
        }
        fonte.addEventListener("erro", desistir);
        fonte.onerror = function () {
            if (fonte.readyState === EventSource.CLOSED) desistir();
        };
    }

    /* O que vai para o mentor: cada pergunta com a alternativa escolhida ao
     * lado, mais o texto livre. Mandar só a resposta solta obrigaria o modelo
     * a adivinhar a qual pergunta ela pertence. */
    function montarBriefing() {
        var partes = [];
        if (listaPerguntas) {
            listaPerguntas.querySelectorAll("input[type=radio]:checked").forEach(function (entrada) {
                partes.push(entrada.dataset.pergunta + "\n" + entrada.value);
            });
        }
        var livre = campo && (caixa.querySelector("#briefing").value || "").trim();
        if (livre) partes.push("Observações do aluno:\n" + livre);
        return partes.join("\n\n");
    }

    function iniciarStream(briefing) {
        campo && (campo.hidden = true);
        acoes && (acoes.hidden = true);
        erro && (erro.hidden = true);
        espera.hidden = false;

        var inicio = Date.now();
        var relogio = setInterval(function () {
            var s = Math.round((Date.now() - inicio) / 1000);
            decorrido.textContent = s + "s";
        }, 1000);

        var url = caixa.dataset.stream + "?briefing=" + encodeURIComponent(briefing);
        var fonte = new EventSource(url);

        fonte.addEventListener("fim", function (e) {
            clearInterval(relogio);
            fonte.close();
            estado.textContent = "Pronto. Abrindo o plano…";
            window.location = JSON.parse(e.data).url;
        });

        fonte.addEventListener("erro", function (e) {
            clearInterval(relogio);
            fonte.close();
            mostrarErro(JSON.parse(e.data).mensagem);
        });

        /* `error` do EventSource é queda de conexão, não erro da aplicação:
         * são coisas diferentes e chegam por caminhos diferentes. */
        fonte.onerror = function () {
            if (fonte.readyState === EventSource.CLOSED) {
                clearInterval(relogio);
                mostrarErro("A conexão caiu antes de o plano ficar pronto. Tente de novo.");
            }
        };
    }

    if (caixa.dataset.gerando) {
        // Retomada depois de um F5: nada para perguntar, o briefing já foi
        // enviado da vez anterior e está guardado no servidor.
        iniciarStream(caixa.dataset.briefingPendente || "");
    } else {
        carregarPerguntas();
        botaoGerar.addEventListener("click", function () {
            iniciarStream(montarBriefing());
        });
    }
})();
