/* "Como fazer": quando o mentor descreve os passos em lista, cada item ganha
 * uma caixa para marcar o que já foi feito, do mesmo jeito e com a mesma
 * regra do "Você terminou quando" (ver static/js/criterios.js).
 *
 * Não é progresso do passo — o servidor nunca sabe disso. É só a pessoa
 * conferindo item por item enquanto trabalha, e a marcação precisa sobreviver
 * a um F5 para servir de alguma coisa.
 */
(function () {
    "use strict";

    var bloco = document.querySelector("[data-como-fazer]");
    if (!bloco) return;

    var itens = bloco.querySelectorAll("li");
    if (!itens.length) return;

    var chave = "dojo-como-fazer-" + bloco.dataset.passo;
    var marcados = {};
    try {
        marcados = JSON.parse(localStorage.getItem(chave) || "{}");
    } catch (e) {
        marcados = {};
    }

    itens.forEach(function (item, indice) {
        // O conteúdo original do item (texto, `código`, o que vier do
        // markdown) migra para dentro do rótulo, com a caixa na frente: o
        // clique em qualquer parte do item marca, não só na caixinha.
        var conteudo = document.createElement("div");
        conteudo.className = "como-item-texto";
        while (item.firstChild) conteudo.appendChild(item.firstChild);

        var caixa = document.createElement("input");
        caixa.type = "checkbox";
        caixa.checked = !!marcados[indice];

        var rotulo = document.createElement("label");
        rotulo.className = "como-item";
        rotulo.appendChild(caixa);
        rotulo.appendChild(conteudo);

        item.appendChild(rotulo);
        item.classList.add("como-marcavel");

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
