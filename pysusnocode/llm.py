"""Backends de conversa com o Claude.

Dois modos:
- AgentSDKBackend: usa o Claude Agent SDK + CLI do Claude Code, com o login da
  conta claude.ai do usuário (mesma autenticação do Claude Code).
- AnthropicAPIBackend: usa a API da Anthropic diretamente, com chave de API.

Ambos expõem `send(...)`, uma chamada BLOQUEANTE pensada para rodar dentro de
uma thread de trabalho da interface.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from .config import BACKEND_AGENT, BACKEND_API, Config, find_claude_cli

OnChunk = Callable[[str], None]


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

        try:
            return asyncio.run(
                self._send_async(user_text, system_prompt, model, on_chunk, cancel)
            )
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(self._friendly(exc)) from exc

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

        cli = find_claude_cli(self.config["cli_path"])
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
    def _friendly(exc: Exception) -> str:
        try:
            from claude_agent_sdk import CLIConnectionError, CLINotFoundError, ProcessError
        except Exception:  # noqa: BLE001
            return f"Erro ao falar com o Claude: {exc}"

        if isinstance(exc, CLINotFoundError):
            return (
                "O Claude Code não está instalado neste computador. Use o botão "
                "“Instalar Claude Code” nas Configurações, ou rode no PowerShell:\n"
                "irm https://claude.ai/install.ps1 | iex"
            )
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
def make_backend(config: Config):
    if config["backend"] == BACKEND_API:
        return AnthropicAPIBackend(config)
    return AgentSDKBackend(config)
