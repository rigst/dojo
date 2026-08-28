/* Espera da revisão: abre o stream e leva para o resultado quando ele chega.
 * Mesmo cuidado do chat. O EventSource é fechado à mão, porque reconectar
 * sozinho dispararia uma segunda revisão paga da mesma submissão. */
(function () {
    "use strict";

    var caixa = document.querySelector("[data-revisar]");
    if (!caixa) return;

    var espera = caixa.querySelector("[data-espera]");
    var erro = caixa.querySelector("[data-erro]");
    var fonte = new EventSource(caixa.dataset.stream);

    function falhar(mensagem) {
        espera.hidden = true;
        erro.hidden = false;
        erro.textContent = mensagem;
    }

    fonte.addEventListener("fim", function (e) {
        fonte.close();
        /* O destino vem com um 0 no lugar do id, resolvido pelo {% url %} do
         * template: montar a URL à mão no JS duplicaria a rota. */
        window.location = caixa.dataset.destino.replace(/0\/$/, JSON.parse(e.data).id + "/");
    });

    fonte.addEventListener("erro", function (e) {
        fonte.close();
        falhar(JSON.parse(e.data).mensagem);
    });

    fonte.onerror = function () {
        if (fonte.readyState === EventSource.CLOSED) {
            falhar("A conexão caiu antes de a revisão terminar. Volte ao passo e tente de novo.");
        }
    };
})();
