#!/usr/bin/env bash
#
# Atualiza a instalação, rodado pelo usuário que roda o serviço:
#
#   /var/www/dojo/scripts/atualizar.sh
#
# O restart no fim precisa de sudo.
set -euo pipefail

# A raiz é a do próprio script, e não um caminho escrito à mão: a instalação
# mora em /var/www/dojo (veja WorkingDirectory em dojo.service) e o /srv/dojo
# que estava aqui matava o script no `cd` da primeira linha. DOJO_RAIZ continua
# mandando, para quem instalar noutro lugar.
RAIZ="${DOJO_RAIZ:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# O ambiente virtual se chama `venv` nesta máquina e `.venv` na convenção mais
# nova; aceitar os dois evita que o nome da pasta decida se o deploy roda.
VENV="$RAIZ/.venv"
[ -d "$VENV" ] || VENV="$RAIZ/venv"

cd "$RAIZ"

# Sem isto o collectstatic roda em modo de desenvolvimento e não gera o
# staticfiles.json. O app sobe, e cada página estoura na primeira tag {% static %}
# por falta de entrada no manifesto.
export DJANGO_ENV=production

echo "==> código"
git pull --ff-only

echo "==> dependências"
"$VENV/bin/pip" install --quiet --upgrade -r requirements.txt

echo "==> migrations"
"$VENV/bin/python" manage.py migrate --noinput

# Só faz sentido quando o cache é a tabela no banco; com Redis o comando não
# existe para rodar. Idempotente: se a tabela já está lá, ele diz e sai.
if grep -qE '^DOJO_CACHE_NO_BANCO=(1|true|yes|on)$' .env 2>/dev/null; then
    echo "==> tabela de cache"
    "$VENV/bin/python" manage.py createcachetable
fi

echo "==> estáticos"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "==> conferência"
"$VENV/bin/python" manage.py check --deploy

echo "==> reinício"
# O reload do gunicorn (HUP) não serve aqui: ele troca os workers, mas o
# ManifestStaticFilesStorage lê o manifesto uma vez por processo, e código novo
# com manifesto velho serve arquivo que não existe mais.
sudo systemctl restart dojo

echo "pronto."
