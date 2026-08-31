"""Configuração do Dojo.

Segue o padrão do sistema_arq: um único módulo de settings, com o ambiente
escolhido por DJANGO_ENV e não por arquivo separado. O que muda aqui é a
ausência de Celery. No Dojo toda chamada ao modelo é servida dentro da própria
requisição SSE, então não há fila.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


ENV_FILE = os.getenv("DJANGO_ENV_FILE", "").strip()

if ENV_FILE:
    load_env_file(Path(ENV_FILE))
else:
    load_env_file(BASE_DIR / ".env")

ENV = os.getenv("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"
# `manage.py test` põe "test" no argv; o pytest não põe nada parecido. Sem a
# segunda condição o bloco `if IS_TEST` nunca valeria para a suíte de verdade.
# Três detecções porque cada forma de rodar a suíte deixa um rastro diferente:
# `manage.py test` põe "test" no argv; `pytest` direto vira argv[0]; e
# `python -m pytest` (que é como o venv roda) tem argv[0] = "__main__.py" e só
# se denuncia pelo módulo importado. Sem a terceira, a suíte inteira sai
# tentando falar com a API de verdade.
IS_TEST = (
    "test" in sys.argv
    or Path(sys.argv[0]).name.startswith(("pytest", "py.test"))
    or "pytest" in sys.modules
)


def env_bool(nome, default=False):
    return os.getenv(nome, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(nome, default=""):
    return [item.strip() for item in os.getenv(nome, default).split(",") if item.strip()]


DEFAULT_SECRET_KEY = "dev-only-insecure-secret-key-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY)

if IS_PRODUCTION and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise RuntimeError("Defina DJANGO_SECRET_KEY em produção.")

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

if IS_PRODUCTION:
    if DEBUG:
        raise RuntimeError("DEBUG deve estar desativado em produção.")
    if not os.getenv("DJANGO_ALLOWED_HOSTS", "").strip() or "*" in ALLOWED_HOSTS:
        raise RuntimeError("Defina DJANGO_ALLOWED_HOSTS explicitamente e sem curinga em produção.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "usuarios",
    "projetos",
    "mentoria",
    "revisoes",
    "ia",
    "legal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_headers.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# O Django 6 usa o `cached.Loader` mesmo com DEBUG ligado: ele lê cada template
# uma vez e guarda o compilado no processo. Sob `runserver` isso é invisível,
# porque o autoreload reinicia a cada alteração, mas o Dojo roda em uvicorn (é
# o servidor que aguenta o SSE), e ali o processo não reinicia ao editar um
# .html. O sintoma é uma mudança de template que "não aparece" nem com recarga
# forçada do navegador. Em desenvolvimento, então, os loaders vão explícitos e
# sem cache; em produção o cache volta, que é onde ele serve para alguma coisa.
TEMPLATE_LOADERS = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]
if not DEBUG:
    TEMPLATE_LOADERS = [("django.template.loaders.cached.Loader", TEMPLATE_LOADERS)]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        # APP_DIRS fica desligado porque `loaders` é explícito. O Django recusa
        # os dois juntos. O app_directories.Loader acima faz o mesmo trabalho.
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": TEMPLATE_LOADERS,
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.marca",
                "core.context_processors.navegacao",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Banco de dados
# Alvo do projeto: PostgreSQL (defina DATABASE_URL). Sem ele, cai em SQLite
# para desenvolvimento local rodar sem dependência externa.
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_CONN_MAX_AGE = int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60"))
DB_SSL_REQUIRE = env_bool("DJANGO_DB_SSL_REQUIRE", default=IS_PRODUCTION)

if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=DB_CONN_MAX_AGE,
            ssl_require=DB_SSL_REQUIRE,
        )
    }
else:
    if IS_PRODUCTION:
        raise RuntimeError("Defina DATABASE_URL (PostgreSQL) em produção.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
            "OPTIONS": {"timeout": int(os.getenv("SQLITE_TIMEOUT", "20"))},
        }
    }

# ---------------------------------------------------------------------------
# Cache
#
# O app usa cache para duas coisas, e as duas são controle de segurança: a
# trava por IP na criação de contas de visitante e a trava de força bruta na
# tela de entrada. O padrão do Django é LocMemCache, que vive dentro de um
# processo: com três workers do gunicorn, o contador passa a existir em
# triplicata e o limite configurado vale três vezes.
#
# Por isso produção não aceita o padrão. Redis é o caminho normal; a tabela de
# cache no próprio banco serve quando não se quer subir mais um serviço, e
# custa um `manage.py createcachetable` no deploy.
# ---------------------------------------------------------------------------
REDIS_CACHE_URL = os.getenv("DOJO_REDIS_CACHE_URL", "").strip()
CACHE_NO_BANCO = env_bool("DOJO_CACHE_NO_BANCO", default=False)

if REDIS_CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
        }
    }
elif CACHE_NO_BANCO:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "cache_dojo",
        }
    }
elif IS_PRODUCTION:
    raise RuntimeError(
        "Em produção o cache precisa ser compartilhado entre os workers, senão a "
        "trava de criação de visitantes vale por processo. Defina "
        "DOJO_REDIS_CACHE_URL, ou DOJO_CACHE_NO_BANCO=1 e rode "
        "`manage.py createcachetable`."
    )
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dojo"}}

# ---------------------------------------------------------------------------
# Log
#
# O padrão do Django manda o console para /dev/null quando DEBUG está
# desligado: o handler de console é filtrado por require_debug_true, e o que
# sobra é o mail_admins, que sem ADMINS não escreve em lugar nenhum. Numa
# instalação de produção isso significa erro 500 sem uma linha de traceback.
# Aqui tudo vai para stderr, que sob systemd é o journal.
# ---------------------------------------------------------------------------
LOG_NIVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stderr,
            "formatter": "padrao",
        }
    },
    "root": {"handlers": ["console"], "level": LOG_NIVEL},
    "loggers": {
        # Sem propagate=False o traceback sairia duas vezes, uma pelo logger
        # e outra pela raiz.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "dojo": {"handlers": ["console"], "level": LOG_NIVEL, "propagate": False},
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Nos testes o hasher de produção domina o tempo da suíte e não prova nada.
if IS_TEST:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
DATE_FORMAT = "d/m/Y"
SHORT_DATE_FORMAT = "d/m/Y"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "painel"
LOGOUT_REDIRECT_URL = "login"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

USE_MANIFEST_STATICFILES = env_bool("DJANGO_USE_MANIFEST_STATICFILES", default=IS_PRODUCTION)
if USE_MANIFEST_STATICFILES:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024))

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE", "1209600"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# HSTS e redirect: ligados por padrão em produção, desligados fora dela. Deixar
# o valor fixo aqui quebraria o desenvolvimento em http; deixar de fora faria o
# `check --deploy` reclamar para sempre e ninguém mais olharia a saída dele.
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=IS_PRODUCTION)

if env_bool("DJANGO_USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# MAILERS, e não os EMAIL_* soltos: o Django 6.1 depreciou aqueles oito
# settings e os remove na 7.0. Em desenvolvimento o e-mail vai para o console,
# o que basta para o fluxo de redefinição de senha.
MAILERS = {
    "default": {
        "BACKEND": os.getenv(
            "DJANGO_EMAIL_BACKEND",
            "django.core.mail.backends.smtp.EmailBackend"
            if IS_PRODUCTION
            else "django.core.mail.backends.console.EmailBackend",
        ),
        "OPTIONS": {
            "host": os.getenv("DJANGO_EMAIL_HOST", "localhost"),
            "port": int(os.getenv("DJANGO_EMAIL_PORT", "587")),
            "username": os.getenv("DJANGO_EMAIL_HOST_USER", ""),
            "password": os.getenv("DJANGO_EMAIL_HOST_PASSWORD", ""),
            "use_tls": env_bool("DJANGO_EMAIL_USE_TLS", True),
            "timeout": int(os.getenv("DJANGO_EMAIL_TIMEOUT", "10")),
        },
    }
}
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "Dojo <noreply@localhost>")

ENABLE_CSP = env_bool("DJANGO_ENABLE_CSP", default=IS_PRODUCTION)
# style-src precisa de 'unsafe-inline' por causa das barras de progresso, que
# recebem a largura em atributo style. script-src não: todo script é externo ou
# carrega nonce.
CONTENT_SECURITY_POLICY = os.getenv(
    "DJANGO_CONTENT_SECURITY_POLICY",
    "default-src 'self'; img-src 'self' data:; script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; object-src 'none'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
)

# ---------------------------------------------------------------------------
# Mentoria (Claude API)
# A chave é uma só, de quem hospeda o app, e serve a todas as contas.
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# "fake" devolve respostas fixas sem tocar a rede. É o padrão na suíte de
# testes: teste que depende de chave de API não roda no CI de ninguém.
IA_BACKEND = os.getenv("DOJO_IA_BACKEND", "fake" if IS_TEST else "anthropic").strip()

# Sonnet, sempre e para tudo (briefing, plano, próximo passo, revisão e
# conversa passam todos por `settings.IA_MODELO`, ver ia/motores/anthropic_motor.py):
# é o modelo de custo-benefício da família para orientação passo a passo, e um
# só modelo mantém o cache de prompt (ia/preparo.py) útil entre as chamadas.
IA_MODELO = os.getenv("DOJO_IA_MODELO", "claude-sonnet-5").strip()

# Teto de tokens por resposta. Alto de propósito: a orientação de um passo
# costuma ser longa, e resposta cortada no meio custa uma rodada inteira.
IA_MAX_TOKENS = int(os.getenv("DOJO_IA_MAX_TOKENS", "64000"))

# Teto de gasto por usuário no mês, em dólar. Zero desliga a checagem.
#
# Quem define é quem hospeda o app, não cada pessoa: a chave da Anthropic é uma
# só, do provedor, e é a conta dele que cada resposta consome.
IA_LIMITE_MENSAL_USD = float(os.getenv("DOJO_IA_LIMITE_MENSAL_USD", "10"))

# Teto do que o aluno pode colar de uma vez, em tokens. Acima disso o app
# recusa com orientação, em vez de truncar em silêncio.
IA_MAX_TOKENS_SUBMISSAO = int(os.getenv("DOJO_IA_MAX_TOKENS_SUBMISSAO", "12000"))

# Teto de gasto de uma conta de visitante. Menor que o da conta comum: ela é
# anônima e qualquer pessoa cria uma com um clique.
IA_LIMITE_VISITANTE_USD = float(os.getenv("DOJO_IA_LIMITE_VISITANTE_USD", "0.5"))

# Trava de força bruta na entrada: tentativas fracassadas por IP dentro da
# janela. Oito é folgado para quem esqueceu a senha e apertado para quem está
# testando lista.
LOGIN_TENTATIVAS = int(os.getenv("DOJO_LOGIN_TENTATIVAS", "8"))
LOGIN_JANELA_SEGUNDOS = int(os.getenv("DOJO_LOGIN_JANELA_SEGUNDOS", "900"))

# Só ligue atrás de um proxy que sobrescreve o cabeçalho. Sem proxy, confiar
# no X-Forwarded-For deixa qualquer um escolher o próprio identificador e
# escapar das travas trocando de valor a cada tentativa.
CONFIA_NO_X_FORWARDED_FOR = env_bool("DJANGO_TRUST_X_FORWARDED_FOR", default=False)

# ---------------------------------------------------------------------------
# Conta de visitante
# ---------------------------------------------------------------------------
# Depois deste prazo a conta é apagada com tudo o que produziu.
VISITANTE_TTL_HORAS = int(os.getenv("DOJO_VISITANTE_TTL_HORAS", "48"))

# Trava por IP na criação: sem ela, um laço de requisições enche a tabela de
# usuários e torra a cota do provedor, com cota nova a cada conta.
VISITANTE_LIMITE_POR_JANELA = int(os.getenv("DOJO_VISITANTE_LIMITE", "5"))
VISITANTE_JANELA_SEGUNDOS = int(os.getenv("DOJO_VISITANTE_JANELA_SEGUNDOS", "900"))

# ==============================================================================
# Monitoramento de erros (Sentry) — ativo só quando SENTRY_DSN está definido.
# ==============================================================================

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        from django.core.exceptions import DisallowedHost

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE") or None,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            send_default_pii=False,
            ignore_errors=[DisallowedHost],
        )
    except Exception:
        # Pacote ausente ou integração indisponível (ex.: Celery não instalado):
        # seguimos sem monitoramento, sem quebrar o app.
        pass
