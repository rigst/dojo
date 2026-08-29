/* Tela de espera enquanto o mentor prepara o próximo passo.
 *
 * Sempre abre a conexão ao carregar: tanto a primeira vez (redirecionada por
 * `passo_concluir`) quanto uma retomada depois de F5 caem aqui e disparam o
 * mesmo stream. O servidor decide sozinho se ainda há o que gerar (ver
 * projetos/views.py:passo_gerar_stream).
 */
(function () {
    "use strict";

    var caixa = document.querySelector("[data-passo-gerando]");
    if (!caixa) return;

    var estado = caixa.querySelector("[data-estado]");
    var decorrido = caixa.querySelector("[data-decorrido]");
    var erro = caixa.querySelector("[data-erro]");
    var espera = caixa.querySelector("[data-espera]");

    function mostrarErro(mensagem) {
        espera.hidden = true;
        erro.hidden = false;
        erro.textContent = mensagem;
    }

    var inicio = Date.now();
    var relogio = setInterval(function () {
        var s = Math.round((Date.now() - inicio) / 1000);
        decorrido.textContent = s + "s";
    }, 1000);

    var fonte = new EventSource(caixa.dataset.stream);

    fonte.addEventListener("fim", function (e) {
        clearInterval(relogio);
        fonte.close();
        estado.textContent = "Pronto. Abrindo o passo…";
        window.location = JSON.parse(e.data).url;
    });

    fonte.addEventListener("erro", function (e) {
        clearInterval(relogio);
        fonte.close();
        mostrarErro(JSON.parse(e.data).mensagem);
    });

    fonte.onerror = function () {
        if (fonte.readyState === EventSource.CLOSED) {
            clearInterval(relogio);
            mostrarErro("A conexão caiu antes de o passo ficar pronto. Recarregue a página para tentar de novo.");
        }
    };
})();
