# Licenças de terceiros — Dojo

Gerado por `scripts/licencas_terceiros.py` em 2026-08-28 a partir dos pacotes instalados no venv de produção.
Para regenerar: `./venv/bin/python scripts/licencas_terceiros.py`.

O código deste projeto é licenciado sob **AGPL-3.0** (ver `LICENSE`). As bibliotecas abaixo permanecem sob suas licenças originais.

## Dependências diretas

| Pacote | Versão | Licença |
|---|---|---|
| anthropic | 1.2.0 | MIT License |
| asgiref | 3.12.1 | BSD License |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| dj-database-url | 3.1.2 | BSD-3-Clause |
| Django | 6.1 | BSD-3-Clause |
| gunicorn | 26.2.0 | MIT |
| Markdown | 3.10.3 | BSD-3-Clause |
| nh3 | 0.3.7 | MIT |
| psycopg | 3.2.12 | LGPL-3.0-only |
| pydantic | 2.13.4 | MIT |
| redis | 7.1.0 | MIT |
| sqlparse | 0.6.0 | BSD License |
| uvicorn | 0.52.4 | BSD-3-Clause |

## Dependências transitivas

| Pacote | Versão | Licença |
|---|---|---|
| annotated-types | 0.8.0 | MIT |
| anyio | 4.14.2 | MIT |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| docstring_parser | 0.18.0 | MIT License |
| h11 | 0.16.0 | MIT License |
| httpcore2 | 2.12.0 | BSD-3-Clause |
| httpx2 | 2.12.0 | BSD-3-Clause |
| idna | 3.19 | BSD-3-Clause |
| jiter | 0.16.0 | MIT |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic_core | 2.46.4 | MIT |
| sniffio | 1.3.1 | MIT License / Apache Software License |
| truststore | 0.10.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |

## Componentes com licença recíproca (copyleft)

Listados para conferência ao redistribuir o código ou ao combinar com componentes fechados. O uso como biblioteca, sem modificação e sem distribuição do binário, não propaga obrigações de abertura.

| Pacote | Versão | Licença |
|---|---|---|
| psycopg | 3.2.12 | LGPL-3.0-only |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |

## Notas de manutenção

- **Redis**: o servidor em uso é a série 7.0 (BSD-3-Clause). As versões 7.4 a 7.9 passaram a ser RSALv2/SSPL, que não são licenças livres segundo a OSI. Ao atualizar o servidor, reveja esta seção.
- As fontes em `static/fonts/` (Zen Old Mincho, Zen Kaku Gothic New, M PLUS 1 Code) são vendorizadas do Google Fonts sob a SIL Open Font License 1.1 (`OFL.txt` junto aos arquivos), não sob a licença do código.
