"""Generate a synthetic orders extract with a few deliberate defects.

All values are random and fictional. Run: python scripts/generate_data.py
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parents[1] / "data"
STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED"]


def rows(n: int, defects: bool):
    start = datetime(2026, 1, 1)
    for i in range(1, n + 1):
        yield {
            "order_id": f"ORD-{i:06d}",
            "customer_id": f"CUST-{random.randint(1, 400):05d}",
            "order_ts": (start + timedelta(minutes=17 * i)).isoformat(),
            "status": random.choice(STATUSES),
            "amount_usd": round(random.uniform(5, 950), 2),
            "email": f"user{random.randint(1, 9999)}@example.com",
        }
    if defects:
        yield {"order_id": "ORD-000010", "customer_id": "CUST-00001", "order_ts": start.isoformat(),
               "status": "SHIPPED", "amount_usd": 20.0, "email": "dup@example.com"}  # duplicate key
        yield {"order_id": f"ORD-{n + 1:06d}", "customer_id": "", "order_ts": start.isoformat(),
               "status": "RETURNED", "amount_usd": -15.0, "email": "not-an-email"}  # several defects


def write(name: str, n: int, defects: bool) -> None:
    OUT.mkdir(exist_ok=True)
    data = list(rows(n, defects))
    with open(OUT / name, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    print(f"wrote {len(data)} rows to {OUT / name}")


if __name__ == "__main__":
    write("orders_clean.csv", 500, defects=False)
    write("orders_with_defects.csv", 500, defects=True)
