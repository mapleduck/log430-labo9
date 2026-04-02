"""
Yugabyte demo project
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import json
from flask import Flask, request, jsonify
from db import get_sqlalchemy_session, get_engine, Base
from controllers.order_controller import (
    create_order_pessimistic,
    create_order_optimistic,
    _ensure_version_column,
)
from sqlalchemy import text

app = Flask(__name__)


def _session():
    session, _ = get_sqlalchemy_session()
    return session


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/orders/pessimistic", methods=["POST"])
def order_pessimistic():
    body = request.get_json(force=True)
    session = _session()
    order = create_order_pessimistic(session, user_id=body["user_id"], items=body["items"])
    session.close()
    if order:
        return jsonify({"order_id": order.id, "total": str(order.total_amount)}), 201
    return jsonify({"error": "Order failed (stock or constraint issue)"}), 409


@app.route("/orders/optimistic", methods=["POST"])
def order_optimistic():
    body = request.get_json(force=True)
    session = _session()
    order = create_order_optimistic(session, user_id=body["user_id"], items=body["items"])
    session.close()
    if order:
        return jsonify({"order_id": order.id, "total": str(order.total_amount)}), 201
    return jsonify({"error": "Order failed (stock or constraint issue)"}), 409


@app.route("/stocks", methods=["GET"])
def get_stocks():
    session = _session()
    rows = session.execute(text("SELECT product_id, quantity FROM stocks ORDER BY product_id")).fetchall()
    session.close()
    return jsonify([{"product_id": r.product_id, "quantity": r.quantity} for r in rows])


@app.route("/stocks/reset", methods=["POST"])
def reset_stocks():
    """Reset stocks to initial seed values for a clean load-test run."""
    session = _session()
    session.execute(text("UPDATE stocks SET quantity = 1000 WHERE product_id = 1"))
    session.execute(text("UPDATE stocks SET quantity = 500  WHERE product_id = 2"))
    session.execute(text("UPDATE stocks SET quantity = 2    WHERE product_id = 3"))
    session.execute(text("UPDATE stocks SET quantity = 90   WHERE product_id = 4"))
    session.commit()
    session.close()
    return jsonify({"status": "reset ok"})


if __name__ == "__main__":
    session, engine = get_sqlalchemy_session()
    Base.metadata.create_all(engine)
    _ensure_version_column(session)
    session.close()
    app.run(host="0.0.0.0", port=5000, debug=False)
