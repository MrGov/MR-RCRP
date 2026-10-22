"""Offline operator evolution package."""

from .evolution_loop import EvolutionArtifacts, EvolutionLoopConfig, run_evolution_loop
from .file_provider import FileOperatorEvolutionProvider
from .freezing import FreezeResult, freeze_best_operators
from .langchain_provider import LangChainOperatorEvolutionProvider
from .mock_provider import MockOperatorEvolutionProvider
from .prompt_builder import build_initial_generation_prompt, build_revision_prompt
from .provider_factory import build_provider
from .provider_interface import OperatorEvolutionProvider
from .schemas import GeneratedOperatorDraft, OperatorMetricsSummary, OperatorRecord, OperatorValidationResult
from .r5_mock_pipeline import (
    BudgetEntry,
    BudgetLedger,
    EvaluationAddress,
    Counterexample,
    OperatorArchive,
    OperatorBehaviorProfile,
    OperatorCandidate,
    SelectionConfig,
    TrustedFixtureFileProvider,
    TrustedFixtureEntry,
    TrustedFixtureRegistry,
    EliteRetentionEvent,
    aggregate_evaluation_results,
    bind_dp_behavior_metrics,
    validate_elite_retention_events,
    TrustedFixtureMockProvider,
    build_r5_split_manifests,
    build_trusted_fixtures,
    run_mock_pipeline,
    select_complementary_set,
)

__all__ = [
    "OperatorEvolutionProvider",
    "MockOperatorEvolutionProvider",
    "FileOperatorEvolutionProvider",
    "LangChainOperatorEvolutionProvider",
    "build_provider",
    "EvolutionLoopConfig",
    "EvolutionArtifacts",
    "run_evolution_loop",
    "FreezeResult",
    "freeze_best_operators",
    "build_initial_generation_prompt",
    "build_revision_prompt",
    "GeneratedOperatorDraft",
    "OperatorValidationResult",
    "OperatorMetricsSummary",
    "OperatorRecord",
    "OperatorBehaviorProfile",
    "OperatorCandidate",
    "OperatorArchive",
    "SelectionConfig",
    "BudgetEntry",
    "EvaluationAddress",
    "BudgetLedger",
    "Counterexample",
    "TrustedFixtureFileProvider",
    "TrustedFixtureEntry",
    "TrustedFixtureRegistry",
    "EliteRetentionEvent",
    "aggregate_evaluation_results",
    "bind_dp_behavior_metrics",
    "validate_elite_retention_events",
    "TrustedFixtureMockProvider",
    "build_r5_split_manifests",
    "build_trusted_fixtures",
    "select_complementary_set",
    "run_mock_pipeline",
]
