"""LangChain-based provider for real LLM operator candidate generation."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Dict, List, Optional

from .provider_interface import OperatorEvolutionProvider
from .schemas import GeneratedOperatorDraft

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class LangChainOperatorEvolutionProvider(OperatorEvolutionProvider):
    """Provider that calls an OpenAI-compatible LLM via LangChain.

    Args:
        chat_model: A pre-built :class:`ChatOpenAI` instance.
        raw_response_dir: Optional directory to persist raw LLM responses
            for debugging and reproducibility.
    """

    def __init__(
        self,
        chat_model: ChatOpenAI,
        *,
        raw_response_dir: Optional[Path] = None,
        requested_temperature: float | None = None,
    ) -> None:
        self._chat = chat_model
        self._raw_dir = raw_response_dir
        self.temperature_requested = requested_temperature
        self.temperature_sent = getattr(chat_model, "temperature", requested_temperature)
        self.last_call_metadata: dict[str, object] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "latency_ms": None,
            "estimated_cost_usd": None,
            "temperature_requested": requested_temperature,
            "temperature_sent": self.temperature_sent,
            "temperature_fallback_reason": None,
            "raw_response_candidate_count": None,
            "parsed_candidate_count": None,
            "parse_failure_count": 0,
        }
        if self._raw_dir is not None:
            self._raw_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API (OperatorEvolutionProvider protocol)
    # ------------------------------------------------------------------

    def generate_operator_candidates(
        self,
        prompt: str,
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        return self._call_and_parse(
            prompt=prompt,
            operator_type=operator_type,
            round_id=round_id,
            n=n,
            phase="generate",
        )

    def revise_operator_candidates(
        self,
        prompt: str,
        previous_results: Dict[str, object],
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        return self._call_and_parse(
            prompt=prompt,
            operator_type=operator_type,
            round_id=round_id,
            n=n,
            phase="revise",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_and_parse(
        self,
        *,
        prompt: str,
        operator_type: str,
        round_id: int,
        n: int,
        phase: str,
    ) -> List[GeneratedOperatorDraft]:
        """Send prompt to LLM, parse response into drafts.

        Strategy:
        1. Try JSON array parse.
        2. Fallback: extract markdown code fences.
        3. If all parsing fails, save raw response and return empty list.
        """
        raw_text = self._invoke(prompt)
        self._save_raw(raw_text, operator_type, round_id, phase)

        raw_count = self._raw_candidate_count(raw_text, operator_type)
        drafts = self._try_parse_json(raw_text, operator_type, round_id, n)
        if drafts:
            self.last_call_metadata.update(
                raw_response_candidate_count=raw_count,
                parsed_candidate_count=len(drafts),
                parse_failure_count=0,
            )
            return drafts

        drafts = self._try_parse_code_fences(raw_text, operator_type, round_id, n)
        if drafts:
            self.last_call_metadata.update(
                raw_response_candidate_count=raw_count,
                parsed_candidate_count=len(drafts),
                parse_failure_count=0,
            )
            return drafts

        logger.warning(
            "Failed to parse LLM response for %s round %d (%s). "
            "Raw response saved. Returning empty candidate list.",
            operator_type,
            round_id,
            phase,
        )
        self.last_call_metadata.update(
            raw_response_candidate_count=raw_count,
            parsed_candidate_count=0,
            parse_failure_count=1,
        )
        return []

    def _invoke(self, prompt: str) -> str:
        """Call the LangChain chat model and return the text content."""
        try:
            from langchain_core.messages import HumanMessage
        except ImportError:
            # Keep fake/provider-protocol tests usable without the optional
            # LangChain package.  The real factory still requires langchain-openai.
            class HumanMessage:  # type: ignore[no-redef]
                def __init__(self, content: str) -> None:
                    self.content = content

        started = perf_counter()
        try:
            response = self._chat.invoke([HumanMessage(content=prompt)])
        except Exception as exc:
            if not self._is_temperature_error(exc) or self.temperature_sent is None:
                raise
            self._set_temperature(None)
            response = self._chat.invoke([HumanMessage(content=prompt)])
            self.last_call_metadata["temperature_fallback_reason"] = (
                "provider/model rejected temperature"
            )
        latency_ms = (perf_counter() - started) * 1000.0
        usage = getattr(response, "usage_metadata", None) or {}
        response_metadata = getattr(response, "response_metadata", None) or {}
        if not usage:
            usage = response_metadata.get("token_usage", {}) or response_metadata.get("usage", {}) or {}
        prompt_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        completion_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        total_tokens = usage.get("total_tokens")
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = int(prompt_tokens) + int(completion_tokens)
        self.last_call_metadata = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            # Pricing varies by provider/model; do not fabricate a dollar value.
            "estimated_cost_usd": None,
            "temperature_requested": self.temperature_requested,
            "temperature_sent": self.temperature_sent,
            "temperature_fallback_reason": self.last_call_metadata.get(
                "temperature_fallback_reason"
            ),
            "raw_response_candidate_count": None,
            "parsed_candidate_count": None,
            "parse_failure_count": 0,
        }
        return self._extract_text(response)

    def _set_temperature(self, value: float | None) -> None:
        self.temperature_sent = value
        try:
            self._chat.temperature = value
        except Exception:
            if hasattr(self._chat, "model_copy"):
                self._chat = self._chat.model_copy(update={"temperature": value})

    @staticmethod
    def _is_temperature_error(error: Exception) -> bool:
        message = str(error).lower()
        return "temperature" in message and (
            "unsupported" in message
            or "not support" in message
            or "unknown parameter" in message
            or "invalid parameter" in message
        )

    @staticmethod
    def _extract_text(response: object) -> str:
        helper = getattr(response, "text", None)
        if isinstance(helper, str):
            return helper
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                    continue
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type in {"text", "output_text"} and isinstance(
                        block.get("text"), str
                    ):
                        parts.append(block["text"])
                    continue
                block_type = getattr(block, "type", None)
                block_text = getattr(block, "text", None)
                if block_type in {"text", "output_text"} and isinstance(block_text, str):
                    parts.append(block_text)
            return "".join(parts)
        raise TypeError("provider response did not contain text content")

    @staticmethod
    def _raw_candidate_count(raw_text: str, operator_type: str) -> int | None:
        text = raw_text.strip()
        try:
            parsed = json.loads(re.sub(r"```(?:json)?\s*\n(.*?)```", r"\1", text, flags=re.DOTALL))
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return 1
        if isinstance(parsed, list):
            return len(parsed)
        func_name = "repair" if operator_type == "repair" else "destroy"
        blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        return sum(f"def {func_name}(" in block for block in blocks) or None

    def _save_raw(
        self, raw_text: str, operator_type: str, round_id: int, phase: str
    ) -> None:
        if self._raw_dir is None:
            return
        filename = f"{phase}_{operator_type}_round_{round_id:03d}_raw.txt"
        path = self._raw_dir / filename
        path.write_text(raw_text, encoding="utf-8")
        logger.debug("Saved raw LLM response to %s", path)

    # ------------------------------------------------------------------
    # Parsing strategies
    # ------------------------------------------------------------------

    def _try_parse_json(
        self,
        raw_text: str,
        operator_type: str,
        round_id: int,
        n: int,
    ) -> List[GeneratedOperatorDraft]:
        """Try to parse the response as a JSON array of candidate objects.

        Expected JSON schema per element::

            {
                "name": "...",
                "description": "...",
                "code": "def repair(...):\\n    ..."
            }
        """
        # Extract JSON from possible markdown wrapper
        json_text = raw_text.strip()
        json_match = re.search(r"```(?:json)?\s*\n(.*?)```", json_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1).strip()

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []

        drafts: List[GeneratedOperatorDraft] = []
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict) or "code" not in item:
                continue
            operator_id = f"{operator_type}_r{round_id:03d}_{idx:03d}"
            drafts.append(
                GeneratedOperatorDraft(
                    operator_id=operator_id,
                    operator_type=operator_type,
                    round_id=round_id,
                    name=item.get("name", f"{operator_type}_candidate_{idx}"),
                    description=item.get("description", "LLM-generated candidate"),
                    source="langchain",
                    code=item["code"],
                    module_filename=f"{operator_id}.py",
                )
            )
        return drafts[:n]

    def _try_parse_code_fences(
        self,
        raw_text: str,
        operator_type: str,
        round_id: int,
        n: int,
    ) -> List[GeneratedOperatorDraft]:
        """Fallback: extract Python code blocks from markdown fences."""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        blocks = re.findall(pattern, raw_text, re.DOTALL)
        if not blocks:
            return []

        func_name = "repair" if operator_type == "repair" else "destroy"
        drafts: List[GeneratedOperatorDraft] = []
        for idx, code in enumerate(blocks):
            code = code.strip()
            if f"def {func_name}(" not in code:
                continue
            operator_id = f"{operator_type}_r{round_id:03d}_{idx:03d}"
            drafts.append(
                GeneratedOperatorDraft(
                    operator_id=operator_id,
                    operator_type=operator_type,
                    round_id=round_id,
                    name=f"{operator_type}_candidate_{idx}",
                    description="LLM-generated candidate (code fence)",
                    source="langchain",
                    code=code,
                    module_filename=f"{operator_id}.py",
                )
            )
        return drafts[:n]
