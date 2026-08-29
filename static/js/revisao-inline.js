/* Revisão inline: intercepta o submit do form de revisão e exibe o
 * resultado no próprio passo, sem navegar para páginas separadas. */
(function () {
    "use strict";

    var secao = document.querySelector("[data-revisao-secao]");
    if (!secao) return;

    var form = secao.querySelector("[data-forma-revisao]");
    var slot = secao.querySelector("[data-revisao-slot]");
    var urlBase = secao.dataset.revisaoInlineBase;

    if (!form || !slot || !urlBase) return;

    function mostrarEspera() {
        slot.innerHTML =
            '<div class="espera">' +
            '<p class="espera-estado" role="status" aria-live="polite">Revisando…</p>' +
            '<div class="ds-progress"><span class="ds-progress-fill espera-barra"></span></div>' +
            "</div>";
        slot.hidden = false;
        form.hidden = true;
    }

    function mostrarErro(mensagem) {
        slot.innerHTML =
            '<p class="auth-erro">' +
            mensagem +
            "</p>" +
            '<button type="button" class="ds-btn" data-revisao-enviar-outro>Tentar de novo</button>';
        slot.hidden = false;
        vincularBotaoOutro();
    }

    function voltarForm() {
        slot.hidden = true;
        slot.innerHTML = "";
        form.hidden = false;
        form.querySelector("textarea") && form.querySelector("textarea").focus();
    }

    function vincularBotaoOutro() {
        var btn = slot.querySelector("[data-revisao-enviar-outro]");
        if (btn) btn.addEventListener("click", voltarForm);
    }

    function mostrarResultado(html) {
        slot.innerHTML = html;
        slot.hidden = false;
        vincularBotaoOutro();
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        var dados = new FormData(form);
        mostrarEspera();

        fetch(form.action, {
            method: "POST",
            body: dados,
            headers: { Accept: "application/json" },
        })
            .then(function (r) {
                return r.json().then(function (body) {
                    if (!r.ok) throw new Error(body.erro || "Erro ao enviar.");
                    return body;
                });
            })
            .then(function (resp) {
                var fonte = new EventSource(resp.stream_url);

                fonte.addEventListener("fim", function (ev) {
                    fonte.close();
                    var id = JSON.parse(ev.data).id;
                    var url = urlBase.replace(/\/0\/$/, "/" + id + "/");
                    fetch(url)
                        .then(function (r) {
                            return r.text();
                        })
                        .then(mostrarResultado)
                        .catch(function () {
                            mostrarErro("Não consegui carregar a revisão.");
                        });
                });

                fonte.addEventListener("erro", function (ev) {
                    fonte.close();
                    mostrarErro(JSON.parse(ev.data).mensagem);
                });

                fonte.onerror = function () {
                    if (fonte.readyState === EventSource.CLOSED) {
                        mostrarErro("A conexão caiu antes de terminar. Tente de novo.");
                    }
                };
            })
            .catch(function (err) {
                mostrarErro(err.message || "Erro ao enviar. Tente de novo.");
            });
    });
})();
