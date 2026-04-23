from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.engine.agent_runtime import run_agent


def _load_json_argument(value: str | None) -> Any:
    if not value:
        return None
    candidate = Path(value)
    if candidate.exists() and candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a DataAlchemy agent from the CLI.")
    parser.add_argument("agent", help="Agent name, for example: report_agent")
    parser.add_argument("--dataset-id", required=True, help="Dataset file_id to run the agent against")
    parser.add_argument("--step", default="run_from_cli", help="Step name to pass to the agent payload")
    parser.add_argument("--config", help="Inline JSON string or path to a JSON file")
    parser.add_argument("--prior-results", help="Inline JSON array or path to a JSON file")
    return parser


async def _main_async(args: argparse.Namespace) -> dict[str, Any]:
    config = _load_json_argument(args.config) or {}
    prior_results = _load_json_argument(args.prior_results) or []
    return await run_agent(
        args.agent,
        {
            "agent": args.agent,
            "step": args.step,
            "dataset_id": args.dataset_id,
            "config": config,
            "prior_results": prior_results,
        },
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(_main_async(args))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
