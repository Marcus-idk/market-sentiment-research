"""Generate `docs/Test_Catalog.md` from pytest collection and AST metadata."""

import ast
import inspect
import logging
from collections import OrderedDict
from collections.abc import Iterable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from tool_utils import clean_docstring

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
OUTPUT_PATH = ROOT / "docs" / "Test_Catalog.md"

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Metadata for a single collected test case."""

    name: str
    doc: str | None
    markers: set[str] = field(default_factory=set)


@dataclass
class FixtureInfo:
    """Metadata for a pytest fixture defined in a test module."""

    name: str
    doc: str | None = None


@dataclass
class FileReport:
    """Aggregated test, fixture, and helper information for one test file."""

    path: Path
    module_doc: str | None = None
    fixtures: list[FixtureInfo] = field(default_factory=list)
    helpers: list[str] = field(default_factory=list)
    tests_by_class: OrderedDict[str | None, list[TestCase]] = field(default_factory=OrderedDict)
    tags: set[str] = field(default_factory=set)

    def add_test(self, class_name: str | None, case: TestCase) -> None:
        """Add a test case to this report and update its tags."""
        cases = self.tests_by_class.setdefault(class_name, [])
        if not any(existing.name == case.name for existing in cases):
            cases.append(case)
        self.tags.update(marker_tags(case.markers, self.path))


def marker_tags(markers: set[str], path: Path) -> set[str]:
    """Derive high-level tags (async, network, shared, integration) from markers and path."""
    tags: set[str] = set()
    marker_names = {marker.lower() for marker in markers}
    if "asyncio" in marker_names:
        tags.add("async")
    if "network" in marker_names:
        tags.add("network")
    if "shared" in marker_names:
        tags.add("shared")
    if "integration" in marker_names or "integration" in path.parts:
        tags.add("integration")
    if "shared" in path.parts:
        tags.add("shared")
    return tags


def parse_ast_metadata(path: Path) -> tuple[str | None, list[FixtureInfo], list[str]]:
    """Parse module docstring, fixtures, and helper names from a test module AST."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module_doc = clean_docstring(ast.get_docstring(tree))
    fixtures: list[FixtureInfo] = []
    helpers: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_fixture(node.decorator_list):
                fixtures.append(
                    FixtureInfo(
                        name=node.name,
                        doc=clean_docstring(ast.get_docstring(node)),
                    )
                )
                continue
            if not node.name.startswith("test_"):
                helpers.append(node.name)
        elif isinstance(node, ast.ClassDef):
            # we ignore class functions
            if not node.name.startswith("Test"):
                helpers.append(node.name)

    return module_doc, fixtures, helpers


def _is_fixture(decorators: Iterable[ast.expr]) -> bool:
    """Return True when the given decorators include a pytest.fixture."""
    for decorator in decorators:
        node = decorator
        if isinstance(node, ast.Call):
            node = node.func
        if isinstance(node, ast.Name) and node.id == "fixture":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "fixture":
            return True
    return False


def collect_tests() -> dict[Path, FileReport]:
    """Collect tests via pytest and build initial FileReport objects keyed by path."""
    reports: dict[Path, FileReport] = {}

    class Collector:
        """Lightweight pytest plugin that records collected test items."""

        def __init__(self) -> None:
            self.items: list[pytest.Item] = []

        def pytest_collection_modifyitems(
            self, session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
        ) -> None:  # noqa: ARG002
            """Hook: capture all collected items for later summarization."""
            self.items.extend(items)

    collector = Collector()
    args = [
        str(TESTS_DIR),
        "--collect-only",
        "-q",
        "--disable-warnings",
        "--color=no",
        "-p",
        "no:cov",
        "--override-ini",
        "addopts=",
    ]
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = pytest.main(args, plugins=[collector])
    if result != 0:
        raise SystemExit(result)

    for item in collector.items:
        path_attr: Any = getattr(item, "path", None) or getattr(item, "fspath", None)
        if path_attr is None:
            continue
        path = Path(str(path_attr)).resolve()
        try:
            rel_path = path.relative_to(ROOT)
        except ValueError:
            rel_path = path

        # Get or create the FileReport for this test file, then modify it
        report = reports.setdefault(rel_path, FileReport(path=rel_path))
        module_obj: Any = getattr(item, "module", None)
        if report.module_doc is None and module_obj is not None:
            report.module_doc = clean_docstring(inspect.getdoc(module_obj))

        test_name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
        test_obj: Any = getattr(item, "obj", None)
        test_doc = clean_docstring(inspect.getdoc(test_obj)) if test_obj is not None else None
        markers = {marker.name for marker in item.iter_markers()}
        cls_obj: Any = getattr(item, "cls", None)
        class_name = cls_obj.__name__ if cls_obj is not None else None

        report.add_test(class_name, TestCase(name=test_name, doc=test_doc, markers=markers))
        report.tags.update(marker_tags(markers, rel_path))

    return reports


def ensure_reports_have_metadata(reports: dict[Path, FileReport]) -> None:
    """Ensure every test file has a FileReport with AST-derived docs, fixtures, and helpers."""
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            rel_path = path.resolve().relative_to(ROOT)
        except ValueError:
            rel_path = path
        report = reports.setdefault(rel_path, FileReport(path=rel_path))
        module_doc, fixtures, helpers = parse_ast_metadata(path)
        if report.module_doc is None:
            report.module_doc = module_doc
        if not report.fixtures:
            report.fixtures = fixtures
        if not report.helpers:
            report.helpers = helpers
        report.tags.update(marker_tags(set(), rel_path))


def format_tags(tags: set[str]) -> str:
    """Format a tag set as a space-separated string of [tag] entries."""
    if not tags:
        return ""
    return " ".join(f"[{tag}]" for tag in sorted(tags))


def build_lines(reports: dict[Path, FileReport]) -> list[str]:
    """Build the markdown lines that make up the test catalog."""
    lines = [
        "# Test Catalog — Complete Test Inventory",
        "",
        "This file is autogenerated by `tools/generate_test_catalog.py`. Do not edit by hand.",
        "",
        "## Tag Legend",
        "- [network] — Performs real HTTP calls; requires network and API keys.",
        "- [shared] — Shared behavior suite applied across implementations.",
        "- [async] — Module-level asyncio usage in this file.",
        "- [integration] — Marks cross-module or external-integration suites.",
        "",
    ]

    for report in sorted(reports.values(), key=lambda r: r.path.as_posix()):
        rel_path = report.path.as_posix()
        lines.append(f"### `{rel_path}`")
        purpose = report.module_doc or "(no module docstring)"
        lines.append(f"- Purpose: {purpose}")

        tags_text = format_tags(report.tags)
        if tags_text:
            lines.append(f"- Tags: {tags_text}")

        if report.fixtures:
            lines.append("- Fixtures:")
            for fixture in report.fixtures:
                description = fixture.doc or "(no docstring)"
                lines.append(f"  - `{fixture.name}` - {description}")
        elif any("conftest.py" in part for part in rel_path.split("/")):
            lines.append("- Fixtures: (none)")

        if report.helpers:
            helpers_text = ", ".join(f"`{name}`" for name in report.helpers)
            lines.append(f"- Helpers: {helpers_text}")

        if not report.tests_by_class:
            lines.append("- Tests: (none)")
            lines.append("")
            continue

        lines.append("- Tests:")
        for class_name, cases in report.tests_by_class.items():
            if class_name:
                lines.append(f"  **{class_name}**")
            for case in cases:
                description = case.doc or "(no docstring)"
                lines.append(f"  - `{case.name}` - {description}")
            if class_name:
                lines.append("")
        if lines[-1] != "":
            lines.append("")

    return lines


def write_output(lines: list[str]) -> None:
    """Write the rendered catalog lines to the output markdown file."""
    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    """Entry point used by pre-commit to regenerate the test catalog."""
    if not TESTS_DIR.exists():
        logger.error("tests directory not found at %s", TESTS_DIR)
        return 1

    reports = collect_tests()
    ensure_reports_have_metadata(reports)
    lines = build_lines(reports)
    write_output(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
