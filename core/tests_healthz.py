"""Sonda de saúde: o que o smoke-test do CD e o nginx enxergam."""

import pytest
from django.core.cache import cache
from django.db import OperationalError, connection

ROTAS = ["/healthz/", "/saude/"]


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_responde_ok_com_banco_e_cache_de_pe(client, rota):
    resposta = client.get(rota)

    assert resposta.status_code == 200
    assert resposta.content == b"ok\n"
    # Sem cache: uma resposta guardada por proxy esconderia a queda.
    assert "no-cache" in resposta["Cache-Control"]


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_banco_fora_vira_503(client, monkeypatch, caplog, rota):
    def explodir():
        raise OperationalError("sem conexão")

    monkeypatch.setattr(connection, "cursor", explodir)

    resposta = client.get(rota)

    assert resposta.status_code == 503
    # Corpo neutro: a rota é pública, e o componente que caiu vai para o log.
    assert resposta.content == b"indisponivel\n"
    assert "healthz: banco indisponível" in caplog.text


@pytest.mark.django_db
def test_cache_que_nao_devolve_o_valor_vira_503(client, monkeypatch, caplog):
    """Com o Redis fora, as travas de força bruta deixam de valer: o app
    responde, mas não está saudável."""
    monkeypatch.setattr(cache, "get", lambda *a, **k: None)

    assert client.get("/healthz/").status_code == 503
    assert "healthz: cache indisponível" in caplog.text


@pytest.mark.django_db
def test_cache_que_levanta_erro_vira_503(client, monkeypatch):
    def explodir(*args, **kwargs):
        raise ConnectionError("redis fora")

    monkeypatch.setattr(cache, "set", explodir)

    assert client.get("/healthz/").status_code == 503


@pytest.mark.django_db
def test_so_aceita_get(client):
    assert client.post("/healthz/").status_code == 405
