/* Chat do mentor: envia a pergunta e recebe a resposta token a token.
 *
 * Duas decisões que valem a pena registrar:
 *
 * 1. O EventSource é fechado à mão em `fim` e em `erro`. O padrão dele é
 *    reconectar sozinho quando a conexão cai, e como a pergunta viaja na URL,
 *    reconectar aqui significaria pedir a MESMA resposta de novo, pagando duas
 *    vezes. Reconectar é decisão de quem lê, então vira um botão.
 *
 * 2. Nada aqui usa innerHTML. O texto vem de um modelo de linguagem; ele é
 *    inserido como nó de texto e a formatação leve é montada no DOM.
 */
(function () {
    "use strict";

    var caixa = document.querySelector("[data-chat]");
    if (!caixa) return;

    var fluxo = caixa.querySelector("[data-fluxo]");
    var forma = caixa.querySelector("[data-forma]");
    var campo = caixa.querySelector("[data-pergunta]");
    var enviar = caixa.querySelector("[data-enviar]");
    var rodape = caixa.querySelector("[data-rodape]");
    var fonte = null;

    function rolarParaOFim() {
        fluxo.scrollTop = fluxo.scrollHeight;
    }

    function bolha(classe) {
        var el = document.createElement("div");
        /* `msg--nova` só nas que chegam agora: o histórico já está na tela
         * quando a página carrega, e animá-lo seria desfile sem motivo. */
        el.className = "msg msg--nova msg--" + classe;
        fluxo.appendChild(el);
        return el;
    }

    /* A bolha do mentor tem duas partes: o traço na margem, que ancora o turno
     * visualmente, e a prosa. O texto que chega no stream vai só na segunda. */
    function bolhaDoMentor() {
        var el = bolha("mentor");
        var marca = document.createElement("span");
        marca.className = "msg-marca";
        marca.setAttribute("aria-hidden", "true");
        el.appendChild(marca);
        var prosa = document.createElement("div");
        prosa.className = "prosa";
        el.appendChild(prosa);
        return { bolha: el, prosa: prosa };
    }

    /* Formatação leve do que chega ao vivo: parágrafo, **negrito** e `código`.
     * O markdown completo é renderizado no servidor quando a página recarrega
     * (ver core/templatetags/prosa.py, que também sanitiza). */
    function pintar(destino, texto) {
        destino.textContent = "";
        texto.split(/\n{2,}/).forEach(function (paragrafo) {
            var p = document.createElement("p");
            paragrafo.split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach(function (parte) {
                if (/^\*\*[\s\S]+\*\*$/.test(parte)) {
                    var forte = document.createElement("strong");
                    forte.textContent = parte.slice(2, -2);
                    p.appendChild(forte);
                } else if (/^`[^`]+`$/.test(parte)) {
                    var cod = document.createElement("code");
                    cod.textContent = parte.slice(1, -1);
                    p.appendChild(cod);
                } else if (parte) {
                    p.appendChild(document.createTextNode(parte));
                }
            });
            destino.appendChild(p);
        });
    }

    function ocupado(estado) {
        enviar.classList.toggle("is-busy", estado);
        enviar.disabled = estado;
        fluxo.setAttribute("aria-busy", estado ? "true" : "false");
    }

    function perguntar(texto) {
        var vazio = fluxo.querySelector(".chat-vazio");
        if (vazio) vazio.remove();

        var minha = bolha("aluno");
        minha.appendChild(document.createElement("p")).textContent = texto;

        var turno = bolhaDoMentor();
        var resposta = turno.prosa;
        turno.bolha.classList.add("is-escrevendo");
        var acumulado = "";
        ocupado(true);
        rodape.textContent = "";
        rolarParaOFim();

        var url = caixa.dataset.stream + "?pergunta=" + encodeURIComponent(texto);
        if (caixa.dataset.passo) url += "&passo=" + caixa.dataset.passo;

        fonte = new EventSource(url);

        fonte.addEventListener("delta", function (e) {
            acumulado += JSON.parse(e.data).texto;
            pintar(resposta, acumulado);
            rolarParaOFim();
        });

        fonte.addEventListener("ferramenta", function (e) {
            rodape.textContent = "ajustando o plano (" + JSON.parse(e.data).nome + ")…";
        });

        fonte.addEventListener("fim", function (e) {
            var dados = JSON.parse(e.data);
            fonte.close();
            fonte = null;
            turno.bolha.classList.remove("is-escrevendo");
            ocupado(false);
            rodape.textContent = "US$ " + dados.custo;
            campo.focus();
        });

        fonte.addEventListener("erro", function (e) {
            fonte.close();
            fonte = null;
            turno.bolha.classList.remove("is-escrevendo");
            ocupado(false);
            turno.bolha.remove();
            var aviso = bolha("erro");
            aviso.textContent = JSON.parse(e.data).mensagem;
            rolarParaOFim();
        });

        fonte.onerror = function () {
            if (!fonte) return;
            fonte.close();
            fonte = null;
            turno.bolha.classList.remove("is-escrevendo");
            ocupado(false);
            rodape.textContent = acumulado
                ? "a conexão caiu no meio. O trecho acima foi salvo"
                : "a conexão caiu antes de a resposta começar";
        };
    }

    /* "Estou travado": preenche o começo da pergunta e devolve o cursor. Não
     * envia sozinho. O mentor precisa do sintoma, e só quem travou sabe qual é. */
    var travado = caixa.querySelector("[data-travado]");
    if (travado) {
        travado.addEventListener("click", function () {
            if (!campo.value.trim()) {
                campo.value = "Estou travado neste passo. O que tentei até agora: ";
            }
            ajustarAltura();
            campo.focus();
            campo.setSelectionRange(campo.value.length, campo.value.length);
        });
    }

    /* O campo cresce com o texto até um teto (definido no CSS). Sem isto, uma
     * pergunta de cinco linhas fica rolando dentro de duas. */
    function ajustarAltura() {
        campo.style.height = "auto";
        campo.style.height = campo.scrollHeight + "px";
    }
    campo.addEventListener("input", ajustarAltura);

    forma.addEventListener("submit", function (e) {
        e.preventDefault();
        var texto = campo.value.trim();
        if (!texto || enviar.disabled) return;
        campo.value = "";
        ajustarAltura();
        perguntar(texto);
    });

    /* Enter envia, Shift+Enter quebra linha: o campo é de pergunta, não de
     * redação, e quem escreve código está acostumado com esse par. */
    campo.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            forma.requestSubmit();
        }
    });

    /* Fechar a aba cancela o stream no servidor, que grava o parcial e para de
     * gerar (ver mentoria/views.py). */
    window.addEventListener("pagehide", function () {
        if (fonte) fonte.close();
    });

    rolarParaOFim();
})();
