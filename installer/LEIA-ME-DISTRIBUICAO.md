# Distribuindo o PySusNoCode no seu site

## O arquivo para publicar

Depois de compilar, o arquivo único para colocar no site é:

```
installer\Output\PySusNoCode-Setup-1.1.0.exe   (~14 MB)
```

## O que o instalador faz no computador do usuário

1. Instala **por usuário** em `%LOCALAPPDATA%\Programs\PySusNoCode` — **não pede
   senha de administrador**.
2. Extrai um **Python 3.12 embarcado** (oficial do python.org, vem dentro do
   instalador) exclusivo do aplicativo — não interfere em nenhum Python que o
   usuário já tenha.
3. Baixa e instala automaticamente todas as bibliotecas: **pysus**, PySide6,
   anthropic, claude-agent-sdk, jupyter_client, ipykernel, nbformat,
   matplotlib, openpyxl. *(Requer internet nessa etapa; é o que mantém o
   instalador pequeno.)*
4. Opcionalmente (opção marcada por padrão) instala o **Claude Code** oficial
   (`irm https://claude.ai/install.ps1 | iex`), necessário para o login com a
   conta claude.ai.
5. Cria atalhos: **PySusNoCode** (Menu Iniciar e Área de trabalho) e
   **Reparar PySusNoCode** (reexecuta a preparação do ambiente, útil se a
   internet caiu no meio da instalação).
6. Desinstalação normal por "Aplicativos instalados" do Windows. As
   configurações e lições aprendidas do usuário ficam em `%APPDATA%\PySusNoCode`
   e são preservadas.

## Requisitos do computador do usuário

- Windows 10/11 de 64 bits;
- Conexão com a internet (para a instalação das bibliotecas e para usar o app);
- Uma conta **claude.ai** (Pro/Max) *ou* uma chave da API da Anthropic.

## Texto sugerido para a página de download

> **PySusNoCode** — crie análises de dados do DATASUS (dengue, internações,
> mortalidade, vacinação…) conversando em português com uma IA, sem programar.
> Baixe, instale (não precisa de administrador) e peça sua primeira análise.
> Requer Windows 10/11 64 bits, internet e uma conta claude.ai ou chave da API
> Anthropic.

## Como gerar uma nova versão do instalador

1. Edite o código em `pysusnocode\` e ajuste `MyAppVersion` no arquivo
   `installer\PySusNoCode.iss` (e `__version__` em `pysusnocode\__init__.py`).
2. Compile:

```bash
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "C:\Users\Alexandre\Documents\CodigosDoClaudeCode\PySusNoCodeForWindows\installer\PySusNoCode.iss"
```

3. Publique o novo `Output\PySusNoCode-Setup-<versão>.exe`.

## Observações

- **SmartScreen**: por não ser assinado digitalmente, na primeira execução o
  Windows pode mostrar "O Windows protegeu o seu computador" — o usuário clica
  em *Mais informações → Executar assim mesmo*. Para eliminar esse aviso é
  preciso comprar um certificado de assinatura de código (ex.: Certum, Sectigo)
  e assinar o `Setup.exe` com `signtool`.
- Os componentes embutidos vêm de fontes oficiais: Python de python.org,
  get-pip de bootstrap.pypa.io, bibliotecas do PyPI e Claude Code de claude.ai.

