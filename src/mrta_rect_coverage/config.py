"""Configuration loading utilities."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


@dataclass
class Config:
    """Typed configuration container."""

    instance_path: Path
    constructor: str
    local_search_enabled: bool
    local_search_max_iterations: int
    local_search_use_stronger: bool
    algorithm: str
    alns_iterations: int | None
    alns_acceptance: str
    alns_destroy_fraction: float
    alns_use_dp_aware_insertion: bool
    alns_frozen_operator_registry_path: str
    alns_use_frozen_repair: bool
    alns_use_frozen_destroy: bool
    advisor_mode: str
    visualization_output_dir: Path
    visualization_dpi: int
    alns_profile: str = "B0"
    alns_max_runtime_seconds: float | None = None
    alns_time_per_task: float | None = None
    alns_random_seed: int = 0


def load_config(path: Optional[str | Path] = None) -> Config:
    """Load YAML configuration and return a typed Config object."""

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    with config_path.open("r", encoding="utf-8") as handle:
        raw_config: Dict[str, Any] = yaml.safe_load(handle)
    return _parse_config(raw_config, base_path=config_path.parent)


def _parse_config(raw: Dict[str, Any], base_path: Path) -> Config:
    solver_conf = raw.get("solver", {})
    constructor = solver_conf.get("constructor", "spatial_sort")
    local_search = solver_conf.get("local_search", {})
    alns_conf = solver_conf.get("alns", {})

    instance_path = Path(raw.get("instance_path", "data/R2_T6_0.txt"))
    if not instance_path.is_absolute():
        instance_path = PROJECT_ROOT / instance_path

    vis_conf = raw.get("visualization", {})

    output_dir = Path(vis_conf.get("output_dir", "outputs"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    return Config(
        instance_path=instance_path,
        constructor=constructor,
        local_search_enabled=bool(local_search.get("enabled", True)),
        local_search_max_iterations=int(local_search.get("max_iterations", 100)),
        local_search_use_stronger=bool(local_search.get("use_stronger", False)),
        algorithm=str(solver_conf.get("algorithm", "baseline")),
        alns_iterations=(int(alns_conf.get("iterations", 200)) if alns_conf.get("iterations", 200) is not None else None),
        alns_acceptance=str(alns_conf.get("acceptance", "simulated_annealing" if alns_conf.get("profile", "B0").upper() == "B1" else "improvement_only")),
        alns_destroy_fraction=float(alns_conf.get("destroy_fraction", 0.25)),
        alns_use_dp_aware_insertion=bool(alns_conf.get("use_dp_aware_insertion", False)),
        alns_frozen_operator_registry_path=str(alns_conf.get("frozen_operator_registry_path", "")),
        alns_use_frozen_repair=bool(alns_conf.get("use_frozen_repair", False)),
        alns_use_frozen_destroy=bool(alns_conf.get("use_frozen_destroy", False)),
        advisor_mode=str(alns_conf.get("advisor_mode", "none")),
        visualization_output_dir=output_dir,
        visualization_dpi=int(vis_conf.get("dpi", 120)),
        alns_profile=str(alns_conf.get("profile", "B0")).upper(),
        alns_max_runtime_seconds=(float(alns_conf["max_runtime_seconds"]) if alns_conf.get("max_runtime_seconds") is not None else None),
        alns_time_per_task=(float(alns_conf["time_per_task"]) if alns_conf.get("time_per_task") is not None else None),
        alns_random_seed=int(alns_conf.get("random_seed", 0)),
    )
