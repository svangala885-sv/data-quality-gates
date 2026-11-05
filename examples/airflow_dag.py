"""Illustrative Airflow DAG showing where the gate sits in a load.

Not executed in CI (Airflow is not a dependency of this repo). The point is the
pattern: validate the staged extract, and only publish when the gate passes.
A raised QualityGateFailed fails the task, so downstream tasks never run.
"""

from datetime import datetime

import pandas as pd
from airflow.decorators import dag, task

from dq_gates import QualityGate


@dag(schedule="@daily", start_date=datetime(2026, 1, 1), catchup=False, tags=["quality"])
def orders_load():
    @task
    def extract() -> str:
        return "/opt/data/staging/orders.csv"  # placeholder path

    @task
    def validate(path: str) -> str:
        QualityGate.from_yaml("/opt/config/orders.yaml").enforce(pd.read_csv(path))
        return path

    @task
    def publish(path: str) -> None:
        ...  # MERGE into the warehouse table

    publish(validate(extract()))


orders_load()
