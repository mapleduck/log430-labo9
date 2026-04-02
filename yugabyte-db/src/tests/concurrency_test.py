"""
Distributed database concurrency test
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import Logger
import requests

DEFAULT_HOST    = "http://localhost:5000"
DEFAULT_THREADS = 5
DEFAULT_PRODUCT = 3   
logger = Logger.get_instance("concurrency_test")

def create_order(barrier: threading.Barrier, host: str, endpoint: str,
                thread_idx: int, user_id: int, product_id: int) -> dict:
    """
    Wait at the barrier until ALL threads are ready, then fire simultaneously.
    Returns a dict summarising the result.
    """
    payload = {
        "user_id": user_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    }

    # Block here until every thread has reached this point
    barrier.wait()
    t0 = time.perf_counter()

    try:
        resp = requests.post(f"{host}{endpoint}", json=payload, timeout=10)
        elapsed = time.perf_counter() - t0
        return {
            "thread":   thread_idx,
            "user_id":  user_id,
            "status":   resp.status_code,
            "body":     resp.json(),
            "elapsed":  round(elapsed, 3),
            "success":  resp.status_code == 201,
        }
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - t0
        return {
            "thread":   thread_idx,
            "user_id":  user_id,
            "status":   None,
            "body":     str(exc),
            "elapsed":  round(elapsed, 3),
            "success":  False,
        }

def run_test(host: str, endpoint: str, n_threads: int, product_id: int,
             label: str) -> None:
    logger.debug(f"\n{'='*60}")
    logger.debug(f"  Stratégie : {label}")
    logger.debug(f"  Endpoint  : {endpoint}")
    logger.debug(f"  Threads   : {n_threads}  (tous libérés simultanément)")
    logger.debug(f"  Article   : {product_id}")
    logger.debug(f"{'='*60}")

    # Reset stocks before each test for reproducibility
    try:
        requests.post(f"{host}/stocks/reset", timeout=5)
        logger.debug("  Stocks réinitialisés ✓\n")
    except requests.RequestException as e:
        logger.debug(f" Impossible de réinitialiser les stocks : {e}\n")

    barrier = threading.Barrier(n_threads)
    results = []

    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [
            executor.submit(create_order, barrier, host, endpoint, i, (i % 3) + 1, product_id)
            for i in range(n_threads)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    # Sort by thread id for readability
    results.sort(key=lambda r: r["thread"])

    successes = [r for r in results if r["success"]]
    failures  = [r for r in results if not r["success"]]

    for r in results:
        icon = "✅" if r["success"] else "❌"
        logger.debug(f"  {icon} thread {r['thread']}  user_id={r['user_id']}  "
              f"HTTP {r['status']}  {r['elapsed']}s  →  {r['body']}")

    logger.debug(f"\n  Résultat : {len(successes)} commande(s) réussie(s), "
          f"{len(failures)} échouée(s) sur {n_threads} threads")

    if successes:
        avg_success = round(sum(r["elapsed"] for r in successes) / len(successes), 3)
        logger.debug(f"  Latence moyenne (succès)  : {avg_success}s")
    if failures:
        avg_failure = round(sum(r["elapsed"] for r in failures) / len(failures), 3)
        logger.debug(f"  Latence moyenne (échecs)  : {avg_failure}s")
    if results:
        avg_total = round(sum(r["elapsed"] for r in results) / len(results), 3)
        logger.debug(f"  Latence moyenne (total)   : {avg_total}s")


def main():
    parser = argparse.ArgumentParser(description="Test de concurrence – verrous distribués")
    parser.add_argument("--host",    default=DEFAULT_HOST,    help="Base URL de l'API Flask")
    parser.add_argument("--threads", default=DEFAULT_THREADS, type=int,
                        help="Nombre de threads concurrents")
    parser.add_argument("--product", default=DEFAULT_PRODUCT, type=int,
                        help="product_id à utiliser (3 = stock limité)")
    args = parser.parse_args()

    logger.debug("\n╔══════════════════════════════════════════════════════════╗")
    logger.debug("║        Test de concurrence – Verrous distribués          ║")
    logger.debug("╚══════════════════════════════════════════════════════════╝")
    logger.debug(f"  Hôte    : {args.host}")
    logger.debug(f"  Threads : {args.threads}")
    logger.debug(f"  Produit : {args.product}")

    run_test(args.host, "/orders/pessimistic", args.threads, args.product,
             "Pessimiste (SELECT FOR UPDATE)")

    run_test(args.host, "/orders/optimistic",  args.threads, args.product,
             "Optimiste  (version + UPDATE conditionnel)")

    logger.debug("\n✔ Tests terminés.\n")


if __name__ == "__main__":
    main()