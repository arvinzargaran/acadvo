#!/usr/bin/env python3
"""Fail the build on CodeQL findings, reading SARIF written by the analyze step.

This exists because `codeql-action/analyze` does not fail a build on what it
finds — it uploads, and a finding becomes a row in the Security tab that a
human has to go and read. That is a reporting tool, not a gate, and it stops
working entirely when code scanning is disabled on the repository.

Severity comes from SARIF: a result's own `level`, else the rule's
`defaultConfiguration.level`. Only `error` fails; `warning` and `note` are
printed so a reviewer can see them without blocking the build on style-grade
findings.
"""

from __future__ import annotations

import glob
import json
import os
import sys


def rule_levels(run: dict) -> dict[str, str]:
    driver = run.get("tool", {}).get("driver", {})
    extensions = run.get("tool", {}).get("extensions", []) or []
    levels: dict[str, str] = {}
    for source in [driver, *extensions]:
        for rule in source.get("rules", []) or []:
            level = rule.get("defaultConfiguration", {}).get("level")
            if rule.get("id") and level:
                levels[rule["id"]] = level
    return levels


def location_of(result: dict) -> str:
    try:
        phys = result["locations"][0]["physicalLocation"]
        path = phys["artifactLocation"]["uri"]
        line = phys.get("region", {}).get("startLine", "?")
        return f"{path}:{line}"
    except (KeyError, IndexError):
        return "<unknown location>"


def main(directory: str) -> int:
    files = sorted(glob.glob(os.path.join(directory, "*.sarif")))
    if not files:
        print(f"No SARIF files in {directory!r} — the analysis did not produce output.")
        return 1

    errors: list[str] = []
    suppressed: list[str] = []
    lesser = 0

    for path in files:
        with open(path, encoding="utf-8") as handle:
            sarif = json.load(handle)
        for run in sarif.get("runs", []):
            levels = rule_levels(run)
            for result in run.get("results", []):
                rule_id = result.get("ruleId", "<no rule id>")
                # A `# codeql[rule-id]` comment in the source marks a result
                # suppressed. Honouring it is what makes the gate usable: without
                # it the only way past a reviewed, accepted finding is to delete
                # the check for everyone. Suppressions are printed, so an
                # accepted finding stays visible instead of disappearing.
                if result.get("suppressions"):
                    suppressed.append(
                        f"suppressed | {rule_id} | {location_of(result)}"
                    )
                    continue
                level = result.get("level") or levels.get(rule_id, "warning")
                message = result.get("message", {}).get("text", "").strip()
                line = f"{level:>7} | {rule_id} | {location_of(result)} | {message}"
                if level == "error":
                    errors.append(line)
                else:
                    lesser += 1
                    print(line)

    if suppressed:
        print("\nSuppressed by an in-source `# codeql[...]` comment:\n")
        for line in suppressed:
            print(f"  {line}")

    print(
        f"\nScanned {len(files)} SARIF file(s): {len(errors)} error, "
        f"{lesser} warning/note, {len(suppressed)} suppressed."
    )
    if errors:
        print("\nCodeQL found error-severity issues:\n")
        for line in errors:
            print(f"  {line}")
        return 1
    print("No error-severity CodeQL findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "codeql-results"))
