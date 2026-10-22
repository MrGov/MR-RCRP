"""Hard-timeout subprocess boundary for generated operator execution."""
from __future__ import annotations

import hashlib
import multiprocessing
import sys
import types
import warnings
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

from .candidate_security import validate_candidate_source


TRUSTED_EXECUTOR_SANDBOX_LEVEL = "timeout_only"
TRUSTED_EXECUTOR_IDENTITY = "timeout_only_subprocess_v1"


@dataclass
class CandidateExecutionResult:
    status: str
    runtime_ms: float
    result: Any = None
    error_message: str = ""
    sandbox_level: str = TRUSTED_EXECUTOR_SANDBOX_LEVEL
    effective_sandbox_level: str = TRUSTED_EXECUTOR_SANDBOX_LEVEL
    executor_identity: str = TRUSTED_EXECUTOR_IDENTITY
    safe_to_execute: bool = False
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    wall_time_ms: float = 0.0
    route_dp_calls: int = 0
    route_dp_cache_misses: int = 0


@dataclass
class CandidateProxy:
    path: Path
    operator_type: str
    expected_code_hash: str = ""
    timeout_ms: float = 1000.0
    max_output_chars: int = 4096

    def execute(
        self, args: Sequence[Any], *, timeout_ms: float
    ) -> CandidateExecutionResult:
        return execute_candidate_process(
            path=self.path,
            operator_type=self.operator_type,
            args=args,
            timeout_ms=timeout_ms,
            max_output_chars=self.max_output_chars,
            expected_code_hash=self.expected_code_hash,
        )

    def __call__(self, *args):
        outcome = self.execute(args, timeout_ms=self.timeout_ms)
        if outcome.status == "success":
            return outcome.result
        if outcome.status == "timeout":
            raise TimeoutError(outcome.error_message or "Candidate execution timed out")
        raise RuntimeError(outcome.error_message or "Candidate execution failed")


def execute_candidate_process(
    *,
    path: Path,
    operator_type: str,
    args: Sequence[Any],
    timeout_ms: float,
    import_timeout_s: float = 1.0,
    max_output_chars: int = 4096,
    expected_code_hash: str | None = None,
) -> CandidateExecutionResult:
    """Import then call a candidate in a timeout-limited subprocess.

    This boundary is deliberately labelled ``timeout_only``.  It is not an
    operating-system capability sandbox and does not remove filesystem or
    network permissions from the child process.
    """

    wall_started = perf_counter()
    if not isinstance(expected_code_hash, str) or not expected_code_hash:
        return CandidateExecutionResult(
            status="source_hash_missing",
            runtime_ms=0.0,
            error_message="Expected candidate source hash is required; execution refused",
            wall_time_ms=(perf_counter() - wall_started) * 1000.0,
        )
    context = multiprocessing.get_context("spawn")
    parent_conn, child_conn = context.Pipe()
    process = context.Process(
        target=_candidate_worker,
        args=(
            child_conn,
            str(path),
            operator_type,
            max_output_chars,
            expected_code_hash,
        ),
    )
    process.daemon = True
    process.start()
    child_conn.close()

    try:
        if not parent_conn.poll(import_timeout_s):
            _terminate(process)
            return CandidateExecutionResult(
                status="timeout",
                runtime_ms=import_timeout_s * 1000.0,
                error_message="Candidate import timed out",
                exit_code=process.exitcode,
                wall_time_ms=(perf_counter() - wall_started) * 1000.0,
            )

        ready = parent_conn.recv()
        if ready[0] != "ready":
            _terminate(process)
            status = (
                str(ready[0])
                if ready[0] in {"source_hash_mismatch", "validation_failed"}
                else "runtime_error"
            )
            return CandidateExecutionResult(
                status=status,
                runtime_ms=0.0,
                error_message=str(ready[1]),
                exit_code=process.exitcode,
                stdout=str(ready[2]) if len(ready) > 2 else "",
                stderr=str(ready[3]) if len(ready) > 3 else "",
                stdout_truncated=bool(ready[4]) if len(ready) > 4 else False,
                stderr_truncated=bool(ready[5]) if len(ready) > 5 else False,
                wall_time_ms=(perf_counter() - wall_started) * 1000.0,
            )

        started = perf_counter()
        parent_conn.send(("run", tuple(args)))
        timeout_s = max(0.0, timeout_ms / 1000.0)
        if not parent_conn.poll(timeout_s):
            runtime_ms = (perf_counter() - started) * 1000.0
            _terminate(process)
            return CandidateExecutionResult(
                status="timeout",
                runtime_ms=runtime_ms,
                error_message=f"Candidate exceeded {timeout_ms:g} ms timeout",
                exit_code=process.exitcode,
                wall_time_ms=(perf_counter() - wall_started) * 1000.0,
            )

        message = parent_conn.recv()
        runtime_ms = (perf_counter() - started) * 1000.0
        process.join(timeout=0.2)
        if process.is_alive():
            _terminate(process)
        stdout, stdout_truncated = _truncate(
            str(message[2]) if len(message) > 2 else "", max_output_chars
        )
        stderr, stderr_truncated = _truncate(
            str(message[3]) if len(message) > 3 else "", max_output_chars
        )
        stdout_truncated = stdout_truncated or (
            bool(message[4]) if len(message) > 4 else False
        )
        stderr_truncated = stderr_truncated or (
            bool(message[5]) if len(message) > 5 else False
        )
        if message[0] == "success":
            return CandidateExecutionResult(
                status="success",
                runtime_ms=runtime_ms,
                result=message[1],
                exit_code=process.exitcode,
                stdout=stdout,
                stderr=stderr,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                wall_time_ms=(perf_counter() - wall_started) * 1000.0,
                route_dp_calls=message[6].get("calls", 0) if len(message) > 6 else 0,
                route_dp_cache_misses=message[6].get("cache_misses", 0) if len(message) > 6 else 0,
            )
        return CandidateExecutionResult(
            status="runtime_error",
            runtime_ms=runtime_ms,
            error_message=str(message[1]),
            exit_code=process.exitcode,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            wall_time_ms=(perf_counter() - wall_started) * 1000.0,
        )
    except (EOFError, OSError, BrokenPipeError) as exc:
        _terminate(process)
        return CandidateExecutionResult(
            status="runtime_error",
            runtime_ms=0.0,
            error_message=f"Candidate process communication failed: {exc}",
            exit_code=process.exitcode,
            wall_time_ms=(perf_counter() - wall_started) * 1000.0,
        )
    finally:
        parent_conn.close()


def _candidate_worker(
    connection,
    path: str,
    operator_type: str,
    max_output_chars: int,
    expected_code_hash: str | None,
) -> None:
    captured_stdout = _BoundedTextBuffer(max_output_chars)
    captured_stderr = _BoundedTextBuffer(max_output_chars)
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        warnings.showwarning = _compact_showwarning
        try:
            candidate_path = Path(path)
            source_text = candidate_path.read_text(encoding="utf-8")
            current_code_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            if current_code_hash != expected_code_hash:
                connection.send(
                    (
                        "source_hash_mismatch",
                        "Candidate source hash mismatch; execution refused",
                        captured_stdout.getvalue(),
                        captured_stderr.getvalue(),
                        captured_stdout.truncated,
                        captured_stderr.truncated,
                    )
                )
                return
            try:
                validate_candidate_source(source_text, operator_type)
            except Exception as exc:  # noqa: BLE001 - untrusted source boundary.
                connection.send(
                    (
                        "validation_failed",
                        f"{type(exc).__name__}: {exc}",
                        captured_stdout.getvalue(),
                        captured_stderr.getvalue(),
                        captured_stdout.truncated,
                        captured_stderr.truncated,
                    )
                )
                return
            module_name = f"isolated_operator_{candidate_path.stem}_{multiprocessing.current_process().pid}"
            module = types.ModuleType(module_name)
            module.__file__ = str(candidate_path)
            sys.modules[module_name] = module
            compiled = compile(source_text, str(candidate_path), "exec")
            exec(compiled, module.__dict__)
            fn_name = "repair" if operator_type == "repair" else "destroy"
            function = getattr(module, fn_name, None)
            if function is None:
                raise AttributeError(f"Missing required function: {fn_name}")
            connection.send(("ready", ""))
            command, args = connection.recv()
            if command != "run":
                raise RuntimeError(f"Unknown candidate command: {command}")
            # Count evaluator work inside the existing bounded child process.
            from ...core.dp_evaluator import RouteDPEvaluator
            original_evaluate = RouteDPEvaluator.evaluate_route
            dp_counts = {"calls": 0, "cache_misses": 0}
            def counted_evaluate(evaluator, route):
                misses = evaluator._cache_misses
                value = original_evaluate(evaluator, route)
                dp_counts["calls"] += 1
                dp_counts["cache_misses"] += evaluator._cache_misses - misses
                return value
            RouteDPEvaluator.evaluate_route = counted_evaluate
            result = function(*args)
            connection.send(
                (
                    "success",
                    result,
                    captured_stdout.getvalue(),
                    captured_stderr.getvalue(),
                    captured_stdout.truncated,
                    captured_stderr.truncated,
                    dp_counts,
                )
            )
        except Exception as exc:  # noqa: BLE001
            try:
                connection.send(
                    (
                        "runtime_error",
                        f"{type(exc).__name__}: {exc}",
                        captured_stdout.getvalue(),
                        captured_stderr.getvalue(),
                        captured_stdout.truncated,
                        captured_stderr.truncated,
                    )
                )
            except (BrokenPipeError, EOFError, OSError):
                pass
        finally:
            connection.close()


def _terminate(process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(timeout=0.2)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=0.2)


def _truncate(value: str, max_chars: int) -> tuple[str, bool]:
    limit = max(0, int(max_chars))
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _compact_showwarning(message, category, filename, lineno, file=None, line=None):
    target = file if file is not None else sys.stderr
    print(f"{category.__name__}: {message}", file=target)


class _BoundedTextBuffer:
    def __init__(self, max_chars: int):
        self._limit = max(0, int(max_chars))
        self._parts: list[str] = []
        self._size = 0
        self.truncated = False

    def write(self, value: str) -> int:
        text = str(value)
        remaining = self._limit - self._size
        if remaining > 0:
            kept = text[:remaining]
            self._parts.append(kept)
            self._size += len(kept)
        if len(text) > max(0, remaining):
            self.truncated = True
        return len(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return "".join(self._parts)
