"""Registry for built-in and generated destroy/repair operators."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict


@dataclass
class OperatorRegistry:
    repair_ops: Dict[str, Callable] = field(default_factory=dict)
    destroy_ops: Dict[str, Callable] = field(default_factory=dict)

    def register_repair(self, name: str, fn: Callable) -> None:
        self.repair_ops[name] = fn

    def register_destroy(self, name: str, fn: Callable) -> None:
        self.destroy_ops[name] = fn

    def get_repair(self, name: str) -> Callable:
        return self.repair_ops[name]

    def get_destroy(self, name: str) -> Callable:
        return self.destroy_ops[name]

    def repair_names(self):
        return sorted(self.repair_ops.keys())

    def destroy_names(self):
        return sorted(self.destroy_ops.keys())
