"""Backends de conversa com o Claude.

Dois modos:
- AgentSDKBackend: usa o Claude Agent SDK + CLI do Claude Code, com o login da
  conta claude.ai do usuário (mesma autenticação do Claude Code).
- AnthropicAPIBackend: usa a API da Anthropic diretamente, com chave de API.

Ambos expõem `send(...)`, uma chamada BLOQUEANTE pensada para rodar dentro de
uma thread de trabalho da interface.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from .config import (
    BACKEND_AGENT,
    BACKEND_API,
    BACKEND_OPENAI,
    Config,
    find_claude_cli,
    listar_claude_clis,
)

OnChunk = Callable[[str], None]

_no_window_patched = False


def _patch_subprocess_no_window() -> None:
    """No Windows, o Agent SDK cria o processo do CLI do Claude Code sem
    CREATE_NO_WINDOW; como o aplicativo roda sem console (pythonw), o Windows
    abre uma janela de console preta por cima do app a cada interação. Este
    patch adiciona a flag na criação do processo — a comunicação continua por
    pipes, só a janela deixa de existir."""
    global _no_window_patched
    if _no_window_patched or sys.platform != "win32":
        return
    import anyio

    original = anyio.open_process

    async def _open_process_sem_janela(*args, **kwargs):
        kwargs["creationflags"] = (
            kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        )
        return await original(*args, **kwargs)

    anyio.open_process = _open_process_sem_janela
    _no_window_patched = True


class LLMError(Exception):
    """Erro amigável, com mensagem em português pronta para exibição."""


# ---------------------------------------------------------------------------
# Backend 1: Claude Agent SDK (conta claude.ai via CLI do Claude Code)
# ---------------------------------------------------------------------------
class AgentSDKBackend:
    name = BACKEND_AGENT

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session_id: str | None = None
        # Qual executável usar. Fica gravado depois que um deles funciona, para
        # não repetir a tentativa que falhou a cada mensagem.
        self._cli_escolhido: str | None = None
        # (caminho, erro) de cada executável tentado na última falha.
        self.erros_por_cli: list[tuple[str | None, str]] = []

    def reset(self) -> None:
        self.session_id = None

    def send(
        self,
        user_text: str,
        system_prompt: str,
        model: str | None,
        on_chunk: OnChunk,
        cancel: threading.Event,
    ) -> str:
        import asyncio

        _patch_subprocess_no_window()
        try:
            return self._tentar_cada_cli(
                lambda: asyncio.run(
                    self._send_async(user_text, system_prompt, model, on_chunk, cancel)
                )
            )
        except LLMError as exc:
            # Sessão restaurada de um notebook antigo pode não existir mais no
            # Claude Code; recomeça a conversa e tenta uma vez sem o resume.
            low = str(exc).lower()
            if self.session_id and any(
                k in low for k in ("session", "conversation", "resume", "sessao")
            ):
                self.session_id = None
                try:
                    return asyncio.run(
                        self._send_async(user_text, system_prompt, model, on_chunk, cancel)
                    )
                except LLMError:
                    raise
                except Exception as exc2:  # noqa: BLE001
                    raise LLMError(self._friendly(exc2)) from exc2
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(self._friendly(exc)) from exc

    def _tentar_cada_cli(self, executar):
        """Roda `executar`, trocando de claude.exe se o processo não iniciar.

        É comum a máquina ter dois: o embutido no SDK e o que o usuário
        instalou. Antes, o aplicativo tentava só o primeiro e, se a criação do
        processo falhasse, anunciava que o Claude Code não estava instalado —
        mesmo com um segundo executável perfeitamente utilizável ao lado.
        """
        try:
            from claude_agent_sdk import CLINotFoundError
        except Exception:  # noqa: BLE001
            return executar()

        candidatos: list[str | None] = list(
            listar_claude_clis(self.config["cli_path"])
        )
        if self._cli_escolhido in candidatos:
            candidatos.remove(self._cli_escolhido)
            candidatos.insert(0, self._cli_escolhido)
        if not candidatos:
            # Nenhum encontrado: deixa o próprio SDK procurar e explicar.
            candidatos = [None]

        falha: Exception | None = None
        # Guarda o erro DE CADA UM. Mostrar só o último escondia metade do
        # diagnóstico: o usuário via a queixa sobre o segundo executável sem
        # saber o que tinha acontecido com o primeiro.
        self.erros_por_cli = []
        for caminho in candidatos:
            self._cli_escolhido = caminho
            try:
                return executar()
            except CLINotFoundError as erro:
                from .diag import registrar

                registrar("claude code nao iniciou", f"{caminho} | {erro}")
                self.erros_por_cli.append((caminho, f"{type(erro).__name__}: {erro}"))
                falha = erro
        self._cli_escolhido = None
        # Viaja junto com a exceção: _friendly é estático e não enxerga o
        # backend, mas precisa contar o que houve com cada executável.
        falha._por_cli = list(self.erros_por_cli)  # type: ignore[attr-defined]
        raise falha  # type: ignore[misc]

    async def _send_async(
        self,
        user_text: str,
        system_prompt: str,
        model: str | None,
        on_chunk: OnChunk,
        cancel: threading.Event,
    ) -> str:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )

        cli = self._cli_escolhido or find_claude_cli(self.config["cli_path"])
        options = ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            tools=[],
            allowed_tools=[],
            max_turns=1,
            resume=self.session_id,
            cli_path=cli,
            cwd=str(Path.home()),
            include_partial_messages=True,
        )

        parts: list[str] = []
        result_error: str | None = None
        try:
            async for message in query(prompt=user_text, options=options):
                if cancel.is_set():
                    break
                if isinstance(message, AssistantMessage):
                    # Mensagens sintéticas de erro (ex.: "Not logged in") vêm
                    # com o campo `error` preenchido — não são resposta real.
                    if getattr(message, "error", None):
                        result_error = " ".join(
                            b.text for b in message.content if isinstance(b, TextBlock)
                        ) or str(getattr(message, "error", ""))
                        continue
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    if message.session_id:
                        self.session_id = message.session_id
                    if message.is_error and not result_error:
                        result_error = message.result or message.subtype
                else:
                    event = getattr(message, "event", None)
                    if isinstance(event, dict) and event.get("type") == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            on_chunk(delta["text"])
        except Exception as exc:  # noqa: BLE001
            if result_error:
                raise LLMError(self._friendly_result(result_error)) from exc
            raise

        if result_error:
            raise LLMError(self._friendly_result(result_error))
        return "".join(parts).strip()

    @staticmethod
    def _friendly_result(result: str) -> str:
        low = result.lower()
        if (
            "not logged in" in low
            or "login" in low
            or "auth" in low
            or "api key" in low
            or "credential" in low
        ):
            return (
                "Você ainda não está logado na sua conta claude.ai neste computador. "
                "Clique em “🔑 Entrar (claude.ai)” na barra superior, complete o "
                "login na janela que abrir (o navegador será aberto) e depois envie "
                "seu pedido novamente."
            )
        return "O Claude Code retornou um erro: " + result

    @staticmethod
    def _explicar_cli(exc: Exception, por_cli=None) -> str:
        """Diz o que realmente houve com o executável do Claude Code.

        O SDK levanta CLINotFoundError sempre que a criação do processo termina
        em FileNotFoundError — e no Windows isso tem mais causas do que "o
        arquivo não existe". Até a 1.8.13 o aplicativo afirmava que o Claude
        Code não estava instalado, mesmo quando o executável estava lá e
        íntegro; o usuário ia instalar de novo o que já tinha.

        `por_cli` traz o erro de CADA executável tentado. Sem isso a mensagem
        mostrava só o último, e quem investigasse não saberia o que aconteceu
        com o primeiro.
        """
        from .config import PASTA_PADRAO_INDISPONIVEL
        from .diag import FALHA_AO_GRAVAR

        achados = listar_claude_clis()
        if not achados:
            return (
                "Não encontrei o Claude Code neste computador. Use o botão "
                "“Instalar Claude Code” nas Configurações, ou rode no "
                "PowerShell:\n"
                "irm https://claude.ai/install.ps1 | iex"
            )

        if por_cli:
            lista = "\n".join(
                f"• {caminho or '(busca do próprio SDK)'}\n   {erro}"
                for caminho, erro in por_cli
            )
        else:
            lista = "\n".join(f"• {c}" for c in achados)
            lista += f"\n\nDetalhe técnico: {exc}"

        # Conta o que foi REALMENTE tentado. Contar `achados` fazia a abertura
        # falar em um executável enquanto a lista abaixo mostrava dois.
        quantos = len(por_cli) if por_cli else len(achados)
        if quantos > 1:
            abertura = (
                "O Claude Code está instalado, mas o Windows não conseguiu "
                f"iniciá-lo. Tentei os {quantos} executáveis que encontrei e "
                "nenhum respondeu:"
            )
        else:
            abertura = (
                "O Claude Code está instalado, mas o Windows não conseguiu "
                "iniciá-lo. O executável que encontrei foi:"
            )

        # Estes dois sintomas costumam aparecer junto com a falha de criar
        # processo, e denunciam um ambiente estragado — não um Claude Code
        # ausente. Dizê-los aqui poupa horas de investigação.
        alertas = ""
        if PASTA_PADRAO_INDISPONIVEL:
            alertas += f"\n\n⚠ {PASTA_PADRAO_INDISPONIVEL}"
        if FALHA_AO_GRAVAR:
            alertas += f"\n\n⚠ {FALHA_AO_GRAVAR}"
        if alertas:
            alertas += (
                "\n\nEsses avisos indicam que o ambiente deste processo está "
                "incompleto. Fechar e abrir o aplicativo costuma resolver."
            )

        return (
            f"{abertura}\n{lista}{alertas}\n\n"
            "O que costuma resolver: feche e abra o PySusNoCode; se persistir, "
            "reinicie o computador — um antivírus ou uma atualização em "
            "andamento podem estar segurando o arquivo. Enquanto isso, você "
            "pode continuar trabalhando pela conexão com chave de API, nas "
            "Configurações."
        )

    @staticmethod
    def _friendly(exc: Exception) -> str:
        try:
            from claude_agent_sdk import CLIConnectionError, CLINotFoundError, ProcessError
        except Exception:  # noqa: BLE001
            return f"Erro ao falar com o Claude: {exc}"

        if isinstance(exc, CLINotFoundError):
            return AgentSDKBackend._explicar_cli(exc, getattr(exc, "_por_cli", None))
        if isinstance(exc, ProcessError):
            detail = f"{exc} {getattr(exc, 'stderr', '') or ''}"[-800:]
            low = detail.lower()
            if (
                "not logged in" in low
                or "log in" in low
                or "login" in low
                or "authent" in low
                or "api key" in low
            ):
                return (
                    "Você ainda não está logado na sua conta claude.ai neste "
                    "computador. Clique em “🔑 Entrar (claude.ai)” na barra superior, "
                    "complete o login na janela que abrir e tente novamente."
                )
            return f"O Claude Code encerrou com erro.\n{detail}"
        if isinstance(exc, CLIConnectionError):
            return f"Não consegui me conectar ao Claude Code: {exc}"
        return f"Erro ao falar com o Claude: {exc}"


# ---------------------------------------------------------------------------
# Backend 2: API da Anthropic (chave de API)
# ---------------------------------------------------------------------------
class AnthropicAPIBackend:
    name = BACKEND_API

    # Modelos com fallback automático de recusa (recomendação da Anthropic).
    _FALLBACK_MODELS = {"claude-fable-5", "claude-opus-5"}

    def __init__(self, config: Config) -> None:
        self.config = config
        self.history: list[dict] = []

    def reset(self) -> None:
        self.history = []

    def send(
        self,
        user_text: str,
        system_prompt: str,
        model: str | None,
        on_chunk: OnChunk,
        cancel: threading.Event,
    ) -> str:
        import anthropic

        model = model or "claude-opus-5"
        api_key = (self.config["api_key"] or "").strip() or None
        try:
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Não consegui criar o cliente da API: {exc}") from exc

        messages = self.history + [{"role": "user", "content": user_text}]
        kwargs: dict = dict(
            model=model,
            max_tokens=16000,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )

        try:
            if model in self._FALLBACK_MODELS:
                stream_ctx = client.beta.messages.stream(
                    betas=["server-side-fallback-2026-06-01"],
                    fallbacks=[{"model": "claude-opus-4-8"}],
                    **kwargs,
                )
            else:
                stream_ctx = client.messages.stream(**kwargs)

            with stream_ctx as stream:
                for text in stream.text_stream:
                    if cancel.is_set():
                        raise LLMError("__CANCELLED__")
                    on_chunk(text)
                final = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMError(
                "Chave de API inválida ou ausente. Abra as Configurações e informe "
                "sua chave da Anthropic (console.anthropic.com), ou mude o modo de "
                "conexão para “Conta claude.ai (Claude Code)”."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError(
                "Limite de requisições atingido na API da Anthropic. Aguarde um "
                "minuto e tente novamente."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"A API da Anthropic retornou um erro: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(
                "Sem conexão com a API da Anthropic. Verifique sua internet."
            ) from exc

        text_out = "".join(
            block.text for block in final.content if block.type == "text"
        ).strip()

        if final.stop_reason == "refusal":
            detail = ""
            if getattr(final, "stop_details", None) is not None:
                detail = f" ({final.stop_details.explanation or final.stop_details.category})"
            raise LLMError(
                "O Claude recusou esta solicitação por questões de segurança"
                + detail
                + ". Tente reformular o pedido."
            )

        self.history = messages + [{"role": "assistant", "content": text_out}]
        return text_out


# ---------------------------------------------------------------------------
# Backend 3: API da OpenAI (GPT)
# ---------------------------------------------------------------------------
class OpenAIBackend:
    name = BACKEND_OPENAI

    # A OpenAI às vezes nega acesso a um modelo de forma intermitente (403
    # model_not_found em parte das requisições, com a mesma chave e modelo).
    # Medido no gpt-5.5: ~60% de recusas alternando com sucessos. Retentamos
    # algumas vezes antes de incomodar o usuário.
    MAX_TENTATIVAS = 4
    ESPERA_ENTRE_TENTATIVAS = 1.5

    def __init__(self, config: Config) -> None:
        self.config = config
        self.history: list[dict] = []

    def reset(self) -> None:
        self.history = []

    def _stream_com_retentativa(
        self,
        client,
        model: str,
        messages: list[dict],
        on_chunk: OnChunk,
        cancel: threading.Event,
    ) -> list[str]:
        """Abre o stream e devolve os pedaços recebidos, retentando quando a
        OpenAI recusa o modelo de forma intermitente. Só retenta enquanto nada
        foi entregue à tela, para nunca duplicar texto."""
        import time

        import openai

        from .diag import descrever_erro_api, registrar

        ultimo: Exception | None = None
        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            parts: list[str] = []
            try:
                stream = client.chat.completions.create(
                    model=model, messages=messages, stream=True
                )
                for chunk in stream:
                    if cancel.is_set():
                        stream.close()
                        break
                    if not chunk.choices:
                        continue
                    piece = getattr(chunk.choices[0].delta, "content", None)
                    if piece:
                        parts.append(piece)
                        on_chunk(piece)
                if tentativa > 1:
                    registrar(
                        "openai: sucesso após retentativa",
                        f"modelo={model} tentativa={tentativa}",
                    )
                return parts
            except (openai.PermissionDeniedError, openai.NotFoundError) as exc:
                codigo, mensagem, req_id = descrever_erro_api(exc)
                registrar(
                    "openai: recusa de modelo",
                    f"modelo={model} tentativa={tentativa}/{self.MAX_TENTATIVAS} "
                    f"status={getattr(exc, 'status_code', '?')} code={codigo} "
                    f"req={req_id} msg={mensagem}",
                )
                ultimo = exc
                if parts or tentativa == self.MAX_TENTATIVAS:
                    raise
                time.sleep(self.ESPERA_ENTRE_TENTATIVAS * tentativa)
        if ultimo is not None:  # pragma: no cover - defensivo
            raise ultimo
        return []

    def send(
        self,
        user_text: str,
        system_prompt: str,
        model: str | None,
        on_chunk: OnChunk,
        cancel: threading.Event,
    ) -> str:
        import openai

        api_key = (self.config["openai_api_key"] or "").strip()
        if not api_key:
            raise LLMError(
                "Informe sua chave da OpenAI em ⚙ Configurações → “Chave de API da "
                "OpenAI”. Você a obtém em platform.openai.com/api-keys (é preciso ter "
                "créditos na conta)."
            )
        # O modelo vem da lista da barra superior, onde o personalizado (se
        # houver) aparece como mais uma opção. Até a versão 1.8.8 o
        # personalizado era imposto aqui, atropelando a escolha do usuário: a
        # barra mostrava um modelo e a requisição usava outro.
        model = model or "gpt-5.6-terra"

        messages = (
            [{"role": "system", "content": system_prompt}]
            + self.history
            + [{"role": "user", "content": user_text}]
        )

        client = openai.OpenAI(api_key=api_key)
        parts: list[str] = []
        try:
            parts = self._stream_com_retentativa(
                client, model, messages, on_chunk, cancel
            )
        except openai.AuthenticationError as exc:
            raise LLMError(
                "Chave da OpenAI inválida. Confira em ⚙ Configurações se a chave foi "
                "colada por inteiro (ela começa com “sk-”). Se apagou a chave, gere "
                "outra em platform.openai.com/api-keys."
            ) from exc
        except (openai.PermissionDeniedError, openai.NotFoundError) as exc:
            from .diag import descrever_erro_api

            codigo, mensagem, req_id = descrever_erro_api(exc)
            texto = (
                f"A OpenAI recusou o modelo “{model}” em todas as "
                f"{self.MAX_TENTATIVAS} tentativas.\n\n"
                "O que costuma resolver:\n"
                "• Escolher outro modelo na barra superior (o GPT-5.6 Terra é o "
                "mais estável) — muitas vezes o problema é só deste modelo;\n"
                "• Conferir se o modelo está liberado para o PROJETO da sua chave: "
                "em platform.openai.com, abra Settings → Project → Limits e veja a "
                "lista de modelos permitidos (chaves que começam com “sk-proj-” "
                "valem apenas para um projeto);\n"
                "• Se a conta é nova, alguns modelos só liberam depois da "
                "verificação da organização.\n\n"
                f"Resposta da OpenAI: {mensagem or '(sem detalhes)'}"
            )
            if codigo:
                texto += f" [{codigo}]"
            if req_id:
                texto += f"\nIdentificador da requisição: {req_id}"
            raise LLMError(texto) from exc
        except openai.RateLimitError as exc:
            raise LLMError(
                "A OpenAI recusou por limite de uso — normalmente isso significa que "
                "a conta está sem créditos. Adicione créditos em "
                "platform.openai.com/settings/organization/billing e tente de novo."
            ) from exc
        except openai.BadRequestError as exc:
            raise LLMError(f"A OpenAI recusou a solicitação: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise LLMError(
                "Sem conexão com a OpenAI. Verifique sua internet."
            ) from exc
        except openai.APIStatusError as exc:
            raise LLMError(f"A OpenAI retornou um erro: {exc}") from exc

        full = "".join(parts).strip()
        if not cancel.is_set():
            self.history = self.history + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": full},
            ]
        return full


# ---------------------------------------------------------------------------
def make_backend(config: Config):
    backend = config["backend"]
    if backend == BACKEND_API:
        return AnthropicAPIBackend(config)
    if backend == BACKEND_OPENAI:
        return OpenAIBackend(config)
    return AgentSDKBackend(config)
