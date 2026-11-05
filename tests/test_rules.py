import pandas as pd
import pytest

from dq_gates.rules import build_rule


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "id": [1, 2, 2, 4],
            "amount": [10.0, -1.0, 5.0, None],
            "status": ["A", "B", "Z", None],
            "email": ["a@example.com", "bad", "c@example.org", None],
            "ts": ["2026-01-01T00:00:00", "2026-01-02T00:00:00", "2026-01-03T00:00:00", None],
        }
    )


def test_not_null(df):
    r = build_rule({"type": "not_null", "column": "amount"})(df)
    assert not r.passed and r.failed_rows == 1


def test_unique_flags_all_duplicates(df):
    r = build_rule({"type": "unique", "column": "id"})(df)
    assert r.failed_rows == 2 and r.sample_failures == [2, 2]


def test_in_range(df):
    r = build_rule({"type": "in_range", "column": "amount", "min": 0})(df)
    assert r.failed_rows == 1


def test_accepted_values_ignores_nulls(df):
    r = build_rule({"type": "accepted_values", "column": "status", "values": ["A", "B"]})(df)
    assert r.failed_rows == 1


def test_regex(df):
    r = build_rule({"type": "regex", "column": "email", "pattern": r"[^@]+@[^@]+\.\w+"})(df)
    assert r.failed_rows == 1


def test_failure_rate_threshold(df):
    r = build_rule({"type": "not_null", "column": "amount", "max_failure_rate": 0.3})(df)
    assert r.passed


def test_row_count(df):
    assert not build_rule({"type": "row_count", "min": 10})(df).passed


def test_freshness(df):
    fresh = build_rule({"type": "freshness", "column": "ts", "max_age_hours": 48, "as_of": "2026-01-04"})(df)
    stale = build_rule({"type": "freshness", "column": "ts", "max_age_hours": 1, "as_of": "2026-01-04"})(df)
    assert fresh.passed and not stale.passed


def test_unknown_rule_type():
    with pytest.raises(ValueError):
        build_rule({"type": "nope"})


def test_missing_column_raises(df):
    with pytest.raises(KeyError):
        build_rule({"type": "not_null", "column": "missing"})(df)
