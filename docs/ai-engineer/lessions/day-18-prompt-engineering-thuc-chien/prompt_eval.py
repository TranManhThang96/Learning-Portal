#!/usr/bin/env python3
"""Offline checker for Day 18 prompt library metadata and golden set.

This script intentionally does not call an LLM. It validates that a prompt
library has enough structure before you spend tokens on model evaluation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_PROMPT_FIELDS = {
    "prompt_id",
    "version",
    "owner",
    "status",
    "model_target",
    "decoding",
    "input_variables",
    "output_schema",
    "template",
    "production_readiness",
}

REQUIRED_CASE_FIELDS = {"case_id", "prompt_id", "inputs", "expected", "assertions"}


def load_yaml_like(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: PyYAML. Install with `pip install pyyaml`, "
            "or store prompts as JSON and pass that file."
        ) from exc

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_prompts(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = load_yaml_like(path)

    if isinstance(data, dict) and "prompts" in data:
        data = data["prompts"]

    if isinstance(data, dict):
        prompts = []
        for prompt_id, value in data.items():
            if isinstance(value, dict):
                value = {"prompt_id": prompt_id, **value}
            prompts.append(value)
        data = prompts

    if not isinstance(data, list):
        raise ValueError("Prompt file must be a list, a mapping, or contain `prompts`.")

    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
            row["_line_number"] = line_number
            cases.append(row)
    return cases


def validate_prompts(prompts: list[dict[str, Any]]) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    prompt_ids: set[str] = set()

    for index, prompt in enumerate(prompts, start=1):
        if not isinstance(prompt, dict):
            errors.append(f"prompt #{index}: must be an object")
            continue

        prompt_id = prompt.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            errors.append(f"prompt #{index}: missing prompt_id")
            continue

        prompt_ids.add(prompt_id)
        missing = REQUIRED_PROMPT_FIELDS - set(prompt)
        if missing:
            errors.append(f"{prompt_id}: missing fields: {', '.join(sorted(missing))}")

        input_variables = prompt.get("input_variables")
        if not isinstance(input_variables, list) or not input_variables:
            errors.append(f"{prompt_id}: input_variables must be a non-empty list")

        template = prompt.get("template", "")
        if not isinstance(template, str) or len(template.strip()) < 80:
            errors.append(f"{prompt_id}: template is too short for production review")

        output_schema = prompt.get("output_schema")
        if not isinstance(output_schema, dict):
            errors.append(f"{prompt_id}: output_schema must be an object")

    return prompt_ids, errors


def validate_cases(cases: list[dict[str, Any]], prompt_ids: set[str]) -> list[str]:
    errors: list[str] = []
    seen_case_ids: set[str] = set()
    cases_by_prompt: dict[str, int] = {prompt_id: 0 for prompt_id in prompt_ids}
    injection_cases = 0

    for case in cases:
        line = case.get("_line_number", "?")
        missing = REQUIRED_CASE_FIELDS - set(case)
        if missing:
            errors.append(f"golden_set line {line}: missing fields: {', '.join(sorted(missing))}")
            continue

        case_id = case["case_id"]
        prompt_id = case["prompt_id"]
        if case_id in seen_case_ids:
            errors.append(f"golden_set line {line}: duplicate case_id {case_id}")
        seen_case_ids.add(case_id)

        if prompt_id not in prompt_ids:
            errors.append(f"golden_set line {line}: unknown prompt_id {prompt_id}")
        else:
            cases_by_prompt[prompt_id] += 1

        if not isinstance(case["inputs"], dict) or not case["inputs"]:
            errors.append(f"golden_set line {line}: inputs must be a non-empty object")
        if not isinstance(case["expected"], dict):
            errors.append(f"golden_set line {line}: expected must be an object")
        if not isinstance(case["assertions"], list) or not case["assertions"]:
            errors.append(f"golden_set line {line}: assertions must be a non-empty list")

        searchable = json.dumps(case, ensure_ascii=False).lower()
        if "injection" in searchable or "ignore previous" in searchable or "reveal" in searchable:
            injection_cases += 1

    for prompt_id, count in cases_by_prompt.items():
        if count < 5:
            errors.append(f"{prompt_id}: expected at least 5 golden cases, found {count}")

    if injection_cases < len(prompt_ids):
        errors.append(
            "golden_set: expected at least one injection-oriented case per prompt "
            f"({len(prompt_ids)}), found {injection_cases}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--golden", required=True, type=Path)
    args = parser.parse_args()

    prompts = load_prompts(args.prompts)
    cases = load_jsonl(args.golden)

    prompt_ids, prompt_errors = validate_prompts(prompts)
    case_errors = validate_cases(cases, prompt_ids)
    errors = prompt_errors + case_errors

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS")
    print(f"- prompts: {len(prompt_ids)}")
    print(f"- golden cases: {len(cases)}")
    print("- structure is ready for real LLM eval")
    return 0


if __name__ == "__main__":
    sys.exit(main())
