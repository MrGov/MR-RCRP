"""Runner for offline operator evolution experiments.

Supports two invocation styles:

1. Config-driven (recommended)::

    python -m src.mrta_rect_coverage.experiments.operator_evolution_runner \\
        --config configs/operator_evolution_langchain.yaml --freeze-best

2. CLI-only (quick experiments)::

    python -m src.mrta_rect_coverage.experiments.operator_evolution_runner \\
        --provider mock --rounds 2

CLI flags override values loaded from the YAML config file.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml

from ..llm.operator_evolution.evolution_loop import EvolutionLoopConfig, run_evolution_loop
from ..llm.operator_evolution.eligibility_policy import parse_strict_bool
from ..llm.operator_evolution.freezing import freeze_best_operators
from ..llm.operator_evolution.provider_factory import (
    PROVIDER_FILE,
    PROVIDER_LANGCHAIN,
    PROVIDER_MOCK,
    build_provider,
)
from ..visualization.plot_operator_evolution import (
    plot_candidate_leaderboard,
    plot_round_best_trend,
)

_VALID_PROVIDERS = (PROVIDER_MOCK, PROVIDER_FILE, PROVIDER_LANGCHAIN)


def _load_yaml_config(path: Path) -> Dict[str, Any]:
    """Read the ``operator_evolution`` section from a YAML config file."""
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return raw.get("operator_evolution", {})


def _build_evolution_config(
    project_root: Path,
    yaml_cfg: Dict[str, Any],
) -> EvolutionLoopConfig:
    """Construct :class:`EvolutionLoopConfig` from a merged YAML dict."""
    seeds = yaml_cfg.get("seeds", (0, 1))
    if isinstance(seeds, list):
        seeds = tuple(seeds)

    op_types = yaml_cfg.get("operator_types_to_evolve", ("repair", "destroy"))
    if isinstance(op_types, list):
        op_types = tuple(op_types)

    return EvolutionLoopConfig(
        project_root=project_root,
        provider_name=yaml_cfg.get("provider_name", PROVIDER_MOCK),
        round_count=yaml_cfg.get("round_count", 2),
        repair_candidates_per_round=yaml_cfg.get("repair_candidates_per_round", 3),
        destroy_candidates_per_round=yaml_cfg.get("destroy_candidates_per_round", 1),
        benchmark_instance_glob=yaml_cfg.get("benchmark_instance_glob", "data/R*_T*_*.txt"),
        benchmark_instance_list=str(yaml_cfg.get("benchmark_instance_list", "")),
        evidence_report_glob=str(yaml_cfg.get("evidence_report_glob", "")),
        evidence_budget_bytes=int(yaml_cfg.get("evidence_budget_bytes", 2500)),
        seeds=seeds,
        timeout_ms=yaml_cfg.get("timeout_ms", 1000.0),
        top_k_to_keep=yaml_cfg.get("top_k_to_keep", 2),
        operator_types_to_evolve=op_types,
        use_rich_prompts=yaml_cfg.get("use_rich_prompts"),
        allow_unsafe_candidate_execution=parse_strict_bool(
            yaml_cfg.get("allow_unsafe_candidate_execution", False),
            field_name="allow_unsafe_candidate_execution",
        ),
        generated_dir=Path(yaml_cfg.get("generated_dir", "generated_operators")),
        output_dir=Path(yaml_cfg.get("output_dir", "outputs/operator_evolution")),
    )


def run_operator_evolution(
    *,
    project_root: Path,
    config: EvolutionLoopConfig,
    freeze_best: bool,
) -> dict:
    output_dir = project_root / config.output_dir

    provider = build_provider(
        config.provider_name,
        exchange_dir=output_dir / "file_provider_exchange",
        raw_response_dir=output_dir,
    )

    artifacts = run_evolution_loop(provider, config)

    summary_path = Path(artifacts.evolution_summary_path)
    plot_dir = output_dir / "plots"
    plot_round_best_trend(summary_path, plot_dir)
    if artifacts.round_metrics_files:
        plot_candidate_leaderboard(Path(artifacts.round_metrics_files[-1]), plot_dir)

    freeze_result = None
    if freeze_best:
        freeze_result = freeze_best_operators(
            project_root=project_root,
            best_operators_json=Path(artifacts.best_operators_path),
            generated_root=project_root / config.generated_dir,
        )

    return {
        "artifacts": artifacts,
        "freeze_result": freeze_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline operator evolution runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Config-driven (recommended)\n"
            "  %(prog)s --config configs/operator_evolution_langchain.yaml --freeze-best\n\n"
            "  # CLI-only quick run\n"
            "  %(prog)s --provider mock --rounds 1\n"
        ),
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to YAML config file (e.g. configs/operator_evolution_langchain.yaml)",
    )
    parser.add_argument(
        "--provider",
        choices=list(_VALID_PROVIDERS),
        default=None,
        help="Override provider_name from config",
    )
    parser.add_argument("--rounds", type=int, default=None, help="Override round_count")
    parser.add_argument("--repair-candidates", type=int, default=None)
    parser.add_argument("--destroy-candidates", type=int, default=None)
    parser.add_argument("--benchmark-glob", type=str, default=None)
    parser.add_argument("--freeze-best", action="store_true")
    parser.add_argument(
        "--allow-unsafe-candidate-execution",
        action="store_true",
        help=(
            "Explicitly acknowledge risk and allow real-provider code in the "
            "timeout-only subprocess (not a capability sandbox)"
        ),
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]

    # --- Load YAML config (if provided) ---
    yaml_cfg: Dict[str, Any] = {}
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        yaml_cfg = _load_yaml_config(config_path)

    # --- CLI overrides take precedence ---
    if args.provider is not None:
        yaml_cfg["provider_name"] = args.provider
    if args.rounds is not None:
        yaml_cfg["round_count"] = args.rounds
    if args.repair_candidates is not None:
        yaml_cfg["repair_candidates_per_round"] = args.repair_candidates
    if args.destroy_candidates is not None:
        yaml_cfg["destroy_candidates_per_round"] = args.destroy_candidates
    if args.benchmark_glob is not None:
        yaml_cfg["benchmark_instance_glob"] = args.benchmark_glob
    if args.allow_unsafe_candidate_execution:
        yaml_cfg["allow_unsafe_candidate_execution"] = True

    config = _build_evolution_config(project_root, yaml_cfg)
    result = run_operator_evolution(
        project_root=project_root,
        config=config,
        freeze_best=args.freeze_best,
    )

    artifacts = result["artifacts"]
    print("Operator evolution completed.")
    print(f"Summary: {artifacts.evolution_summary_path}")
    print(f"Best operators: {artifacts.best_operators_path}")
    if result["freeze_result"] is not None:
        print(f"Frozen registry: {result['freeze_result'].registry_path}")


if __name__ == "__main__":
    main()
