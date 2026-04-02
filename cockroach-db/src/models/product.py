"""
Product class
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
from db import Base
from sqlalchemy import (
    Column, Integer, String, DateTime, Numeric, func
)
from sqlalchemy.orm import relationship

class Product(Base):
    __tablename__ = "products"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(150), nullable=False)
    sku        = Column(String(64),  nullable=False, unique=True)
    price      = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock       = relationship("Stock",     back_populates="product", uselist=False)
    order_items = relationship("OrderItem", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}', price={self.price})>"
