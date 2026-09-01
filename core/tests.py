import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


def test_painel_exige_login(client):
    resposta = client.get("/")
    assert resposta.status_code == 302
    assert "/conta/entrar/" in resposta["Location"]


def test_painel_abre_para_quem_entrou(client, aluno):
    client.force_login(aluno)
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert b"Seus projetos" in resposta.content


def test_csp_assina_a_resposta_quando_ligada(client, aluno, settings):
    """A CSP fica desligada em desenvolvimento; o que precisa de teste é que o
    middleware assina de fato quando a variável é ligada. É assim que roda em
    produção, e um cabeçalho ausente lá não aparece em nenhuma tela."""
    settings.ENABLE_CSP = True
    client.force_login(aluno)
    resposta = client.get("/")
    politica = resposta["Content-Security-Policy"]
    assert "nonce-" in politica
    # O nonce do cabeçalho tem de ser o mesmo que assina o <script> da página.
    nonce = politica.split("nonce-")[1].split("'")[0]
    assert f'nonce="{nonce}"'.encode() in resposta.content


def test_tema_escolhido_marca_a_raiz(client, aluno):
    """A escolha explícita vai no atributo do <html>, e não em script: assim ela
    vale antes da primeira pintura e a tela não pisca em branco."""
    aluno.tema = "escuro"
    aluno.save()
    client.force_login(aluno)
    conteudo = client.get("/").content
    assert b'data-tema="escuro"' in conteudo

    aluno.tema = "auto"
    aluno.save()
    conteudo = client.get("/").content
    # Em "auto" não há atributo de tema: quem decide é o CSS pela preferência do
    # sistema. O data-tema-fonte continua lá. É ele que diz ao script do
    # navegador para não sobrepor a escolha de quem está autenticado.
    assert b'data-tema="' not in conteudo
    assert b'data-tema-fonte="servidor"' in conteudo


def test_botao_de_tema_grava_a_escolha(client, aluno):
    client.force_login(aluno)
    resposta = client.post("/conta/tema/", {"tema": "escuro"})
    aluno.refresh_from_db()
    assert resposta.status_code == 204
    assert aluno.tema == "escuro"


def test_botao_de_tema_recusa_valor_inventado(client, aluno):
    client.force_login(aluno)
    assert client.post("/conta/tema/", {"tema": "neon"}).status_code == 400


def test_pagina_404_usa_o_visual_do_app(client, aluno, settings):
    """O 404 padrão do Django é uma página branca com texto de depuração. Como
    ele aparece toda vez que alguém tenta abrir o projeto de outra pessoa, vale
    ser uma tela do app."""
    settings.DEBUG = False
    settings.ALLOWED_HOSTS = ["testserver"]
    client.force_login(aluno)

    resposta = client.get("/rota/que/nao/existe/")
    assert resposta.status_code == 404
    assert b"N\xc3\xa3o h\xc3\xa1 nada aqui" in resposta.content


def test_estatico_em_desenvolvimento_nao_e_cacheado(rf, settings):
    """Sem Cache-Control, o navegador guarda o CSS por conta própria: você
    edita, recarrega e continua vendo a folha antiga, sem nenhum aviso.

    A view é chamada direto porque a rota só é registrada com DEBUG ligado, e
    a suíte roda com DEBUG desligado, o que se quer garantir aqui é o
    cabeçalho, não o roteamento.
    """
    from core.estaticos import servir_sem_cache

    # A view do Django recusa servir com DEBUG desligado, e a suíte roda assim.
    settings.DEBUG = True
    resposta = servir_sem_cache(rf.get("/static/css/dojo.css"), "css/dojo.css")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_saude_responde_sem_autenticacao(client):
    """A sonda é chamada pelo nginx e por quem monitora, que não têm sessão."""
    resposta = client.get("/saude/")

    assert resposta.status_code == 200
    assert resposta.content == b"ok\n"


@pytest.mark.django_db
def test_saude_denuncia_banco_fora(client, monkeypatch):
    """Responder 200 com o banco fora é o defeito que a sonda existe para não
    ter: o processo está de pé e não serve para nada."""
    from django.db import connection

    def explodir():
        raise RuntimeError("sem conexão")

    monkeypatch.setattr(connection, "cursor", explodir)

    assert client.get("/saude/").status_code == 503


def test_sentry_nao_inicializa_durante_a_suite():
    """O .env da raiz é lido em qualquer execução local e traz o SENTRY_DSN de
    produção; sem a guarda IS_TEST, rodar a suíte na máquina mandava evento de
    verdade para o projeto do Sentry. Na CI isso não aparece — lá não há .env."""
    import sentry_sdk
    from django.conf import settings

    assert settings.IS_TEST
    assert not sentry_sdk.get_client().is_active()
