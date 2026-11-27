"""Enforce the integration's per-module line and config flow branch coverage in each HA job."""
import json
from pathlib import Path
import sys


def main() -> int:
    root = Path("custom_components/ceny_paliv")
    report = json.loads(Path("coverage.json").read_text(encoding="utf-8"))
    if not report["meta"]["branch_coverage"]:
        sys.exit("Run pytest with --cov-branch to measure config flow branches.")
    failures = []
    for module in sorted(root.rglob("*.py")):
        record = report["files"].get(module.as_posix())
        if record is None:
            failures.append(f"{module}: missing from coverage report")
            continue
        stats = record["summary"]
        if module == root / "config_flow.py":
            if stats["missing_lines"] or stats["missing_branches"]:
                failures.append(f"{module}: missed lines {record['missing_lines']}, branches {record['missing_branches']}")
        elif stats["num_statements"] and 100 * stats["covered_lines"] <= 95 * stats["num_statements"]:
            failures.append(f"{module}: only {stats['covered_lines']}/{stats['num_statements']} lines covered")
    if failures:
        sys.exit("\n".join(failures))
    print("Every module exceeds 95% line coverage. Config flow has 100% line and branch coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
