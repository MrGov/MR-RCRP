"""File-based provider for manual/offline operator drafts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .provider_interface import OperatorEvolutionProvider
from .schemas import GeneratedOperatorDraft


class FileOperatorEvolutionProvider(OperatorEvolutionProvider):
    """Provider that exports prompts and reads manually authored candidate files."""

    def __init__(self, *, exchange_dir: Path):
        self.exchange_dir = exchange_dir
        self.exchange_dir.mkdir(parents=True, exist_ok=True)

    def generate_operator_candidates(
        self,
        prompt: str,
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        self._write_prompt(prompt, operator_type, round_id, phase="generate")
        return self._read_drafts(operator_type=operator_type, round_id=round_id)

    def revise_operator_candidates(
        self,
        prompt: str,
        previous_results: Dict[str, object],
        n: int,
        operator_type: str,
        round_id: int,
    ) -> List[GeneratedOperatorDraft]:
        payload = {"prompt": prompt, "previous_results": previous_results}
        self._write_prompt(json.dumps(payload, ensure_ascii=False, indent=2), operator_type, round_id, phase="revise")
        return self._read_drafts(operator_type=operator_type, round_id=round_id)

    def _write_prompt(self, prompt: str, operator_type: str, round_id: int, phase: str) -> None:
        path = self.exchange_dir / f"{phase}_{operator_type}_round_{round_id:03d}_prompt.txt"
        path.write_text(prompt, encoding="utf-8")

    def _read_drafts(self, *, operator_type: str, round_id: int) -> List[GeneratedOperatorDraft]:
        drafts_dir = self.exchange_dir / f"round_{round_id:03d}" / operator_type
        if not drafts_dir.exists():
            return []

        drafts: List[GeneratedOperatorDraft] = []
        for path in sorted(drafts_dir.glob("*.py")):
            operator_id = path.stem
            drafts.append(
                GeneratedOperatorDraft(
                    operator_id=operator_id,
                    operator_type=operator_type,
                    round_id=round_id,
                    name=operator_id,
                    description="loaded from file provider",
                    source="file",
                    code=path.read_text(encoding="utf-8"),
                    module_filename=path.name,
                )
            )
        return drafts
