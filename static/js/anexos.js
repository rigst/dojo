/* Mostra os arquivos escolhidos para a revisão e deixa tirar um antes de
 * mandar. O input de arquivo nativo não lista nada sozinho, e sem lista o
 * único jeito de saber o que vai junto é reabrir o seletor.
 */
(function () {
    "use strict";

    var forma = document.querySelector("[data-forma-revisao]");
    if (!forma) return;

    var campo = forma.querySelector("#arquivos");
    var lista = forma.querySelector("[data-anexo-lista]");

    function formatarTamanho(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    /* Tira um arquivo da seleção. `FileList` é somente leitura, então a troca
     * passa por um `DataTransfer` novo com todos os outros dentro. */
    function remover(indice) {
        var dt = new DataTransfer();
        Array.from(campo.files).forEach(function (arquivo, i) {
            if (i !== indice) dt.items.add(arquivo);
        });
        campo.files = dt.files;
        desenhar();
    }

    function desenhar() {
        lista.textContent = "";
        var arquivos = Array.from(campo.files);
        lista.hidden = arquivos.length === 0;

        arquivos.forEach(function (arquivo, indice) {
            var item = document.createElement("li");
            item.className = "anexo-item";

            var nome = document.createElement("span");
            nome.textContent = arquivo.name + " · " + formatarTamanho(arquivo.size);
            item.appendChild(nome);

            var botao = document.createElement("button");
            botao.type = "button";
            botao.className = "anexo-remover";
            botao.setAttribute("aria-label", "Remover " + arquivo.name);
            botao.textContent = "×";
            botao.addEventListener("click", function () {
                remover(indice);
            });
            item.appendChild(botao);

            lista.appendChild(item);
        });
    }

    campo.addEventListener("change", desenhar);
})();
