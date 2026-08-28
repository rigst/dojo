/* Geração do plano: dispara o stream e acompanha a espera.
 *
 * O servidor manda batimentos enquanto o modelo pensa (ver core/sse.py). Aqui
 * eles não geram evento nenhum. A única coisa que a tela precisa saber é que a
 * conexão continua viva, e isso o próprio EventSource já garante ao não
 * disparar `error`. O contador de tempo existe para a espera não parecer travada.
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

    function mostrarErro(mensagem) {
        espera.hidden = true;
        erro.hidden = false;
        erro.textContent = mensagem;
        acoes.hidden = false;
        campo.hidden = false;
    }

    /* As perguntas do mentor, carregadas ao abrir a tela.
     *
     * Se a chamada falhar, a seção some e sobra o campo livre: o briefing
     * melhora o plano, mas não pode ser condição para existir um. */
    var esperaBriefing = caixa.querySelector("[data-briefing-espera]");
    var listaPerguntas = caixa.querySelector("[data-briefing-perguntas]");

    function carregarPerguntas() {
        var fonte = new EventSource(caixa.dataset.briefing);

        fonte.addEventListener("perguntas", function (e) {
            fonte.close();
            esperaBriefing.hidden = true;
            var perguntas = JSON.parse(e.data).perguntas || [];
            if (!perguntas.length) return;

            perguntas.forEach(function (p, i) {
                var campo = document.createElement("div");
                campo.className = "campo";

                var id = "pergunta-" + i;
                var rotulo = document.createElement("label");
                rotulo.setAttribute("for", id);
                rotulo.textContent = p.pergunta;
                campo.appendChild(rotulo);

                var entrada = document.createElement("input");
                entrada.id = id;
                entrada.dataset.resposta = p.pergunta;
                entrada.placeholder = "Uma frase basta";
                campo.appendChild(entrada);

                if (p.porque) {
                    var ajuda = document.createElement("span");
                    ajuda.className = "campo-ajuda";
                    ajuda.textContent = p.porque;
                    campo.appendChild(ajuda);
                }
                listaPerguntas.appendChild(campo);
            });
            listaPerguntas.hidden = false;
        });

        function desistir() {
            fonte.close();
            esperaBriefing.hidden = true;
        }
        fonte.addEventListener("erro", desistir);
        fonte.onerror = function () {
            if (fonte.readyState === EventSource.CLOSED) desistir();
        };
    }

    carregarPerguntas();

    /* O que vai para o mentor: cada pergunta com a resposta ao lado, mais o
     * texto livre. Mandar só as respostas soltas obrigaria o modelo a adivinhar
     * a qual pergunta cada uma pertence. */
    function montarBriefing() {
        var partes = [];
        listaPerguntas.querySelectorAll("[data-resposta]").forEach(function (entrada) {
            var resposta = (entrada.value || "").trim();
            if (resposta) partes.push(entrada.dataset.resposta + "\n" + resposta);
        });
        var livre = (caixa.querySelector("#briefing").value || "").trim();
        if (livre) partes.push("Observações do aluno:\n" + livre);
        return partes.join("\n\n");
    }

    caixa.querySelector("[data-gerar]").addEventListener("click", function () {
        var briefing = montarBriefing();
        campo.hidden = true;
        acoes.hidden = true;
        erro.hidden = true;
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
    });
})();
