/* "Você terminou quando": marca e desmarca à vontade, guardado no navegador.
 *
 * Não é progresso do passo — o servidor nunca sabe disso. É só a pessoa
 * conferindo os critérios um a um, e a marcação precisa sobreviver a um F5
 * para servir de alguma coisa.
 */
(function () {
    "use strict";

    var lista = document.querySelector("[data-criterios]");
    if (!lista) return;

    var chave = "dojo-criterios-" + lista.dataset.passo;
    var marcados = {};
    try {
        marcados = JSON.parse(localStorage.getItem(chave) || "{}");
    } catch (e) {
        marcados = {};
    }

    lista.querySelectorAll("input[type=checkbox]").forEach(function (caixa) {
        var indice = caixa.dataset.criterio;
        caixa.checked = !!marcados[indice];

        caixa.addEventListener("change", function () {
            marcados[indice] = caixa.checked;
            try {
                localStorage.setItem(chave, JSON.stringify(marcados));
            } catch (e) {
                // Sem storage (aba privada, cota cheia): a marca some no
                // recarregamento, mas continua funcionando na sessão atual.
            }
        });
    });
})();
