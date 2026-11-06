import pytest
from django.contrib.auth import get_user_model

POLITICA = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


@pytest.fixture
def admin(db):
    return get_user_model().objects.create_superuser("chefe", email="chefe@example.com")


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ["/healthz/", "/conta/entrar/"])
def test_permissions_policy_nas_rotas_publicas(client, rota):
    resposta = client.get(rota)
    assert resposta["Permissions-Policy"] == POLITICA


def test_permissions_policy_no_admin(client, admin):
    client.force_login(admin)
    resposta = client.get("/admin/")
    assert resposta.status_code == 200
    assert resposta["Permissions-Policy"] == POLITICA


@pytest.mark.django_db
def test_permissions_policy_vazia_desliga_o_cabecalho(client, settings):
    settings.PERMISSIONS_POLICY = ""
    assert "Permissions-Policy" not in client.get("/healthz/")


def test_check_deploy_so_silencia_o_preload(settings):
    """W021 calado por decisão de domínio; nenhum outro aviso pode ir junto,
    senão o check --deploy em WARNING do CI deixa de proteger."""
    assert settings.SILENCED_SYSTEM_CHECKS == ["security.W021"]
