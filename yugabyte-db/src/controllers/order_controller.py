"""
Distributed-lock demonstration
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
from __future__ import annotations

import random
import time
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from logger import Logger
from models.order import Order
from models.order_item import OrderItem
from models.stock import Stock
from models.user import User
from models.product import Product

logger = Logger.get_instance("order_controller")

def _get_or_create_user(session: Session, user_id: int = 1) -> User:
    """ Retrieve user from the database """
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return user


# ---------------------------------------------------------------------------
# Strategy 1 – Pessimistic locking (SELECT FOR UPDATE)
# Row is locked at read time; other transactions block until commit/rollback.
# ---------------------------------------------------------------------------

def create_order_pessimistic(
    session: Session,
    user_id: int,
    items: list[dict],          # [{"product_id": int, "quantity": int}, ...]
) -> Optional[Order]:
    """
    Create an order while holding row-level locks on every stock row
    involved (SELECT … FOR UPDATE).  Concurrent transactions that touch
    the same rows will *block* until this transaction finishes.
    """
    try:
        # Lock all stock rows upfront (sorted to avoid deadlocks)
        product_ids = sorted(item["product_id"] for item in items)
        stocks: dict[int, Stock] = {}
        for pid in product_ids:
            stock = (
                session.query(Stock)
                .filter(Stock.product_id == pid)
                .with_for_update()
                .one_or_none()
            )
            if stock is None:
                raise ValueError(f"Stock record not found for product {pid}")
            stocks[pid] = stock

        # Validate & deduct
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
        session.flush()   # get order.id

        for oi in order_items_objs:
            oi.order_id = order.id
            session.add(oi)

        session.commit()
        logger.debug(f"[PESSIMISTIC] Order {order.id} created – total {total}")
        return order

    except Exception as exc:
        session.rollback()
        logger.debug(f"[PESSIMISTIC] Failed: {exc}")
        return None


# ---------------------------------------------------------------------------
#  Strategy 2 – Optimistic locking (version counter)
#  No lock at read time; conflict is detected at write time via a version counter.
#  On conflict the caller retries.
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
    If 0 rows are affected another transaction already modified the row
    and we retry from scratch (up to `max_retries` times).

    NOTE: the `version` column is added by this service the first time
    it runs via `_ensure_version_column`.
    """
    _ensure_version_column(session)

    for attempt in range(1, max_retries + 1):
        try:
            product_ids = sorted(item["product_id"] for item in items)

            # Read current stock + version (no lock)
            snapshots: dict[int, dict] = {}
            for pid in product_ids:
                row = session.execute(
                    text("SELECT quantity, version FROM stocks WHERE product_id = :pid"),
                    {"pid": pid},
                ).fetchone()
                if row is None:
                    raise ValueError(f"Stock record not found for product {pid}")
                snapshots[pid] = {"quantity": row.quantity, "version": row.version}

            # Validate
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

            # Apply conditional updates
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
                    # Conflict detected – retry
                    session.rollback()
                    logger.debug(
                        f"[OPTIMISTIC] Attempt {attempt}: conflict on product {upd['pid']}, retrying…"
                    )
                    time.sleep(random.uniform(0.01, 0.05))
                    break
            else:
                # All updates succeeded
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
            logger.debug(f"[OPTIMISTIC] Attempt {attempt} failed: {exc}")
            if attempt == max_retries:
                return None
            time.sleep(random.uniform(0.01, 0.1))

    return None

def _ensure_version_column(session: Session) -> None:
    """Add `version` column to stocks if it doesn't exist yet."""
    try:
        session.execute(
            text(
                "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0"
            )
        )
        session.commit()
    except Exception:
        session.rollback()


def print_all_orders(session: Session) -> None:
    """ Print all orders in the database """
    orders = session.query(Order).order_by(Order.id).all()
    logger.debug(f"\n--- Orders ({len(orders)} record(s)) ---")
    for o in orders:
        logger.debug(f"  {o}  items={[str(i) for i in o.items]}")
    logger.debug("-------------------------------------------\n")


def print_stocks(session: Session) -> None:
    """ Print stock quantity in the database for a given product_id """
    stocks = session.query(Stock).order_by(Stock.product_id).all()
    logger.debug("\n--- Stocks ---")
    for s in stocks:
        logger.debug(f"  product_id={s.product_id}  qty={s.quantity}")
    logger.debug("--------------\n")
