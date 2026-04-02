"""
Stock class
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
from db import Base
from sqlalchemy import (
    Column, Integer, ForeignKey
)
from sqlalchemy.orm import relationship

class Stock(Base):
    __tablename__ = "stocks"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True)
    quantity   = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="stock")

    def __repr__(self):
        return f"<Stock(product_id={self.product_id}, quantity={self.quantity})>"
