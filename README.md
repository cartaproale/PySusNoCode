# PySusNoCode

Aplicativo desktop para **Windows** que permite a profissionais de saúde criarem
análises de dados públicos do **DATASUS** (dengue, mortalidade, internações,
nascimentos, vacinação…) **sem saber programar**, conversando com o Claude —
como no Claude Code, mas com um único propósito: gerar notebooks Python com a
biblioteca [PySUS](https://pysus.readthedocs.io/en/latest/).

## O que ele faz

- 💬 **Chat em português**: você descreve a análise ("casos de dengue em 2024
  por município") e o Claude cria o notebook **passo a passo**, uma célula por vez.
- 🧪 **Autoteste**: cada célula criada é executada automaticamente num kernel
  Python embutido (o mesmo motor do Jupyter/Colab). Se der erro, o aplicativo
  manda o erro de volta ao Claude e **corrige sozinho** (até 3 tentativas).
- 🧠 **Aprende com os erros**: cada correção gera uma "lição" gravada em disco
  e reaproveitada nas próximas conversas (memória entre sessões).
- 📓 **Notebook de verdade**: as células podem ser editadas, executadas uma a
  uma, copiadas individualmente, ou exportadas como **.ipynb** para abrir no
  **Google Colab** sem nenhuma alteração.
- 💾 **Continue de onde parou**: ao salvar, a conversa do chat vai junto,
  dentro do próprio arquivo `.ipynb` (metadados). O botão **“📂 Abrir”**
  restaura o notebook **e** o contexto da conversa; ao fechar com alterações
  não salvas, o aplicativo pergunta se deseja salvar.
- 🔑 **Três formas de conectar**: sua conta **claude.ai** (login do Claude Code,
  botão "Entrar (claude.ai)"), uma chave de API da **Anthropic**, ou uma chave
  de API da **OpenAI** para usar o **GPT**.
- 🎛 **Escolha do modelo**: Claude Opus 5 (padrão), Sonnet 5, Haiku 4.5 e
  Fable 5; ou GPT-5.6 (Terra/Sol/Luna), GPT-5.5 e GPT-5.4 mini quando a conexão
  for pela OpenAI — mais um campo para digitar um modelo GPT novo.
- ⬇ **Aviso de nova versão**: o aplicativo consulta uma vez por dia a página
  oficial de versões e avisa quando há atualização, com um botão que abre o
  download (nada é baixado nem instalado sozinho; pode ser desligado em
  Configurações).
- 🎨 **Acessibilidade (botão "Aparência")**: tema **Claro** ou **Escuro** e
  **tamanho da letra** ajustável (11–24 px) para chat, células e toda a
  interface. Todas as cores de texto são explícitas — o app fica legível
  independentemente do modo claro/escuro do Windows.

## Notebooks de exemplo

Precisa de um ponto de partida? O repositório
**[PySusNoCode-Exemplos](https://github.com/cartaproale/PySusNoCode-Exemplos)**
traz análises prontas (leitos, dengue, mortalidade, nascimentos), todas
validadas com dados reais — é só abrir no Colab e trocar o estado e o ano.

> Nem este repositório nem o de exemplos são a biblioteca **PySUS**: ela é
> mantida pelo AlertaDengue/Fiocruz em
> [AlertaDengue/PySUS](https://github.com/AlertaDengue/PySUS) e é usada aqui
> como dependência.

## Vídeo tutorial

▶ **[Como usar o PySusNoCode (YouTube)](https://youtu.be/MWqOzsnJxtY)** — também
acessível dentro do aplicativo, no botão **“🎥 Tutorial”**.

## Download

**[⬇ Baixar o instalador (Windows 10/11 64 bits)](https://github.com/cartaproale/PySusNoCode/releases/latest/download/PySusNoCode-Setup.exe)**
— publicado em [GitHub Releases](https://github.com/cartaproale/PySusNoCode/releases).

## Instalador para distribuição

Para instalar em qualquer computador Windows 10/11 64 bits, use o instalador
único `installer\Output\PySusNoCode-Setup-1.1.0.exe` (veja
`installer\LEIA-ME-DISTRIBUICAO.md` para publicá-lo no seu site e gerar novas
versões). Ele instala o Python embarcado, todas as bibliotecas e, opcionalmente,
o Claude Code — sem precisar de administrador.

## Como iniciar (nesta pasta de desenvolvimento)

Dê dois cliques em **`PySusNoCode.bat`**.

Na primeira execução ele cria o ambiente Python (pasta `.venv`) e instala as
dependências — demora alguns minutos. Nas execuções seguintes abre direto.

> Pré-requisito: Python 3.10+ instalado (https://python.org). Neste computador
> o ambiente já foi criado e testado com o Python 3.12.

## Conexão com o Claude

Dois modos (mude na barra superior, em "Conexão"):

1. **Conta claude.ai (Claude Code)** — recomendado. Usa o CLI do Claude Code e
   o login da sua conta claude.ai (Pro/Max). Se ainda não estiver logado,
   clique em **"🔑 Entrar (claude.ai)"** e complete o login na janela que abre.
   Se o Claude Code não estiver instalado, use **Configurações → Instalar
   Claude Code**.
2. **API Anthropic (chave)** — informe uma chave de `console.anthropic.com` em
   **Configurações**. Neste modo, para os modelos Opus 5 e Fable 5 o aplicativo
   ativa o *fallback automático de recusa* recomendado pela Anthropic (se o
   modelo recusar por segurança, a mesma solicitação é reexecutada no
   Claude Opus 4.8 dentro da própria chamada).

## Usando no Google Colab

- **💾 Salvar .ipynb** e depois, no [Colab](https://colab.research.google.com),
  `Upload` do arquivo; **ou**
- **📋 Copiar tudo** e colar num notebook vazio.

A primeira célula gerada é sempre `%pip install pysus -q`, então o notebook
funciona em qualquer ambiente.

## Onde ficam os dados do aplicativo

- Configurações e memória de lições: `%APPDATA%\PySusNoCode\`
  (`config.json`, `lessons.json`)
- Notebooks salvos (sugestão padrão): `Documentos\PySusNoCode\`
- Dados baixados do DATASUS (cache do PySUS): `%USERPROFILE%\pysus`

## About (English)

**PySusNoCode** is a Windows desktop app that lets Brazilian health
professionals analyze public health data from DATASUS (Brazil's national
health-data repository) by chatting in Portuguese with an AI (Claude). It
builds Jupyter-compatible notebooks step by step using the open-source
[PySUS](https://pysus.readthedocs.io) library, runs and auto-fixes every cell
in an embedded kernel, and exports Google Colab-ready `.ipynb` files. Licensed
under MIT; installers are built from source by GitHub Actions on every version
tag and published to GitHub Releases.

## Licença

O PySusNoCode é distribuído sob a licença **MIT** (veja [`LICENSE`](LICENSE)).

O instalador embarca 122 bibliotecas de terceiros para funcionar em redes que
bloqueiam o pypi.org. A maioria é permissiva (MIT, BSD, Apache), e sete têm
licença recíproca — entre elas a [PySUS](https://github.com/AlertaDengue/PySUS)
(GPLv3), o [pyreaddbc](https://github.com/AlertaDengue/PyReadDBC) (AGPL-3.0) e o
PySide6 (LGPL-3.0). Nenhuma impede a distribuição nem altera a licença do nosso
código; todas pedem atribuição.

A lista completa, com versão e licença de cada componente, está em
[`TERCEIROS.md`](TERCEIROS.md) — gerada a partir dos próprios arquivos a cada
compilação, por `installer/gerar_terceiros.py`. O texto integral de cada licença
viaja dentro do respectivo `.whl`. No aplicativo instalado, o mesmo resumo abre
em **Configurações → ⚖ Licenças e componentes de terceiros**.

## Estrutura do código

```
pysusnocode/
├── __main__.py        # python -m pysusnocode
├── config.py          # configurações persistentes + localização do CLI
├── lessons.py         # memória de lições aprendidas (aprendizado entre sessões)
├── prompts.py         # prompt de sistema (especialista PySUS 2.x) e prompts de correção
├── protocol.py        # extrai células (###CELULA:...###) e lições das respostas
├── llm.py             # backends: Claude Agent SDK (claude.ai) e API Anthropic
├── kernel.py          # kernel Jupyter embutido (execução real das células)
├── nb.py              # modelo do notebook + exportação .ipynb (Colab)
└── gui/               # interface PySide6 (chat, notebook, células, configurações)
```
