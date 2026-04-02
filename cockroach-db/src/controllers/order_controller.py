"""
Distributed-lock demonstration – CockroachDB edition
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025

Key CockroachDB differences vs YugabyteDB:
  - CockroachDB uses SERIALIZABLE isolation by default and can raise
    serialization errors (SQLSTATE 40001) when two transactions conflict.
    The caller must catch these and retry – which matches the optimistic
    strategy naturally and is handled explicitly in the pessimistic path.
  - SELECT … FOR UPDATE is fully supported.
  - The `version` column approach works identically.
"""
from __future__ import annotations

import random
import time
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from logger import Logger
from models.order import Order
from models.order_item import OrderItem
from models.stock import Stock
from models.user import User
from models.product import Product

logger = Logger.get_instance("order_controller")

# CockroachDB serialization-error SQLSTATE
_CRDB_RETRY_CODES = {"40001"}  # serialization failure


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception is a CockroachDB serialization error."""
    msg = str(exc).lower()
    return "40001" in msg or "restart transaction" in msg or "retry" in msg


def _get_or_create_user(session: Session, user_id: int = 1) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return user


# ---------------------------------------------------------------------------
# Strategy 1 – Pessimistic locking (SELECT FOR UPDATE)
# CockroachDB supports SELECT FOR UPDATE under SERIALIZABLE isolation.
# Rows are locked at read time; concurrent transactions block until commit.
# CockroachDB may still raise a serialization error in rare cases, so we
# include a retry loop here too.
# ---------------------------------------------------------------------------

def create_order_pessimistic(
    session: Session,
    user_id: int,
    items: list[dict],
    max_retries: int = 5,
) -> Optional[Order]:
    """
    Create an order while holding row-level locks on every stock row
    involved (SELECT … FOR UPDATE).  Concurrent transactions that touch
    the same rows will *block* until this transaction finishes.

    A retry loop handles CockroachDB serialization errors (SQLSTATE 40001).
    """
    for attempt in range(1, max_retries + 1):
        try:
            product_ids = sorted(item["product_id"] for item in items)
            stocks: dict[int, Stock] = {}
            for pid in product_ids:
                stock = (
                    session.query(Stock)
                    .filter(Stock.product_id == pid)
                    .with_for_update()   # <-- pessimistic lock
                    .one_or_none()
                )
                if stock is None:
                    raise ValueError(f"Stock record not found for product {pid}")
                stocks[pid] = stock

            order_items_objs: list[OrderItem] = []
            total = Decimal("0.00")
            for item in items:
                pid = item["product_id"]
                qty = item["quantity"]
                stock = stocks[pid]
                if stock.quantity < qty:
                    raise ValueError(
                        f"Insufficient stock for product {pid}: "
                        f"requested {qty}, available {stock.quantity}"
                    )
                product: Product = session.get(Product, pid)
                stock.quantity -= qty
                total += product.price * qty
                order_items_objs.append(
                    OrderItem(product_id=pid, quantity=qty, unit_price=product.price)
                )

            order = Order(user_id=user_id, total_amount=total)
            session.add(order)
            session.flush()

            for oi in order_items_objs:
                oi.order_id = order.id
                session.add(oi)

            session.commit()
            logger.debug(f"[PESSIMISTIC] Order {order.id} created – total {total}")
            return order

        except Exception as exc:
            session.rollback()
            if _is_retryable(exc) and attempt < max_retries:
                logger.debug(
                    f"[PESSIMISTIC] Attempt {attempt}: retryable error, retrying… ({exc})"
                )
                time.sleep(random.uniform(0.01, 0.05) * attempt)
                continue
            logger.debug(f"[PESSIMISTIC] Failed: {exc}")
            return None

    return None


# ---------------------------------------------------------------------------
# Strategy 2 – Optimistic locking (version counter)
# No lock at read time; conflict detected at write time via version counter.
# CockroachDB's SERIALIZABLE default also catches conflicts automatically,
# but the explicit version check makes the logic self-contained and portable.
# ---------------------------------------------------------------------------

def create_order_optimistic(
    session: Session,
    user_id: int,
    items: list[dict],
    max_retries: int = 5,
) -> Optional[Order]:
    """
    Create an order using optimistic concurrency control.

    Each stock row has a `version` column.  We read the version, compute
    the new quantity, then UPDATE … WHERE version = <old_version>.
    If 0 rows are affected another transaction modified the row; we retry.
    CockroachDB serialization errors (40001) are also retried.
    """
    for attempt in range(1, max_retries + 1):
        try:
            product_ids = sorted(item["product_id"] for item in items)

            snapshots: dict[int, dict] = {}
            for pid in product_ids:
                row = session.execute(
                    text("SELECT quantity, version FROM stocks WHERE product_id = :pid"),
                    {"pid": pid},
                ).fetchone()
                if row is None:
                    raise ValueError(f"Stock record not found for product {pid}")
                snapshots[pid] = {"quantity": row.quantity, "version": row.version}

            order_items_objs: list[OrderItem] = []
            total = Decimal("0.00")
            updates: list[dict] = []
            for item in items:
                pid = item["product_id"]
                qty = item["quantity"]
                snap = snapshots[pid]
                if snap["quantity"] < qty:
                    raise ValueError(
                        f"Insufficient stock for product {pid}: "
                        f"requested {qty}, available {snap['quantity']}"
                    )
                product: Product = session.get(Product, pid)
                new_qty = snap["quantity"] - qty
                updates.append(
                    {"pid": pid, "new_qty": new_qty, "old_version": snap["version"]}
                )
                total += product.price * qty
                order_items_objs.append(
                    OrderItem(product_id=pid, quantity=qty, unit_price=product.price)
                )

            conflict = False
            for upd in updates:
                result = session.execute(
                    text(
                        "UPDATE stocks "
                        "SET quantity = :new_qty, version = version + 1 "
                        "WHERE product_id = :pid AND version = :old_version"
                    ),
                    upd,
                )
                if result.rowcount == 0:
                    session.rollback()
                    logger.debug(
                        f"[OPTIMISTIC] Attempt {attempt}: conflict on product {upd['pid']}, retrying…"
                    )
                    time.sleep(random.uniform(0.01, 0.05))
                    conflict = True
                    break

            if conflict:
                continue

            order = Order(user_id=user_id, total_amount=total)
            session.add(order)
            session.flush()
            for oi in order_items_objs:
                oi.order_id = order.id
                session.add(oi)
            session.commit()
            logger.debug(
                f"[OPTIMISTIC] Order {order.id} created on attempt {attempt} – total {total}"
            )
            return order

        except Exception as exc:
            session.rollback()
            if _is_retryable(exc) and attempt < max_retries:
                logger.debug(
                    f"[OPTIMISTIC] Attempt {attempt}: retryable error, retrying… ({exc})"
                )
                time.sleep(random.uniform(0.01, 0.1) * attempt)
                continue
            logger.debug(f"[OPTIMISTIC] Attempt {attempt} failed: {exc}")
            if attempt == max_retries:
                return None

    return None


def print_all_orders(session: Session) -> None:
    orders = session.query(Order).order_by(Order.id).all()
    logger.debug(f"\n--- Orders ({len(orders)} record(s)) ---")
    for o in orders:
        logger.debug(f"  {o}  items={[str(i) for i in o.items]}")
    logger.debug("-------------------------------------------\n")


def print_stocks(session: Session) -> None:
    stocks = session.query(Stock).order_by(Stock.product_id).all()
    logger.debug("\n--- Stocks ---")
    for s in stocks:
        logger.debug(f"  product_id={s.product_id}  qty={s.quantity}")
    logger.debug("--------------\n")
