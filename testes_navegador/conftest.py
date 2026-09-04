"""O servidor de verdade para os testes de navegador.

O `live_server` do pytest-django sobe a aplicação em WSGI, e o Dojo depende de
ASGI: o chat e a geração de plano são SSE, que sob
WSGI chegariam em bloco no fim em vez de irem pingando. Testar contra um
servidor diferente do que roda em produção testaria outro app.

Então aqui sobe-se o mesmo uvicorn do desenvolvimento, contra um banco
temporário e com o motor falso, num processo à parte. O fixture é por módulo:
os testes de navegação criam projetos, e os de tela precisam de um banco com
conteúdo previsível.
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
USUARIO = "aluno"
SENHA = "dojo-navegador-1234"


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ambiente(banco):
    ambiente = dict(os.environ)
    ambiente.update(
        {
            "DJANGO_ENV": "development",
            # DEBUG ligado porque é o que faz o app servir os próprios
            # estáticos: sob uvicorn não há runserver para fazer isso, e sem
            # CSS a comparação de telas não teria o que comparar.
            "DJANGO_DEBUG": "True",
            "DJANGO_SECRET_KEY": "chave-so-para-os-testes-de-navegador",
            "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "DATABASE_URL": f"sqlite:///{banco}",
            "DOJO_IA_BACKEND": "fake",
            "ANTHROPIC_API_KEY": "",
            # O subprocesso não pode se achar em teste: IS_TEST muda o motor e
            # o cache, e aqui quem manda nisso é o que está acima.
            "PYTEST_CURRENT_TEST": "",
        }
    )
    ambiente.pop("PYTEST_CURRENT_TEST", None)
    return ambiente


def _esperar(url, processo, segundos=40):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if processo.poll() is not None:
            raise RuntimeError(f"O servidor de teste morreu com código {processo.returncode}.")
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except urllib.error.HTTPError:
            return  # Respondeu, e é só isso que interessa aqui.
        except OSError:
            time.sleep(0.15)
    raise RuntimeError("O servidor de teste não subiu a tempo.")


@pytest.fixture(scope="module")
def servidor():
    pasta = Path(tempfile.mkdtemp(prefix="dojo-navegador-"))
    banco = pasta / "teste.sqlite3"
    ambiente = _ambiente(banco)
    porta = _porta_livre()
    base = f"http://127.0.0.1:{porta}"

    def gerenciar(*argumentos):
        subprocess.run(
            [sys.executable, "manage.py", *argumentos],
            cwd=RAIZ,
            env=ambiente,
            check=True,
            capture_output=True,
        )

    gerenciar("migrate", "--no-input")
    gerenciar("semear_stacks")
    subprocess.run(
        [sys.executable, "testes_navegador/semear.py"],
        cwd=RAIZ,
        env=ambiente,
        check=True,
        capture_output=True,
    )

    processo = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "config.asgi:application",
            "--host",
            "127.0.0.1",
            "--port",
            str(porta),
            "--log-level",
            "warning",
        ],
        cwd=RAIZ,
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _esperar(base + "/", processo)
        yield base
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
        shutil.rmtree(pasta, ignore_errors=True)


@pytest.fixture
def pagina(servidor, page):
    """Uma aba de navegador apontada para o servidor de teste.

    Movimento desligado por duas razões: as animações de entrada tornariam cada
    captura uma corrida contra o relógio, e respeitar `prefers-reduced-motion` é
    justamente uma das coisas que se quer garantir que continuam funcionando.
    """
    page.set_default_timeout(15000)
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 1440, "height": 900})
    return page


@pytest.fixture
def autenticado(pagina, servidor):
    pagina.goto(f"{servidor}/conta/entrar/")
    pagina.fill("#id_username", USUARIO)
    pagina.fill("#id_password", SENHA)
    pagina.click("button[type=submit]")
    # Esperar pelo conteúdo do painel, e não pela URL: um glob de URL casa com
    # a própria tela de entrada e o teste segue como se tivesse entrado.
    pagina.wait_for_selector("text=Seus projetos")
    return pagina


# ---------------------------------------------------------------------------
# Comparação de telas
# ---------------------------------------------------------------------------
# O CSS do app tem regras que dependem da posição na cascata, e o arquivo de
# origem registra que fundi-las quebra dezenas de telas. Isso é o tipo de dano
# que nenhum teste de Python percebe: o servidor responde 200, o HTML está
# certo e a tela está destruída. Comparar pixels é a única rede que pega.

REFERENCIA = Path(__file__).parent / "referencia"
DIFERENCAS = Path(__file__).parent / "diferencas"

# Antialiasing de fonte varia entre execuções mesmo sem mudança nenhuma. A
# folga é pequena de propósito: qualquer alteração real de layout mexe em muito
# mais que isto.
TOLERANCIA = 0.0015


def pytest_addoption(parser):
    parser.addoption(
        "--atualizar-telas",
        action="store_true",
        help="Regrava as capturas de referência em vez de comparar com elas.",
    )


@pytest.fixture
def comparar_tela(request):
    """Captura a tela e confronta com a referência versionada.

    Falhar aqui não significa "está errado": significa "mudou". Olhe a imagem
    de diferença gravada em testes_navegador/diferencas/ e, se a mudança era o
    que você queria, regrave a referência com --atualizar-telas.
    """
    from PIL import Image
    from pixelmatch.contrib.PIL import pixelmatch

    atualizar = request.config.getoption("--atualizar-telas")
    REFERENCIA.mkdir(exist_ok=True)

    def comparar(pagina, nome, mascarar=()):
        # `animations="disabled"` congela transições no estado final; sem isso
        # a captura sai num quadro qualquer da animação de entrada.
        bytes_tela = pagina.screenshot(
            full_page=True,
            animations="disabled",
            caret="hide",
            mask=[pagina.locator(s) for s in mascarar],
        )

        alvo = REFERENCIA / f"{nome}.png"
        if atualizar or not alvo.exists():
            alvo.write_bytes(bytes_tela)
            if not atualizar:
                pytest.skip(f"Referência de '{nome}' criada agora; rode de novo para comparar.")
            return

        import io

        atual = Image.open(io.BytesIO(bytes_tela)).convert("RGB")
        referencia = Image.open(alvo).convert("RGB")

        if atual.size != referencia.size:
            _gravar_falha(nome, atual, None)
            pytest.fail(
                f"'{nome}' mudou de tamanho: {referencia.size} virou {atual.size}. "
                f"A captura nova está em testes_navegador/diferencas/."
            )

        diferenca = Image.new("RGB", atual.size)
        pixels = pixelmatch(atual, referencia, diferenca, includeAA=True, threshold=0.12)
        proporcao = pixels / (atual.size[0] * atual.size[1])

        if proporcao > TOLERANCIA:
            _gravar_falha(nome, atual, diferenca)
            pytest.fail(
                f"'{nome}' mudou em {pixels} pixels ({proporcao:.2%}). "
                f"Veja testes_navegador/diferencas/{nome}-diferenca.png. "
                f"Se a mudança era intencional, rode com --atualizar-telas."
            )

    return comparar


def _gravar_falha(nome, atual, diferenca):
    DIFERENCAS.mkdir(exist_ok=True)
    atual.save(DIFERENCAS / f"{nome}-atual.png")
    if diferenca is not None:
        diferenca.save(DIFERENCAS / f"{nome}-diferenca.png")


def definir_tema(pagina, servidor, valor):
    """Fixa o tema da conta.

    O tema é preferência gravada no usuário, e o banco dos testes de tela vive
    o módulo inteiro: sem fixá-lo, um teste que escurece a tela deixa escuras
    todas as capturas seguintes, e a referência gravada passa a depender da
    ordem em que os testes rodaram.
    """
    pagina.goto(f"{servidor}/conta/")
    pagina.check(f"input[name=tema][value={valor}]")
    pagina.click("text=Salvar tema")
    pagina.wait_for_selector("text=Aparência")

    # Sair da Conta antes de devolver a página: o aviso "Tema atualizado" fica
    # flutuando sobre o conteúdo e entraria na captura. Mensagem do Django é
    # consumida ao ser renderizada, então a navegação seguinte já não a traz.
    pagina.goto(f"{servidor}/")
    pagina.wait_for_selector("text=Seus projetos")
