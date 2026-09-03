from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from usuarios.models import UsoMensal


@pytest.fixture
def aluno(db):
    return get_user_model().objects.create_user("aluno", password="senha-de-teste-123")


def test_cadastro_cria_conta_e_entra(client, db):
    resposta = client.post(
        "/conta/criar/",
        {
            "username": "novato",
            "password1": "praticar-todo-dia-9",
            "password2": "praticar-todo-dia-9",
        },
    )
    assert resposta.status_code == 302
    assert get_user_model().objects.filter(username="novato").exists()
    assert client.get("/").status_code == 200


def test_uso_mensal_e_unico_por_competencia(aluno, db):
    from django.db import IntegrityError

    UsoMensal.objects.create(usuario=aluno, ano_mes="2026-08")
    with pytest.raises(IntegrityError):
        UsoMensal.objects.create(usuario=aluno, ano_mes="2026-08")


def test_exportar_dados_traz_projeto_e_conversa(client, aluno):
    from mentoria.models import Conversa, Mensagem
    from projetos.models import Projeto

    projeto = Projeto.objects.create(usuario=aluno, titulo="Meu app", objetivo="objetivo")
    conversa = Conversa.objects.create(projeto=projeto)
    Mensagem.objects.create(conversa=conversa, papel="user", conteudo="minha pergunta")

    client.force_login(aluno)
    resposta = client.get("/conta/meus-dados.json")

    import json

    dados = json.loads(resposta.content)
    assert resposta["Content-Disposition"].endswith('filename="dojo-meus-dados.json"')
    assert dados["projetos"][0]["titulo"] == "Meu app"
    assert dados["projetos"][0]["conversa"][0]["conteudo"] == "minha pergunta"


def test_excluir_conta_exige_o_nome_digitado(client, aluno):
    from django.contrib.auth import get_user_model

    client.force_login(aluno)
    client.post("/conta/excluir/", {"confirmacao": "errado"})
    assert get_user_model().objects.filter(pk=aluno.pk).exists()

    client.post("/conta/excluir/", {"confirmacao": "aluno"})
    assert not get_user_model().objects.filter(pk=aluno.pk).exists()


def test_excluir_conta_leva_os_projetos_junto(client, aluno):
    from projetos.models import Projeto

    Projeto.objects.create(usuario=aluno, titulo="some junto", objetivo="x")
    client.force_login(aluno)
    client.post("/conta/excluir/", {"confirmacao": "aluno"})
    assert Projeto.objects.count() == 0


def test_quem_ja_entrou_nao_ve_a_tela_de_login(client, aluno):
    """Sem o redirect, o Django renderiza o formulário de entrada dentro do
    shell do app, com barra lateral, projetos e tudo."""
    client.force_login(aluno)
    resposta = client.get("/conta/entrar/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/"


def test_troca_de_senha_funciona_pela_conta(client, aluno):
    """Antes só existia pelo admin do Django: quem não fosse staff não tinha
    como trocar a própria senha."""
    client.force_login(aluno)
    assert client.get("/conta/senha/").status_code == 200

    resposta = client.post(
        "/conta/senha/",
        {
            "old_password": "senha-de-teste-123",
            "new_password1": "senha-nova-bem-longa-7",
            "new_password2": "senha-nova-bem-longa-7",
        },
    )
    aluno.refresh_from_db()
    assert resposta.status_code == 302
    assert aluno.check_password("senha-nova-bem-longa-7")


def test_recuperacao_de_senha_manda_email(client, aluno, mailoutbox):
    aluno.email = "aluno@exemplo.com"
    aluno.save()

    resposta = client.post("/conta/senha/recuperar/", {"email": "aluno@exemplo.com"})
    assert resposta.status_code == 302
    assert len(mailoutbox) == 1
    assert "senha" in mailoutbox[0].subject.lower()
    assert "/conta/senha/nova/" in mailoutbox[0].body


def test_recuperacao_nao_revela_se_o_email_existe(client, db, mailoutbox):
    """A tela responde igual para e-mail cadastrado e não cadastrado. Senão
    ela vira um verificador de quem tem conta aqui."""
    resposta = client.post("/conta/senha/recuperar/", {"email": "ninguem@exemplo.com"}, follow=True)
    assert resposta.status_code == 200
    assert b"Verifique seu e-mail" in resposta.content
    assert len(mailoutbox) == 0


def test_entrada_oferece_recuperacao_de_senha(client, db):
    conteudo = client.get("/conta/entrar/").content
    assert b"Esqueci minha senha" in conteudo


def test_limite_vem_do_sistema_e_nao_do_usuario(aluno, settings):
    """Quem define o teto é quem hospeda o app: a chave da Anthropic é uma só,
    do provedor, e é a conta dele que cada resposta consome."""
    settings.IA_LIMITE_MENSAL_USD = 10
    settings.IA_LIMITE_VISITANTE_USD = 0.5

    assert float(aluno.limite_mensal_usd) == 10

    aluno.eh_visitante = True
    assert float(aluno.limite_mensal_usd) == 0.5


def test_visitante_entra_sem_cadastro(client, db):
    resposta = client.post("/conta/visitante/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/"

    visitante = get_user_model().objects.get(eh_visitante=True)
    # Sem senha utilizável: a única porta é o botão da tela de entrada.
    assert not visitante.has_usable_password()
    assert client.get("/").status_code == 200


def test_visitante_expirado_some_com_tudo_que_criou(db, settings):
    from datetime import timedelta

    from django.utils import timezone

    from projetos.models import Projeto
    from usuarios.visitantes import criar_visitante, limpar_expirados

    settings.VISITANTE_TTL_HORAS = 48
    visitante = criar_visitante()
    Projeto.objects.create(usuario=visitante, titulo="Rascunho", objetivo="x")

    # Ainda dentro do prazo: nada acontece.
    assert limpar_expirados() == 0

    get_user_model().objects.filter(pk=visitante.pk).update(
        date_joined=timezone.now() - timedelta(hours=49)
    )
    assert limpar_expirados() == 1
    assert not get_user_model().objects.filter(pk=visitante.pk).exists()
    # A cascata leva o projeto junto; não sobra órfão no banco.
    assert Projeto.objects.count() == 0


def test_criacao_de_visitante_tem_trava_por_ip(client, db, settings):
    """Sem a trava, um laço de requisições enche a tabela de usuários e torra a
    cota do provedor, com cota nova a cada conta."""
    from django.core.cache import cache

    cache.clear()
    settings.VISITANTE_LIMITE_POR_JANELA = 2

    for _ in range(2):
        client.post("/conta/visitante/")
        client.post("/conta/sair/")

    resposta = client.post("/conta/visitante/", follow=True)
    assert get_user_model().objects.filter(eh_visitante=True).count() == 2
    assert any("Muitos acessos" in str(m) for m in resposta.context["messages"])


def test_tela_de_entrada_oferece_a_visita(client, db):
    conteudo = client.get("/conta/entrar/").content
    assert b"Entrar como visitante" in conteudo


def test_producao_recusa_subir_sem_cache_compartilhado(monkeypatch):
    """A trava de visitante mora no cache. Com o padrão do Django, que vive
    dentro de um processo, o limite passaria a valer uma vez por worker."""
    import importlib

    for nome, valor in [
        ("DJANGO_ENV", "production"),
        ("DJANGO_DEBUG", "False"),
        ("DJANGO_SECRET_KEY", "chave-longa-o-suficiente-para-producao-passar"),
        ("DJANGO_ALLOWED_HOSTS", "dojo.exemplo.com"),
        ("DATABASE_URL", "postgres://u:p@localhost:5432/dojo"),
        ("DOJO_REDIS_CACHE_URL", ""),
        ("DOJO_CACHE_NO_BANCO", "0"),
        # Sem isto o settings se reconhece como suíte e desliga o modo de
        # produção, que é justamente o que este teste precisa exercitar.
        ("DOJO_SIMULA_BOOT_REAL", "1"),
    ]:
        monkeypatch.setenv(nome, valor)

    import config.settings

    with pytest.raises(RuntimeError, match="cache precisa ser compartilhado"):
        importlib.reload(config.settings)


def test_teto_por_conta_vence_o_do_sistema(db, settings):
    """A exceção existe para levantar o teto de uma pessoa sem levantar o de
    todo mundo, que é o que mexer no .env faria."""
    settings.IA_LIMITE_MENSAL_USD = 10

    usuario = get_user_model().objects.create_user(username="ana", password="x")
    assert usuario.limite_mensal_usd == Decimal("10")
    assert usuario.limite_e_excecao is False

    usuario.limite_proprio_usd = Decimal("42.50")
    assert usuario.limite_mensal_usd == Decimal("42.50")
    assert usuario.limite_e_excecao is True


def test_teto_por_conta_tambem_vale_para_visitante(db, settings):
    settings.IA_LIMITE_VISITANTE_USD = 0.5

    visitante = get_user_model().objects.create_user(username="v", password="x", eh_visitante=True)
    assert visitante.limite_mensal_usd == Decimal("0.5")

    visitante.limite_proprio_usd = Decimal("3")
    assert visitante.limite_mensal_usd == Decimal("3")


def test_entrada_trava_depois_de_erros_seguidos(client, db, settings):
    """Sem a trava, a tela de entrada aceita quantas tentativas vierem, que é o
    alvo de quem varre a internet testando senha."""
    from django.core.cache import cache

    cache.clear()
    settings.LOGIN_TENTATIVAS = 3
    get_user_model().objects.create_user(username="ana", password="senha-certa-1")

    for _ in range(3):
        resposta = client.post("/conta/entrar/", {"username": "ana", "password": "errada"})
        assert resposta.status_code == 200

    bloqueada = client.post("/conta/entrar/", {"username": "ana", "password": "senha-certa-1"})
    assert bloqueada.status_code == 429
    assert "_auth_user_id" not in client.session


def test_entrada_certa_zera_o_contador(client, db, settings):
    """Quem errou a senha duas vezes e acertou na terceira não pode carregar o
    contador para a próxima sessão."""
    from django.core.cache import cache

    from usuarios.seguranca import bloqueado

    cache.clear()
    settings.LOGIN_TENTATIVAS = 3
    get_user_model().objects.create_user(username="ana", password="senha-certa-1")

    client.post("/conta/entrar/", {"username": "ana", "password": "errada"})
    client.post("/conta/entrar/", {"username": "ana", "password": "senha-certa-1"})

    assert "_auth_user_id" in client.session
    assert bloqueado("127.0.0.1") is False


def test_x_forwarded_for_so_e_lido_atras_de_proxy(rf, settings):
    """Confiar no cabeçalho sem proxy na frente deixa qualquer um trocar de
    identificador a cada tentativa e escapar da trava."""
    from usuarios.seguranca import ip_do_pedido

    pedido = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4")

    settings.CONFIA_NO_X_FORWARDED_FOR = False
    assert ip_do_pedido(pedido) == "10.0.0.1"

    settings.CONFIA_NO_X_FORWARDED_FOR = True
    assert ip_do_pedido(pedido) == "1.2.3.4"


def test_visitante_nasce_com_projeto_de_exemplo(client, db):
    """Um painel vazio é a pior primeira tela para quem entrou só para ver o
    app funcionando."""
    from django.core.cache import cache

    from projetos.models import Passo, Projeto

    cache.clear()
    client.post("/conta/visitante/")

    projeto = Projeto.objects.get()
    assert projeto.usuario.eh_visitante
    assert projeto.planos.get(ativo=True).modelo == "exemplo"

    passos = Passo.objects.filter(etapa__plano__projeto=projeto)
    assert passos.count() >= 5
    # A fila precisa nascer com exatamente um passo aberto, senão o projeto não
    # tem "passo da vez" e o botão principal some.
    assert passos.filter(status=Passo.Status.DISPONIVEL).count() == 1


def test_projeto_de_exemplo_nao_gasta_api(db, monkeypatch):
    """Ele é escrito à mão. Se um dia alguém trocá-lo por geração, o custo cai
    sobre quem hospeda o app a cada visita."""
    import ia.motor
    from projetos.exemplo import criar_projeto_exemplo

    def recusa(*args, **kwargs):
        raise AssertionError("o projeto de exemplo não pode chamar o motor")

    for nome in [n for n in dir(ia.motor) if not n.startswith("_")]:
        if callable(getattr(ia.motor, nome)):
            monkeypatch.setattr(ia.motor, nome, recusa, raising=False)

    usuario = get_user_model().objects.create_user(username="ana", password="x")
    criar_projeto_exemplo(usuario)


def test_str_do_uso_mensal_traz_usuario_competencia_e_custo(aluno, db):
    uso = UsoMensal.objects.create(
        usuario=aluno, ano_mes="2026-09", custo_usd=Decimal("1.23"), mensagens=4
    )
    assert str(uso) == f"{aluno} · 2026-09 · US$ 1.23"
