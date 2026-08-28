# Provisionar o Dojo num servidor

Instalação direta, sem Docker: Debian/Ubuntu com nginx, PostgreSQL e Redis do
próprio sistema, o app num venv sob systemd. Os caminhos assumidos são
`/srv/dojo` para o código e o usuário `dojo`; se mudar, mude junto nos arquivos
de `deploy/`.

## 1. Pacotes e usuário

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential \
    postgresql nginx redis-server certbot python3-certbot-nginx

sudo adduser --system --group --home /srv/dojo --shell /usr/sbin/nologin dojo
```

## 2. Banco

```bash
sudo -u postgres createuser dojo --pwprompt
sudo -u postgres createdb dojo --owner dojo
```

## 3. Código e venv

```bash
sudo -u dojo git clone SEU_REPO /srv/dojo
cd /srv/dojo
sudo -u dojo python3 -m venv .venv
sudo -u dojo .venv/bin/pip install -r requirements.txt
```

## 4. Configuração

```bash
sudo -u dojo cp .env.example .env
sudo -u dojo chmod 600 .env
sudo -u dojo nano .env
```

O mínimo para produção:

```
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=            # python -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_ALLOWED_HOSTS=dojo.exemplo.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://dojo.exemplo.com
DATABASE_URL=postgres://dojo:SENHA@localhost:5432/dojo
DJANGO_DB_SSL_REQUIRE=0       # Postgres local costuma não ter TLS ligado
DOJO_REDIS_CACHE_URL=redis://localhost:6379/0
DJANGO_STATIC_ROOT=/srv/dojo/staticfiles
DJANGO_USE_X_FORWARDED_PROTO=1
DJANGO_TRUST_X_FORWARDED_FOR=1
ANTHROPIC_API_KEY=
```

As quatro linhas que mais dão trabalho se forem esquecidas:

- **`DJANGO_USE_X_FORWARDED_PROTO=1`**: o nginx termina o TLS e fala http com o
  gunicorn. Sem ela o Django vê http, redireciona para https, e o navegador
  entra em laço.
- **`DJANGO_TRUST_X_FORWARDED_FOR=1`**: sem ela todo request chega como
  `127.0.0.1`, e as travas por IP passam a contar uma máquina só: oito senhas
  erradas de qualquer pessoa fecham a entrada para todo mundo. Ligue **apenas**
  com o nginx na frente sobrescrevendo o cabeçalho.
- **`DOJO_REDIS_CACHE_URL`**: é onde moram as travas de força bruta e de
  criação de visitantes. O settings recusa subir em produção sem cache
  compartilhado, porque o padrão do Django vive dentro de um processo e o limite
  passaria a valer uma vez por worker. A alternativa sem Redis é
  `DOJO_CACHE_NO_BANCO=1` mais `manage.py createcachetable`.
- **`DJANGO_DB_SSL_REQUIRE=0`**: em produção o padrão é exigir SSL, e o
  Postgres da mesma máquina normalmente sobe sem TLS.

## 5. Primeira carga

```bash
cd /srv/dojo
sudo -u dojo DJANGO_ENV=production .venv/bin/python manage.py migrate
sudo -u dojo DJANGO_ENV=production .venv/bin/python manage.py semear_stacks
sudo -u dojo DJANGO_ENV=production .venv/bin/python manage.py collectstatic --noinput
sudo -u dojo DJANGO_ENV=production .venv/bin/python manage.py createsuperuser
sudo -u dojo DJANGO_ENV=production .venv/bin/python manage.py check --deploy
```

O `DJANGO_ENV=production` no `collectstatic` não é decoração: fora de produção
o app não usa o `ManifestStaticFilesStorage`, o `staticfiles.json` não é escrito,
e aí cada página estoura na primeira tag `{% static %}` por falta de entrada no
manifesto.

## 6. systemd

```bash
sudo cp deploy/dojo.service /etc/systemd/system/
sudo cp deploy/dojo-limpar-visitantes.service /etc/systemd/system/
sudo cp deploy/dojo-limpar-visitantes.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dojo dojo-limpar-visitantes.timer
sudo systemctl status dojo
```

O timer apaga diariamente as contas de visitante vencidas com tudo o que
produziram. A limpeza também roda de carona quando alguém entra como visitante;
o timer é a rede para quando ninguém entra por um tempo.

## 7. nginx e certificado

```bash
sudo cp deploy/nginx.conf.exemplo /etc/nginx/sites-available/dojo
sudo nano /etc/nginx/sites-available/dojo        # troque o server_name
sudo ln -s /etc/nginx/sites-available/dojo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d dojo.exemplo.com
```

## 8. Conferir

```bash
curl -si https://dojo.exemplo.com/saude/ | head -1     # espera 200
journalctl -u dojo -f
```

E, no navegador, o teste que só o SSE reprova: abra um chat e veja se o texto
chega palavra a palavra. Se chegar de uma vez, no fim, é o `proxy_buffering` do
nginx acumulando a resposta. Confira o bloco das rotas de stream.

## Atualizar depois

```bash
sudo -u dojo /srv/dojo/scripts/atualizar.sh
```

Ele puxa o código, instala dependências, migra, regrava os estáticos, roda o
`check --deploy` e reinicia o serviço.

## Backup

O que importa é o Postgres; o resto se reconstrói do repositório.

```bash
sudo -u postgres pg_dump dojo | gzip > /var/backups/dojo-$(date +%F).sql.gz
```
