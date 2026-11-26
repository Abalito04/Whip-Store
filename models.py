from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    image_url = db.Column(db.String(255), default="")

    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    brand = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Integer, nullable=False)
    cash_price = db.Column(db.Integer, nullable=True)  # Precio Efectivo / Transferencia
    compare_at_price = db.Column(db.Integer, nullable=True)
    transfer_discount = db.Column(db.Integer, default=15)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_outlet = db.Column(db.Boolean, default=False)
    subcategory = db.Column(db.String(40), default="")  # Para Indumentaria: casual | competicion
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    # JSON / comma-separated lists stored cleanly
    images_json = db.Column(db.JSON, default=list)
    specs_json = db.Column(db.JSON, default=dict)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants = db.relationship(
        "ProductVariant", backref="product", cascade="all, delete-orphan", lazy=True
    )

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants)

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return None

    @property
    def installment_price(self):
        return round(self.price / 6)

    @property
    def transfer_price(self):
        if self.cash_price and self.cash_price > 0:
            return self.cash_price
        return round(self.price * (1 - (self.transfer_discount or 15) / 100))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "brand": self.brand,
            "description": self.description,
            "price": self.price,
            "cash_price": self.cash_price,
            "compare_at_price": self.compare_at_price,
            "transfer_discount": self.transfer_discount,
            "transfer_price": self.transfer_price,
            "installment_price": self.installment_price,
            "discount_percent": self.discount_percent,
            "is_active": self.is_active,
            "is_featured": self.is_featured,
            "is_outlet": bool(self.is_outlet),
            "subcategory": self.subcategory or "",
            "category_slug": self.category.slug if self.category else "cascos",
            "images": self.images_json or [],
            "specs": self.specs_json or {},
            "total_stock": self.total_stock,
            "variants": [v.to_dict() for v in self.variants],
        }


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(60), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "size": self.size,
            "color": self.color,
            "sku": self.sku,
            "stock": self.stock,
        }


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.Integer, unique=True, nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    shipping_address = db.Column(db.String(200), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)

    payment_method = db.Column(db.String(30), nullable=False)  # MERCADOPAGO | TRANSFERENCIA | EFECTIVO | DEBITO | CREDITO
    payment_status = db.Column(db.String(20), default="PENDING")  # PENDING | PAID | CANCELLED
    shipping_status = db.Column(db.String(20), default="UNFULFILLED")  # UNFULFILLED | PREPARING | SHIPPED | DELIVERED
    tracking_code = db.Column(db.String(80), default="")
    mp_payment_id = db.Column(db.String(100), default="")
    channel = db.Column(db.String(20), default="WEB")  # WEB | LOCAL | WHATSAPP | INSTAGRAM
    notes = db.Column(db.String(255), default="")

    subtotal = db.Column(db.Integer, nullable=False)
    discount_amount = db.Column(db.Integer, default=0)
    shipping_cost = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, nullable=False)
    stock_restored = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "customer_phone": self.customer_phone,
            "shipping_address": self.shipping_address,
            "postal_code": self.postal_code,
            "city": self.city,
            "province": self.province,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "shipping_status": self.shipping_status,
            "tracking_code": self.tracking_code or "",
            "mp_payment_id": self.mp_payment_id or "",
            "channel": self.channel or "WEB",
            "notes": self.notes or "",
            "subtotal": self.subtotal,
            "discount_amount": self.discount_amount,
            "shipping_cost": self.shipping_cost,
            "total": self.total,
            "stock_restored": self.stock_restored,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    variant_label = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(255), default="")
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "variant_id": self.variant_id,
            "product_name": self.product_name,
            "variant_label": self.variant_label,
            "image_url": self.image_url,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    variant_label = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(80), default="")
    movement_type = db.Column(db.String(30), nullable=False)  # VENTA_LOCAL | VENTA_WEB | INGRESO | AJUSTE | DEVOLUCION
    quantity_delta = db.Column(db.Integer, nullable=False)
    stock_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "variant_id": self.variant_id,
            "order_id": self.order_id,
            "product_name": self.product_name,
            "variant_label": self.variant_label,
            "sku": self.sku or "",
            "movement_type": self.movement_type,
            "quantity_delta": self.quantity_delta,
            "stock_after": self.stock_after,
            "reason": self.reason or "",
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
        }


class CashSession(db.Model):
    __tablename__ = "cash_sessions"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default="OPEN", nullable=False)  # OPEN | CLOSED
    opening_amount = db.Column(db.Integer, default=0, nullable=False)
    closing_amount = db.Column(db.Integer, nullable=True)
    expected_cash = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.String(255), default="")
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    movements = db.relationship(
        "CashMovement", backref="session", cascade="all, delete-orphan", lazy=True, order_by="CashMovement.id.desc()"
    )

    def summary(self):
        by_method = {
            "EFECTIVO": 0,
            "TRANSFERENCIA": 0,
            "DEBITO": 0,
            "CREDITO": 0,
            "MERCADOPAGO": 0,
        }
        sales_total = 0
        sales_count = 0
        cash_in = 0
        cash_out = 0

        for m in self.movements:
            if m.movement_type == "VENTA":
                sales_total += m.amount
                sales_count += 1
                by_method[m.payment_method] = by_method.get(m.payment_method, 0) + m.amount
            elif m.movement_type == "INGRESO":
                if m.payment_method == "EFECTIVO":
                    cash_in += m.amount
                else:
                    by_method[m.payment_method] = by_method.get(m.payment_method, 0) + m.amount
            elif m.movement_type == "EGRESO":
                if m.payment_method == "EFECTIVO":
                    cash_out += m.amount

        expected = self.opening_amount + by_method.get("EFECTIVO", 0) + cash_in - cash_out
        return {
            "sales_total": sales_total,
            "sales_count": sales_count,
            "by_method": by_method,
            "cash_in": cash_in,
            "cash_out": cash_out,
            "expected_cash": expected,
        }

    def to_dict(self, include_movements=False):
        s = self.summary()
        diff = (self.closing_amount - (self.expected_cash if self.expected_cash is not None else s["expected_cash"])) if self.closing_amount is not None else None
        data = {
            "id": self.id,
            "status": self.status,
            "opening_amount": self.opening_amount,
            "closing_amount": self.closing_amount,
            "expected_cash": self.expected_cash if self.expected_cash is not None else s["expected_cash"],
            "difference": diff,
            "notes": self.notes or "",
            "opened_at": self.opened_at.strftime("%d/%m/%Y %H:%M"),
            "closed_at": self.closed_at.strftime("%d/%m/%Y %H:%M") if self.closed_at else None,
            "summary": s,
        }
        if include_movements:
            data["movements"] = [m.to_dict() for m in self.movements]
        return data


class CashMovement(db.Model):
    __tablename__ = "cash_movements"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("cash_sessions.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    movement_type = db.Column(db.String(20), nullable=False)  # VENTA | INGRESO | EGRESO
    payment_method = db.Column(db.String(30), default="EFECTIVO", nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "order_id": self.order_id,
            "movement_type": self.movement_type,
            "payment_method": self.payment_method,
            "amount": self.amount,
            "description": self.description or "",
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
        }
