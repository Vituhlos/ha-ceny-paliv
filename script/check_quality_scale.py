"""Check custom_components/ceny_paliv/quality_scale.yaml against the Home Assistant quality scale.

Every rule of every tier must be listed with a valid status, an exemption needs a reason, and no unknown rule may
appear. The script prints the highest tier whose rules (and those of the tiers below) are all done or exempt.
Rules: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules (tiers.json, November 2026).
"""
from __future__ import annotations

import pathlib
import sys

import yaml

TIERS: dict[str, list[str]] = {
    "bronze": [
        "action-setup", "appropriate-polling", "brands", "common-modules", "config-flow-test-coverage",
        "config-flow", "dependency-transparency", "docs-actions", "docs-triggers", "docs-conditions",
        "docs-high-level-description", "docs-installation-instructions", "docs-removal-instructions",
        "entity-event-setup", "entity-unique-id", "has-entity-name", "runtime-data", "test-before-configure",
        "test-before-setup", "unique-config-entry",
    ],
    "silver": [
        "action-exceptions", "config-entry-unloading", "docs-configuration-parameters",
        "docs-installation-parameters", "entity-unavailable", "integration-owner", "log-when-unavailable",
        "parallel-updates", "reauthentication-flow", "test-coverage",
    ],
    "gold": [
        "devices", "diagnostics", "discovery-update-info", "discovery", "docs-data-update", "docs-examples",
        "docs-known-limitations", "docs-supported-devices", "docs-supported-functions", "docs-troubleshooting",
        "docs-use-cases", "dynamic-devices", "entity-category", "entity-device-class",
        "entity-disabled-by-default", "entity-translations", "exception-translations", "icon-translations",
        "reconfiguration-flow", "repair-issues", "stale-devices",
    ],
    "platinum": ["async-dependency", "inject-websession", "strict-typing"],
}
STATUSES = {"done", "exempt", "todo"}
FILE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "ceny_paliv" / "quality_scale.yaml"


def check(rules: dict) -> tuple[list[str], dict[str, str]]:
    """Return (errors, status per rule)."""
    errors: list[str] = []
    status: dict[str, str] = {}
    known = {rule for tier in TIERS.values() for rule in tier}
    for name, value in rules.items():
        if name not in known:
            errors.append(f"unknown rule: {name}")
            continue
        state = value if isinstance(value, str) else (value or {}).get("status")
        if state not in STATUSES:
            errors.append(f"{name}: status must be one of {sorted(STATUSES)}, not {state!r}")
            continue
        if state == "exempt" and not (isinstance(value, dict) and str(value.get("comment", "")).strip()):
            errors.append(f"{name}: an exemption needs a comment with the reason")
        status[name] = state
    errors += [f"missing rule: {rule}" for rule in sorted(known - set(rules))]
    return errors, status


def main() -> int:
    data = yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    errors, status = check(data.get("rules") or {})
    for error in errors:
        print(f"error: {error}")
    reached, complete = "none", True
    for tier, rules in TIERS.items():
        open_rules = [rule for rule in rules if status.get(rule) not in ("done", "exempt")]
        print(f"{tier:9} {len(rules) - len(open_rules):2}/{len(rules)}" + (f"  open: {', '.join(open_rules)}" if open_rules else ""))
        complete = complete and not open_rules  # a tier counts only when every tier below it is complete too
        if complete:
            reached = tier
    print(f"tier reached: {reached}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
