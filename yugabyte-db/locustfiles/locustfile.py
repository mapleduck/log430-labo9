"""
Locustfile - YugabyteDB
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import random
from locust import HttpUser, task, between, events


USERS       = [1, 2, 3]
PRODUCTS    = [1, 2, 3, 4]


def random_order_payload():
    return {
        "user_id": random.choice(USERS),
        "items": [
            {
                "product_id": random.choice(PRODUCTS),
                "quantity": 1,
            }
        ],
    }


class PessimisticOrderUser(HttpUser):
    """Simulates users placing orders via the pessimistic-lock endpoint."""
    wait_time = between(0.1, 0.5)
    weight = 1

    @task(10)
    def create_order(self):
        self.client.post(
            "/orders/pessimistic",
            json=random_order_payload(),
            name="/orders/pessimistic",
        )

    @task(1)
    def check_stocks(self):
        self.client.get("/stocks", name="/stocks")


class OptimisticOrderUser(HttpUser):
    """Simulates users placing orders via the optimistic-lock endpoint."""
    wait_time = between(0.1, 0.5)
    weight = 1

    @task(10)
    def create_order(self):
        self.client.post(
            "/orders/optimistic",
            json=random_order_payload(),
            name="/orders/optimistic",
        )

    @task(1)
    def check_stocks(self):
        self.client.get("/stocks", name="/stocks")


# ---------------------------------------------------------------------------
# Optional: reset stocks before the test run starts so every run is clean
# ---------------------------------------------------------------------------
@events.test_start.add_listener
def reset_stocks_on_start(environment, **kwargs):
    # Only makes sense when running with a real HTTP client; skip in unit tests
    try:
        import requests
        host = environment.host or "http://localhost:5000"
        requests.post(f"{host}/stocks/reset", timeout=5)
        print("[locust] Stocks reset for a fresh test run.")
    except Exception as exc:
        print(f"[locust] Could not reset stocks: {exc}")
