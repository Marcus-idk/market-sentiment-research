"""Generate `docs/Summary.md` from code docstrings and `.env.example`."""

from __future__ import annotations

import ast
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from tool_utils import clean_docstring

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "Summary.md"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
INCLUDE_ROOTS = ("analysis", "config", "data", "llm", "utils", "workflows", "ui", "tools")
SKIP_PARTS = {"tests", "__pycache__", ".venv"}
PROPERTY_DECORATORS = {"property", "cached_property"}

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """A top-level function or class method entry."""

    name: str
    doc: str | None


@dataclass
class ClassInfo:
    """A module-level class and its direct methods."""

    name: str
    doc: str | None
    methods: list[FunctionInfo] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """Inventory data for one Python module."""

    path: Path
    module_doc: str | None
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


def is_property_method(decorators: Iterable[ast.expr]) -> bool:
    """Return True when a function is a property or cached property."""
    for decorator in decorators:
        target = decorator
        if isinstance(target, ast.Call):
            target = target.func
        if isinstance(target, ast.Name) and target.id in PROPERTY_DECORATORS:
            return True
        if isinstance(target, ast.Attribute):
            if target.attr in PROPERTY_DECORATORS | {"setter", "deleter", "getter"}:
                return True
            if isinstance(target.value, ast.Name) and target.value.id in PROPERTY_DECORATORS:
                return True
    return False


def parse_methods(class_node: ast.ClassDef) -> list[FunctionInfo]:
    """Collect direct class methods, skipping properties."""
    methods: list[FunctionInfo] = []
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_property_method(node.decorator_list):
                continue
            methods.append(
                FunctionInfo(name=node.name, doc=clean_docstring(ast.get_docstring(node)))
            )
    return methods


def parse_module(path: Path) -> ModuleInfo:
    """Parse a Python file and return its module, function, and class metadata."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module_doc = clean_docstring(ast.get_docstring(tree))
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                FunctionInfo(name=node.name, doc=clean_docstring(ast.get_docstring(node)))
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(
                ClassInfo(
                    name=node.name,
                    doc=clean_docstring(ast.get_docstring(node)),
                    methods=parse_methods(node),
                )
            )

    return ModuleInfo(
        path=path.relative_to(ROOT), module_doc=module_doc, functions=functions, classes=classes
    )


def iter_source_files() -> list[Path]:
    """Return sorted source files to include in the summary."""
    files: set[Path] = set()
    for root_name in INCLUDE_ROOTS:
        root_dir = ROOT / root_name
        if not root_dir.exists():
            continue
        for path in root_dir.rglob("*.py"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            files.add(path.resolve())

    run_poller = ROOT / "run_poller.py"
    if run_poller.exists():
        files.add(run_poller.resolve())

    return sorted(files)


def parse_env_example(path: Path) -> list[tuple[str, str]]:
    """Extract env var descriptions from `.env.example` comments above each key."""
    env_vars: list[tuple[str, str]] = []
    comment_buffer: list[str] = []
    last_line_was_comment = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            comment_buffer.clear()
            last_line_was_comment = False
            continue
        if line.startswith("#"):
            if not last_line_was_comment:
                comment_buffer.clear()
            comment_text = line.lstrip("#").strip()
            if comment_text.startswith("---"):
                last_line_was_comment = True
                continue
            comment_buffer.append(comment_text)
            last_line_was_comment = True
            continue
        if "=" not in line or line.startswith("export "):
            comment_buffer.clear()
            last_line_was_comment = False
            continue
        key = line.split("=", 1)[0].strip()
        description = " ".join(comment_buffer).strip() or "(no description)"
        env_vars.append((key, description))
        last_line_was_comment = False
    return env_vars


def build_lines(modules: list[ModuleInfo], env_vars: list[tuple[str, str]]) -> list[str]:
    """Render the summary as markdown lines."""
    lines = [
        "# Summary — Complete Code Inventory",
        "",
        "This file is autogenerated by `tools/generate_summary.py`. Do not edit by hand.",
        "",
        "## Environment Variables (from `.env.example`)",
    ]
    if env_vars:
        for key, description in env_vars:
            lines.append(f"- `{key}` - {description}")
    else:
        lines.append("- (none found)")

    top_level = [
        ("README.md", "Landing page that points developers to detailed documentation in `docs/`."),
        (
            "requirements.txt",
            "Runtime and test dependencies (OpenAI, Gemini, httpx, pytest, etc.).",
        ),
        ("requirements-dev.txt", "Developer-only extras."),
        ("pytest.ini", "Pytest configuration (pythonpath, markers, default flags)."),
        ("pyrightconfig.json", "Pyright type checker configuration."),
        (".pre-commit-config.yaml", "Pre-commit hooks (format/lint/typecheck + generators)."),
        (".env.example", "Example environment configuration (copy to `.env` and set API keys)."),
    ]
    lines += ["", "## Top-Level Files"]
    for path_str, description in top_level:
        if (ROOT / path_str).exists():
            lines.append(f"- `{path_str}` - {description}")

    docs_map = [
        ("docs/Roadmap.md", "Project roadmap and next steps."),
        ("docs/Summary.md", "Autogenerated code inventory (`tools/generate_summary.py`)."),
        (
            "docs/Test_Catalog.md",
            "Autogenerated pytest inventory (`tools/generate_test_catalog.py`).",
        ),
        ("docs/Test_Guide.md", "How to run and write tests."),
        ("docs/Writing_Code.md", "Coding rules and conventions."),
        ("docs/LLM_Providers_Guide.md", "LLM provider parameters and gotchas."),
        ("docs/Data_API_Reference.md", "Data layer reference notes."),
    ]
    lines += ["", "## Docs Map"]
    for path_str, description in docs_map:
        if (ROOT / path_str).exists():
            lines.append(f"- `{path_str}` - {description}")

    lines += ["", "## Code Inventory", ""]

    for module in modules:
        rel_path = module.path.as_posix()
        lines.append(f"### `{rel_path}`")
        lines.append(f"- Purpose: {module.module_doc or '(no module docstring)'}")

        if module.functions:
            lines.append("- Functions:")
            for func in module.functions:
                lines.append(f"  - `{func.name}` - {func.doc or '(no docstring)'}")

        if module.classes:
            lines.append("- Classes:")
            for cls in module.classes:
                lines.append(f"  - `{cls.name}` - {cls.doc or '(no docstring)'}")
                if cls.methods:
                    lines.append("    - Methods:")
                    for method in cls.methods:
                        lines.append(f"      - `{method.name}` - {method.doc or '(no docstring)'}")

        lines.append("")

    return lines


def write_output(lines: list[str]) -> None:
    """Write the rendered summary to the output file."""
    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    """Entry point to regenerate the Summary inventory."""
    if not ENV_EXAMPLE_PATH.exists():
        logger.error(".env.example not found at %s", ENV_EXAMPLE_PATH)
        return 1

    env_vars = parse_env_example(ENV_EXAMPLE_PATH)
    modules = [parse_module(path) for path in iter_source_files()]
    lines = build_lines(modules, env_vars)
    write_output(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
