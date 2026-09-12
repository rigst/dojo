# Configuração do gunicorn, lida por descoberta: a unidade não passa
# `--config`, e sem ela o gunicorn procura `./gunicorn.conf.py` a partir do
# WorkingDirectory, que é /var/www/dojo.
#
# Existe por um motivo só, e vale registrá-lo porque o sintoma não aponta para
# a causa. A unidade do dojo é a única da frota com `ProtectHome=yes`, e o
# gunicorn 26 abre um socket de controle (para o `gunicornc`) cujo caminho
# padrão cai em `~/.gunicorn/gunicorn.ctl` quando XDG_RUNTIME_DIR não está
# definido — que é o caso sob systemd. Com /home inacessível, o arbiter
# registra a cada reload:
#
#   [ERROR] Control server error: [Errno 13] Permission denied: '/home/rod'
#
# Os workers sobem normalmente: é ruído, não falha. Mas ruído de ERROR no log
# de produção custa atenção toda vez que alguém investiga outra coisa — foi
# exatamente o que aconteceu numa auditoria em 12/09/2026.
#
# A correção não é afrouxar o ProtectHome, que é a proteção que torna o
# sintoma visível aqui e invisível nos outros apps. É apontar o socket para
# /run/dojo, que a própria unidade já cria (`RuntimeDirectory=dojo`, dono
# rod:www-data) e apaga na parada — o lugar certo para um socket efêmero,
# ao lado do dojo.sock que o nginx consome.
control_socket = "/run/dojo/gunicorn.ctl"
