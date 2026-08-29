/* Dojo. Comportamentos da interface.
 *
 * Portado do arq-ui.js do sistema_arq, sem as máscaras monetárias, o cronômetro
 * e a precificação ao vivo. O que sobra é o que toda tela usa: avisos que se
 * dispensam, modais, barras de progresso e o estado de envio dos botões.
 *
 * Tudo delegado no document e reaplicado após troca de HTMX: elemento que chega
 * por swap não passa pelo DOMContentLoaded.
 */
(function () {
    "use strict";

    /* Barras de progresso: a largura vem em data-pct para não precisar de style
     * inline em cada elemento. A CSP permite estilo inline, mas escrever a
     * largura no HTML espalha número por template. */
    function preencherBarras(raiz) {
        (raiz || document).querySelectorAll("[data-pct]").forEach(function (el) {
            var pct = Math.max(0, Math.min(100, parseFloat(el.dataset.pct) || 0));
            requestAnimationFrame(function () { el.style.width = pct + "%"; });
        });
    }

    /* Envio em curso: o botão vira barra animada e para de aceitar clique. Sem
     * isso, formulário lento vira dois registros iguais. */
    function marcarEnvio() {
        document.addEventListener("submit", function (e) {
            var botao = e.target.querySelector("button[type=submit], .ds-btn[type=submit]");
            if (botao && !botao.classList.contains("is-busy")) {
                botao.classList.add("is-busy");
            }
        });
    }

    /* Avisos: somem sozinhos depois de um tempo, ou no clique do X. Erro não
     * some: quem precisa ler a mensagem de erro costuma estar lendo devagar. */
    function avisos() {
        var caixa = document.querySelector("[data-avisos]");
        if (!caixa) return;

        function fechar(aviso) {
            aviso.classList.add("is-saindo");
            aviso.addEventListener("animationend", function () { aviso.remove(); }, { once: true });
        }

        caixa.addEventListener("click", function (e) {
            var botao = e.target.closest(".ds-aviso-fechar");
            if (botao) fechar(botao.closest(".ds-aviso"));
        });

        caixa.querySelectorAll(".ds-aviso").forEach(function (aviso) {
            if (aviso.classList.contains("ds-aviso--error")) return;
            setTimeout(function () { if (aviso.isConnected) fechar(aviso); }, 6000);
        });
    }

    /* Modais: <dialog> nativo, aberto por [data-abre="#id"]. */
    function modais() {
        document.addEventListener("click", function (e) {
            var abre = e.target.closest("[data-abre]");
            if (abre) {
                var dlg = document.querySelector(abre.dataset.abre);
                if (dlg) { e.preventDefault(); dlg.showModal(); }
                return;
            }
            var fecha = e.target.closest("[data-fecha]");
            if (fecha) {
                e.preventDefault();
                var alvo = fecha.closest("dialog");
                if (alvo) alvo.close();
            }
        });
    }

    /* Exclusão por HTMX não passa pelo submit do navegador, então o confirm
     * precisa ser explícito. */
    function confirmarExclusao() {
        document.addEventListener("click", function (e) {
            var alvo = e.target.closest("[data-confirmar]");
            if (alvo && !window.confirm(alvo.dataset.confirmar)) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);
    }

    /* Alternador de tema.
     *
     * Quem não está autenticado guarda a escolha no navegador; quem está,
     * guarda no perfil, mas a tela troca na hora, e o POST vai atrás. Esperar
     * a resposta do servidor para trocar a cor deixaria um clique de latência
     * numa ação que é puramente visual.
     *
     * O "acompanhar o sistema" não entra no ciclo: ele é a origem, e sair dele
     * é uma escolha; voltar para ele se faz na página da conta. */
    function tema() {
        var botoes = document.querySelectorAll("[data-tema-botao]");
        if (!botoes.length) return;

        var raiz = document.documentElement;

        function atual() {
            if (raiz.dataset.tema) return raiz.dataset.tema;
            return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
        }

        function persistir(escolha) {
            try { localStorage.setItem("dojo-tema", escolha); } catch (e) {}
            if (raiz.dataset.temaFonte !== "servidor") return;

            var forma = new FormData();
            forma.append("tema", escolha);
            fetch("/conta/tema/", {
                method: "POST",
                body: forma,
                headers: { "X-CSRFToken": biscoito("csrftoken") },
                /* Se o POST falhar, a tela já trocou e a escolha volta na
                 * próxima visita. É o tipo de erro que não vale um alerta. */
            }).catch(function () {});
        }

        botoes.forEach(function (botao) {
            botao.addEventListener("click", function () {
                var novo = atual() === "escuro" ? "claro" : "escuro";
                raiz.dataset.tema = novo;
                persistir(novo);
            });
        });
    }

    function biscoito(nome) {
        var achado = document.cookie.split("; ").find(function (linha) {
            return linha.startsWith(nome + "=");
        });
        return achado ? decodeURIComponent(achado.split("=")[1]) : "";
    }

    /* Atalhos de teclado entre passos: J segue, K volta.
     *
     * J/K e não as setas: seta é navegação de leitura, e roubá-la atrapalha
     * quem está só rolando o texto. O par vem do vim, que é vocabulário de
     * quem programa. O público desta tela. Ignorados enquanto se digita, por
     * motivo óbvio. */
    function atalhosDePasso() {
        var tela = document.querySelector("[data-passo-tela]");
        if (!tela) return;

        document.addEventListener("keydown", function (e) {
            if (e.ctrlKey || e.metaKey || e.altKey) return;

            var foco = document.activeElement;
            if (foco && (foco.matches("input, textarea, select") || foco.isContentEditable)) return;

            var destino =
                e.key === "j" ? tela.dataset.proximo : e.key === "k" ? tela.dataset.anterior : null;
            if (destino) {
                e.preventDefault();
                window.location = destino;
            }
        });
    }

    /* Sidebar recolhível no desktop: persiste estado do checkbox no localStorage. */
    function ladoDoSite() {
        var toggle = document.getElementById("nav-toggle");
        if (!toggle) return;
        try {
            if (localStorage.getItem("dojo-lado") === "recolhido") toggle.checked = true;
        } catch (e) {}
        toggle.addEventListener("change", function () {
            try { localStorage.setItem("dojo-lado", toggle.checked ? "recolhido" : "aberto"); } catch (e) {}
        });
    }

    function iniciar() {
        preencherBarras();
        tema();
        ladoDoSite();
        atalhosDePasso();
        marcarEnvio();
        avisos();
        modais();
        confirmarExclusao();
        document.body.addEventListener("htmx:afterSwap", function (evento) {
            preencherBarras(evento.target);
        });
    }

    if (document.readyState !== "loading") iniciar();
    else document.addEventListener("DOMContentLoaded", iniciar);
})();
