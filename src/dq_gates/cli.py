"""Command line entry point: dq-gate --config config/orders.yaml --data data/orders.csv"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from .explain import summarize
from .gate import QualityGate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a data quality gate against a CSV or Parquet file.")
    parser.add_argument("--config", required=True, help="YAML file with dataset name and rules")
    parser.add_argument("--data", required=True, help="CSV or Parquet file to validate")
    parser.add_argument("--report", help="optional path to write the JSON report")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    path = Path(args.data)
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

    gate = QualityGate.from_yaml(args.config)
    result = gate.evaluate(df)
    if args.report:
        Path(args.report).write_text(result.to_json())
    print(summarize(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
