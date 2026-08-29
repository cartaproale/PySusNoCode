# Componentes de terceiros

O **PySusNoCode** é distribuído sob a licença MIT (veja `LICENSE`).

O instalador completo embarca as bibliotecas listadas abaixo, para que a
instalação funcione em redes que bloqueiam o pypi.org — o caso de boa parte
das prefeituras e unidades de saúde. Cada uma continua sob a licença do seu
próprio autor, e o texto integral de cada licença viaja dentro do respectivo
arquivo `.whl`, na pasta `vendor/wheels` da instalação.

Lista gerada automaticamente por `installer/gerar_terceiros.py` em 29/08/2026, a partir dos 122 arquivos que vão no instalador.

## As que pedem atenção

Estas têm licenças recíprocas (*copyleft*). Nenhuma delas impede a
distribuição do PySusNoCode, e nenhuma obriga a mudar a licença do nosso
código — mas todas exigem que se diga que estão aqui e onde encontrar o
código-fonte delas.

| Biblioteca | Versão | Licença | O que isso significa | Código-fonte |
|---|---|---|---|---|
| `certifi` | 2026.7.22 | MPL-2.0 | copyleft fraco, por arquivo | [github.com/certifi/python-certifi](https://github.com/certifi/python-certifi) |
| `pyreaddbc` | 2.0.4 | AGPL-3.0 | copyleft forte, com clausula de rede | [github.com/AlertaDengue/PyReadDBC](https://github.com/AlertaDengue/PyReadDBC) |
| `PySide6_Essentials` | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | copyleft de biblioteca: usar nao contamina o aplicativo | [pyside.org](https://pyside.org) |
| `pysus` | 2.10.6 | GPL | copyleft forte | [github.com/AlertaDengue/PySUS](https://github.com/AlertaDengue/PySUS) |
| `shiboken6` | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | copyleft de biblioteca: usar nao contamina o aplicativo | [pyside.org](https://pyside.org) |
| `tqdm` | 4.70.0 | MPL-2.0 AND MIT | copyleft fraco, por arquivo | [tqdm.github.io](https://tqdm.github.io) |
| `Unidecode` | 1.4.0 | GPL | copyleft forte | [github.com/avian2/unidecode](https://github.com/avian2/unidecode) |

Duas observações sobre a lista acima:

- **O PySusNoCode não se liga à PySUS.** O programa não a importa em momento
  algum; quem a executa é o notebook que você gera, num processo separado.
  O instalador apenas a transporta.
- **PySide6 e shiboken6 são usadas pelo programa**, sob a LGPL. É para isso
  que a LGPL existe: um aplicativo de outra licença pode usá-las, desde que
  o usuário possa substituir a biblioteca — e pode, os arquivos estão soltos
  em `vendor/` e na pasta de instalação.

## Todas as bibliotecas embarcadas

| Biblioteca | Versão | Licença |
|---|---|---|
| `aioftp` | 0.21.4 | Apache-2.0 |
| `annotated-doc` | 0.0.5 | MIT |
| `annotated-types` | 0.8.0 | MIT |
| `anthropic` | 1.2.0 | MIT |
| `anyio` | 4.14.2 | MIT |
| `asttokens` | 3.0.2 | Apache 2.0 |
| `attrs` | 26.1.0 | MIT |
| `bigtree` | 0.12.5 | MIT |
| `boto3` | 1.43.83 | Apache-2.0 |
| `botocore` | 1.43.83 | Apache-2.0 |
| `certifi` | 2026.7.22 | MPL-2.0 |
| `cffi` | 2.1.1 | MIT-0 |
| `chardet` | 7.6.0 | 0BSD |
| `claude-agent-sdk` | 0.2.148 | MIT |
| `click` | 8.5.0 | BSD-3-Clause |
| `colorama` | 0.4.6 | BSD License |
| `comm` | 0.2.3 | BSD 3-Clause License |
| `contourpy` | 1.3.3 | BSD 3-Clause License |
| `cramjam` | 2.12.1 | não declarada |
| `cryptography` | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| `cycler` | 0.12.1 | Copyright (c) 2015, matplotlib project |
| `dateparser` | 1.4.2 | BSD-3-Clause |
| `dbfread` | 2.0.7 | MIT |
| `debugpy` | 1.8.21 | MIT |
| `docstring_parser` | 0.18.0 | MIT |
| `dotenv` | 0.9.9 | UNKNOWN |
| `duckdb` | 1.5.5 | MIT License |
| `duckdb_engine` | 0.17.0 | MIT |
| `et_xmlfile` | 2.0.0 | MIT |
| `executing` | 2.2.1 | MIT |
| `fastjsonschema` | 2.22.2 | BSD-3-Clause |
| `fastparquet` | 2024.11.0 | Apache License 2.0 |
| `fonttools` | 4.63.0 | MIT |
| `fsspec` | 2026.7.0 | BSD-3-Clause |
| `greenlet` | 3.5.5 | MIT AND PSF-2.0 |
| `h11` | 0.16.0 | MIT |
| `httpcore` | 1.0.9 | BSD-3-Clause |
| `httpcore2` | 2.12.0 | BSD-3-Clause |
| `httpx` | 0.28.1 | BSD-3-Clause |
| `httpx2` | 2.12.0 | BSD-3-Clause |
| `humanize` | 4.16.0 | MIT |
| `idna` | 3.19 | BSD-3-Clause |
| `ipykernel` | 7.3.0 | BSD-3-Clause |
| `ipython` | 9.17.0 | BSD-3-Clause |
| `ipython_pygments_lexers` | 1.1.1 | BSD License |
| `jedi` | 0.20.0 | MIT |
| `jiter` | 0.16.0 | MIT |
| `jmespath` | 1.1.0 | MIT |
| `jsonschema` | 4.26.0 | MIT |
| `jsonschema-specifications` | 2025.9.1 | MIT |
| `jupyter_client` | 8.10.0 | BSD 3-Clause License |
| `jupyter_core` | 5.9.1 | BSD-3-Clause |
| `kiwisolver` | 1.5.1 | ========================= |
| `loguru` | 0.6.0 | MIT license |
| `markdown-it-py` | 4.2.0 | MIT License |
| `matplotlib` | 3.11.1 | License agreement for matplotlib versions 1.3.0 and later |
| `matplotlib-inline` | 0.2.2 | BSD-3-Clause |
| `mcp` | 2.1.1 | MIT |
| `mcp-types` | 2.1.1 | MIT |
| `mdurl` | 0.1.2 | MIT License |
| `nbformat` | 5.11.1 | BSD 3-Clause License |
| `nest-asyncio` | 1.6.0 | BSD |
| `nest-asyncio2` | 1.7.2 | BSD |
| `numpy` | 2.5.2 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `openai` | 3.6.0 | Apache-2.0 |
| `openpyxl` | 3.1.5 | MIT |
| `opentelemetry-api` | 1.44.0 | Apache-2.0 |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause |
| `pandas` | 2.3.3 | BSD 3-Clause License |
| `parso` | 0.8.7 | MIT |
| `pillow` | 12.3.0 | MIT-CMU |
| `pip` | 26.2.1 | MIT |
| `platformdirs` | 4.11.5 | MIT |
| `prompt_toolkit` | 3.0.53 | BSD License |
| `psutil` | 7.2.2 | BSD-3-Clause |
| `pure_eval` | 0.2.3 | MIT |
| `pyarrow` | 25.0.1 | Apache-2.0 |
| `pycparser` | 3.0 | BSD-3-Clause |
| `pydantic` | 2.13.5 | MIT |
| `pydantic_core` | 2.46.5 | MIT |
| `Pygments` | 2.21.0 | BSD-2-Clause |
| `PyJWT` | 2.13.0 | MIT |
| `pyparsing` | 3.3.2 | MIT |
| `pyreaddbc` | 2.0.4 | AGPL-3.0 |
| `PySide6_Essentials` | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| `pysus` | 2.10.6 | GPL |
| `python-dateutil` | 2.8.2 | Dual License |
| `python-dotenv` | 1.2.3 | BSD-3-Clause |
| `python-multipart` | 0.0.32 | Apache-2.0 |
| `pytz` | 2026.3.post1 | MIT |
| `pywin32` | 312 | PSF |
| `PyYAML` | 6.0.3 | MIT |
| `pyzmq` | 27.2.0 | BSD-3-Clause |
| `referencing` | 0.37.0 | MIT |
| `regex` | 2026.7.19 | Apache-2.0 AND CNRI-Python |
| `rich` | 15.0.0 | MIT |
| `rpds-py` | 2026.6.3 | MIT |
| `s3transfer` | 0.19.2 | Apache License 2.0 |
| `setuptools` | 84.0.0 | MIT |
| `shellingham` | 1.5.4 | ISC License |
| `shiboken6` | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| `six` | 1.17.0 | MIT |
| `sniffio` | 1.3.1 | MIT OR Apache-2.0 |
| `SQLAlchemy` | 2.0.52 | MIT |
| `sse-starlette` | 3.4.8 | BSD-3-Clause |
| `stack-data` | 0.6.3 | MIT |
| `starlette` | 1.6.0 | BSD-3-Clause |
| `tornado` | 6.5.8 | Apache-2.0 |
| `tqdm` | 4.70.0 | MPL-2.0 AND MIT |
| `traitlets` | 5.16.1 | BSD 3-Clause License |
| `truststore` | 0.10.4 | MIT |
| `typer` | 0.24.2 | MIT |
| `typing-inspection` | 0.4.4 | MIT |
| `typing_extensions` | 4.16.0 | PSF-2.0 |
| `tzdata` | 2026.3 | Apache-2.0 |
| `tzlocal` | 5.4.4 | MIT |
| `Unidecode` | 1.4.0 | GPL |
| `urllib3` | 2.7.0 | MIT |
| `uvicorn` | 0.52.4 | BSD-3-Clause |
| `wcwidth` | 0.8.3 | MIT |
| `wheel` | 0.48.0 | MIT |
| `win32_setctime` | 1.2.0 | MIT license |

---

122 bibliotecas. 119 trazem o texto da licença dentro do próprio arquivo `.whl`.

Sem arquivo de licença embarcado (3): `dbfread`, `et_xmlfile`, `openpyxl`. Para essas, a licença declarada nos metadados é a da tabela acima.

Se você precisar do código-fonte de qualquer componente copyleft e não
conseguir obtê-lo no endereço indicado, abra uma questão em
<https://github.com/cartaproale/PySusNoCode/issues>.
