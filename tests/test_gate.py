from pathlib import Path

import pandas as pd
import pytest

from dq_gates import QualityGate, QualityGateFailed, reconcile
from dq_gates.cli import main
from dq_gates.explain import summarize

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "orders.yaml"


def test_clean_extract_passes():
    df = pd.read_csv(ROOT / "data" / "orders_clean.csv")
    result = QualityGate.from_yaml(CONFIG).enforce(df)
    assert result.passed


def test_defective_extract_blocks_load():
    df = pd.read_csv(ROOT / "data" / "orders_with_defects.csv")
    with pytest.raises(QualityGateFailed) as exc:
        QualityGate.from_yaml(CONFIG).enforce(df)
    failed = {r.name for r in exc.value.result.blocking_failures}
    assert {"order_id_unique", "customer_id_not_null", "amount_non_negative", "status_valid"} <= failed
    assert "email_format" in {r.name for r in exc.value.result.warnings}


def test_broken_rule_fails_closed():
    gate = QualityGate("t", [{"type": "not_null", "column": "missing"}])
    result = gate.evaluate(pd.DataFrame({"a": [1]}))
    assert not result.passed


def test_summary_mentions_cause_and_survives_llm_error():
    df = pd.read_csv(ROOT / "data" / "orders_with_defects.csv")
    result = QualityGate.from_yaml(CONFIG).evaluate(df)

    def broken_llm(_: str) -> str:
        raise TimeoutError

    text = summarize(result, llm=broken_llm)
    assert "FAILED" in text and "Likely cause" in text and "LLM summary unavailable" in text


def test_reconcile():
    src = pd.DataFrame({"id": [1, 2, 3], "amt": [1.0, 2.0, 3.0]})
    tgt = pd.DataFrame({"id": [1, 2, 4], "amt": [1.0, 2.0, 5.0]})
    r = reconcile(src, tgt, key="id", sum_columns=["amt"])
    assert not r.passed and r.missing_keys == [3] and r.unexpected_keys == [4]
    assert r.control_total_diffs["amt"]["diff"] == 2.0
    assert reconcile(src, src, key="id", sum_columns=["amt"]).passed


def test_cli_exit_codes(tmp_path):
    report = tmp_path / "r.json"
    assert main(["--config", str(CONFIG), "--data", str(ROOT / "data" / "orders_clean.csv")]) == 0
    assert main(["--config", str(CONFIG), "--data", str(ROOT / "data" / "orders_with_defects.csv"),
                 "--report", str(report)]) == 1
    assert report.exists()
