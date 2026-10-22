"""Static safety checks for untrusted generated operator source."""
from __future__ import annotations

import ast
import hashlib


FORBIDDEN_MODULE_ROOTS = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "pathlib",
    "shutil",
    "requests",
    "urllib",
    "builtins",
    "importlib",
    "inspect",
    "ctypes",
}
FORBIDDEN_IMPORT_MEMBERS = {
    "io": {"FileIO", "open"},
}
FORBIDDEN_CALL_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
}
FORBIDDEN_ATTRIBUTE_NAMES = {
    "popen",
    "system",
    "spawn",
    "fork",
    "run",
    "call",
    "check_call",
    "check_output",
    "connect",
    "create_connection",
    "urlopen",
    "request",
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
    "fileio",
    "unlink",
    "rmdir",
}


class CandidateSecurityError(ValueError):
    """Raised when generated source requests a forbidden capability."""


def code_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def validate_candidate_source(source: str, operator_type: str) -> ast.Module:
    """Parse and reject forbidden capabilities before any candidate import."""

    tree = ast.parse(source)
    expected_name = "repair" if operator_type == "repair" else "destroy"
    expected_args = (
        ["partial_solution", "unassigned_tasks", "context", "rng"]
        if operator_type == "repair"
        else ["solution", "context", "rng"]
    )

    target_functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == expected_name
    ]
    if len(target_functions) != 1:
        raise ValueError(f"Expected exactly one top-level function: {expected_name}")
    target = target_functions[0]
    if isinstance(target, ast.AsyncFunctionDef):
        raise ValueError(f"Candidate function {expected_name} must be synchronous")
    if target.decorator_list:
        raise CandidateSecurityError("Forbidden decorated candidate function")
    actual_args = [arg.arg for arg in target.args.args]
    if (
        actual_args != expected_args
        or target.args.vararg is not None
        or target.args.kwarg is not None
        or target.args.kwonlyargs
    ):
        raise ValueError(f"Invalid signature {actual_args}, expected {expected_args}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _reject_module(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _reject_module(node.module)
                root = node.module.split(".", 1)[0]
                forbidden_members = FORBIDDEN_IMPORT_MEMBERS.get(root, set())
                for alias in node.names:
                    if alias.name in forbidden_members:
                        raise CandidateSecurityError(
                            f"Forbidden import: {node.module}.{alias.name}"
                        )
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise CandidateSecurityError(
                    f"Forbidden dunder/reflection attribute: {node.attr}"
                )
            if node.attr.lower() in FORBIDDEN_ATTRIBUTE_NAMES:
                raise CandidateSecurityError(
                    f"Forbidden capability attribute: {node.attr}"
                )
            root = _attribute_root(node)
            if root in FORBIDDEN_MODULE_ROOTS:
                raise CandidateSecurityError(
                    f"Forbidden capability root: {root}"
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                raise CandidateSecurityError(
                    f"Forbidden capability call: {node.func.id}"
                )
        elif isinstance(node, ast.Name):
            if node.id.startswith("__") and node.id != "__future__":
                raise CandidateSecurityError(
                    f"Forbidden dunder/reflection name: {node.id}"
                )

    return tree


def _reject_module(module_name: str) -> None:
    root = module_name.split(".", 1)[0]
    if root in FORBIDDEN_MODULE_ROOTS:
        raise CandidateSecurityError(f"Forbidden import: {module_name}")


def _attribute_root(node: ast.Attribute) -> str | None:
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None
