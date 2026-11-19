import hmac
import os
import re
import time
from datetime import datetime
from flask import Flask, jsonify, redirect, render_template, request, session
from sqlalchemy import inspect, text
from models import (
    CashMovement,
    CashSession,
    Category,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    StockMovement,
    db,
)
from seed import seed_database

FREE_SHIPPING_THRESHOLD = 250000
TRANSFER_DISCOUNT_PCT = 15

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "whip-store-dev-secret-2026")

# Base de datos: usa SQLite local en desarrollo y DATABASE_URL automáticamente en Railway
if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("WHIP_DATABASE_URL"):
    db_url = os.environ.get("WHIP_DATABASE_URL") or os.environ.get("DATABASE_URL", "sqlite:///whip_store.db")
else:
    db_url = "sqlite:///whip_store.db"

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def ensure_schema_updates():
    """Agrega columnas nuevas a tablas existentes sin perder datos (SQLite / PostgreSQL)."""
    inspector = inspect(db.engine)
    if "orders" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("orders")}
        if "channel" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN channel VARCHAR(20) DEFAULT 'WEB'"))
        if "notes" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN notes VARCHAR(255) DEFAULT ''"))
        db.session.commit()


def record_stock_movement(variant, delta, movement_type, reason="", order_id=None):
    db.session.add(
        StockMovement(
            variant_id=variant.id,
            order_id=order_id,
            product_name=variant.product.name if variant.product else "Producto",
            variant_label=f"Talle {variant.size} · {variant.color}",
            sku=variant.sku,
            movement_type=movement_type,
            quantity_delta=delta,
            stock_after=variant.stock,
            reason=reason,
        )
    )


with app.app_context():
    db.create_all()
    ensure_schema_updates()
    seed_database()


@app.template_filter("ars")
def format_ars(value):
    try:
        num = int(round(float(value)))
        return "$ " + f"{num:,}".replace(",", ".")
    except Exception:
        return "$ 0"


@app.context_processor
def inject_globals():
    return {
        "FREE_SHIPPING_THRESHOLD": FREE_SHIPPING_THRESHOLD,
        "TRANSFER_DISCOUNT_PCT": TRANSFER_DISCOUNT_PCT,
    }


# ---------------------------------------------------------------------------
# RUTAS STOREFRONT (HTML)
# ---------------------------------------------------------------------------


@app.route("/")
def home():
    active_products = (
        Product.query.filter_by(is_active=True).order_by(Product.is_featured.desc(), Product.id.asc()).all()
    )
    featured_products = [p for p in active_products if p.is_featured][:8]
    categories = Category.query.limit(3).all()
    brands = sorted(list({p.brand for p in active_products}))
    return render_template(
        "index.html",
        featured_products=featured_products,
        products=active_products,
        categories=categories,
        brands=brands,
    )


@app.route("/categoria/<slug>")
def categoria(slug):
    meta_map = {
        "cascos": ("Cascos Off-Road & DH", "Stock real por talle · 6 cuotas sin interés y 15% OFF por transferencia."),
        "antiparras": ("Antiparras", "Visión cristalina en barro y polvo con lentes de alta definición."),
        "indumentaria": ("Indumentaria", "Jerseys, pantalones y equipamiento técnico para pista y enduro."),
        "accesorios": ("Accesorios", "Complementos esenciales para el cuidado de tu equipamiento."),
        "ofertas": ("Sale / Ofertas", "Productos seleccionados con descuento especial y envío gratis."),
    }
    title, subtitle = meta_map.get(slug, ("Catálogo", "Todos los productos disponibles en Whip Store."))

    query = Product.query.filter_by(is_active=True)
    if slug == "ofertas":
        query = query.filter(Product.compare_at_price.isnot(None), Product.compare_at_price > Product.price)
    elif slug != "todos":
        cat = Category.query.filter_by(slug=slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
        else:
            query = query.filter(False)

    base_products = query.all()
    brands = sorted(list({p.brand for p in base_products}))
    sizes = sorted(
        list({v.size for p in base_products for v in p.variants if v.stock > 0}),
        key=lambda s: ["XS", "S", "M", "L", "XL", "XXL", "Único"].index(s)
        if s in ["XS", "S", "M", "L", "XL", "XXL", "Único"]
        else 99,
    )

    brand_filter = request.args.get("marca", "")
    size_filter = request.args.get("talle", "")
    sort_by = request.args.get("orden", "featured")

    filtered = []
    for p in base_products:
        if brand_filter and p.brand != brand_filter:
            continue
        if size_filter and not any(v.size == size_filter and v.stock > 0 for v in p.variants):
            continue
        filtered.append(p)

    if sort_by == "price-asc":
        filtered.sort(key=lambda p: p.price)
    elif sort_by == "price-desc":
        filtered.sort(key=lambda p: p.price, reverse=True)

    return render_template(
        "categoria.html",
        slug=slug,
        title=title,
        subtitle=subtitle,
        products=filtered,
        brands=brands,
        sizes=sizes,
        selected_brand=brand_filter,
        selected_size=size_filter,
        sort_by=sort_by,
    )


@app.route("/producto/<slug>")
def producto(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related = (
        Product.query.filter(
            Product.is_active.is_(True),
            Product.id != product.id,
            Product.category_id == product.category_id,
        )
        .limit(4)
        .all()
    )
    return render_template(
        "producto.html",
        product=product,
        product_dict=product.to_dict(),
        related_products=related,
    )


@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


@app.route("/admin")
def admin_panel():
    return redirect("/pos")


@app.route("/pos")
def pos_panel():
    return render_template("pos.html", is_authed=bool(session.get("admin_authed")))


# ---------------------------------------------------------------------------
# API STOREFRONT (JSON)
# ---------------------------------------------------------------------------


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify([])
    products = Product.query.filter_by(is_active=True).all()
    matches = [
        p.to_dict()
        for p in products
        if q in p.name.lower() or q in p.brand.lower() or q in (p.category.slug if p.category else "")
    ][:6]
    return jsonify(matches)


@app.route("/api/products")
def api_products():
    products = Product.query.filter_by(is_active=True).all()
    return jsonify([p.to_dict() for p in products])


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json(silent=True) or {}
    items_req = data.get("items") or []
    if not items_req:
        return jsonify({"ok": False, "error": "Tu carrito está vacío."}), 400

    required_fields = [
        "customer_name",
        "customer_email",
        "customer_phone",
        "shipping_address",
        "postal_code",
        "city",
        "province",
        "payment_method",
    ]
    for field in required_fields:
        if not str(data.get(field, "")).strip():
            return jsonify({"ok": False, "error": "Completá todos los campos obligatorios."}), 400

    # Validación y descuento atómico de stock en la base de datos
    try:
        subtotal = 0
        order_items_to_create = []

        for item in items_req:
            variant_id = int(item.get("variant_id", 0))
            qty = int(item.get("quantity", 1))
            if qty <= 0:
                return jsonify({"ok": False, "error": "Cantidad inválida."}), 400

            variant = db.session.get(ProductVariant, variant_id)
            if not variant or not variant.product or not variant.product.is_active:
                return jsonify({"ok": False, "error": "Uno de los productos ya no está disponible."}), 400

            if variant.stock < qty:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": f"Stock insuficiente para {variant.product.name} (Talle {variant.size}). Disponible: {variant.stock}.",
                        }
                    ),
                    409,
                )

            subtotal += variant.product.price * qty
            order_items_to_create.append((variant, qty))

        payment_method = data["payment_method"]
        discount_amount = (
            round(subtotal * (TRANSFER_DISCOUNT_PCT / 100)) if payment_method == "TRANSFERENCIA" else 0
        )
        shipping_cost = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else 11500
        total = max(0, subtotal - discount_amount + shipping_cost)

        last_order = Order.query.order_by(Order.order_number.desc()).first()
        next_number = (last_order.order_number + 1) if last_order else 1001

        new_order = Order(
            order_number=next_number,
            customer_name=data["customer_name"].strip(),
            customer_email=data["customer_email"].strip(),
            customer_phone=data["customer_phone"].strip(),
            shipping_address=data["shipping_address"].strip(),
            postal_code=data["postal_code"].strip(),
            city=data["city"].strip(),
            province=data["province"].strip(),
            payment_method=payment_method,
            payment_status="PAID" if payment_method == "MERCADOPAGO" else "PENDING",
            shipping_status="PREPARING" if payment_method == "MERCADOPAGO" else "UNFULFILLED",
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_cost=shipping_cost,
            total=total,
        )
        db.session.add(new_order)
        db.session.flush()

        for variant, qty in order_items_to_create:
            variant.stock -= qty
            db.session.add(
                OrderItem(
                    order_id=new_order.id,
                    variant_id=variant.id,
                    product_name=variant.product.name,
                    variant_label=f"Talle {variant.size} · {variant.color}",
                    image_url=(variant.product.images_json or ["/static/images/cat-cascos.jpg"])[0],
                    quantity=qty,
                    unit_price=variant.product.price,
                )
            )
            record_stock_movement(
                variant,
                -qty,
                "VENTA_WEB",
                reason=f"Pedido Web #{new_order.order_number}",
                order_id=new_order.id,
            )

        db.session.commit()
        return jsonify({"ok": True, "order": new_order.to_dict()})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error al procesar el pedido: {exc}"}), 500


# ---------------------------------------------------------------------------
# API ADMIN (/api/admin/*)
# ---------------------------------------------------------------------------


def require_admin():
    if not session.get("admin_authed"):
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return None


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    expected_email = os.environ.get("ADMIN_EMAIL", "admin@whip-helmets.com.ar").strip().lower()
    expected_password = os.environ.get("ADMIN_PASSWORD", "whip2026").strip()

    if hmac.compare_digest(email, expected_email) and hmac.compare_digest(password, expected_password):
        session["admin_authed"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Credenciales incorrectas."}), 401


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("admin_authed", None)
    return jsonify({"ok": True})


@app.route("/api/admin/state")
def api_admin_state():
    unauth = require_admin()
    if unauth:
        return unauth

    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.id.desc()).all()

    low_stock = []
    for p in products:
        for v in p.variants:
            if v.stock <= 2:
                low_stock.append(
                    {
                        "product_id": p.id,
                        "product_name": p.name,
                        "variant_id": v.id,
                        "size": v.size,
                        "sku": v.sku,
                        "stock": v.stock,
                    }
                )
    low_stock.sort(key=lambda x: x["stock"])

    return jsonify(
        {
            "ok": True,
            "products": [p.to_dict() for p in products],
            "orders": [o.to_dict() for o in orders],
            "low_stock": low_stock,
        }
    )


@app.route("/api/admin/variant/<int:variant_id>", methods=["PATCH"])
def api_admin_update_variant(variant_id):
    unauth = require_admin()
    if unauth:
        return unauth
    variant = db.session.get(ProductVariant, variant_id)
    if not variant:
        return jsonify({"ok": False, "error": "Variante no encontrada"}), 404
    data = request.get_json(silent=True) or {}
    old_stock = variant.stock
    new_stock = max(0, int(data.get("stock", variant.stock)))
    variant.stock = new_stock
    delta = new_stock - old_stock
    if delta != 0:
        record_stock_movement(
            variant,
            delta,
            "INGRESO" if delta > 0 else "AJUSTE",
            reason="Ajuste manual desde /admin",
        )
    db.session.commit()
    return jsonify({"ok": True, "variant": variant.to_dict()})


@app.route("/api/admin/product/<int:product_id>", methods=["PATCH", "DELETE"])
def api_admin_product(product_id):
    unauth = require_admin()
    if unauth:
        return unauth
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404

    if request.method == "DELETE":
        db.session.delete(product)
        db.session.commit()
        return jsonify({"ok": True})

    data = request.get_json(silent=True) or {}
    if "price" in data:
        product.price = max(0, int(data["price"]))
    if "is_active" in data:
        product.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify({"ok": True, "product": product.to_dict()})


@app.route("/api/admin/products", methods=["POST"])
def api_admin_create_product():
    unauth = require_admin()
    if unauth:
        return unauth
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "El nombre es obligatorio."}), 400

    brand = (data.get("brand") or "Whip").strip()
    cat_slug = (data.get("category_slug") or "cascos").strip()
    cat = Category.query.filter_by(slug=cat_slug).first() or Category.query.first()
    price = max(1000, int(data.get("price") or 350000))
    color = (data.get("color") or "Negro Mate").strip()
    stock_s = max(0, int(data.get("stock_s") or 0))
    stock_m = max(0, int(data.get("stock_m") or 0))
    stock_l = max(0, int(data.get("stock_l") or 0))
    stock_xl = max(0, int(data.get("stock_xl") or 0))

    slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = f"{slug_base}-{str(int(time.time()))[-4:]}"
    sku_prefix = f"{brand[:3].upper()}-{str(int(time.time()))[-4:]}"

    prod = Product(
        name=name,
        slug=slug,
        brand=brand,
        category=cat,
        price=price,
        transfer_discount=15,
        is_active=True,
        is_featured=True,
        description="Producto cargado desde el gestor Whip POS.",
        images_json=[
            "/static/images/cascos/Fox-V1-Rojo frontal.png",
            "/static/images/cascos/Fox-V1-Rojo izquierda.png",
        ],
        specs_json={
            "Homologación": "ECE 22.06 / DOT",
            "Peso aproximado": "1.350 g",
            "Material": "Compuesto de alta resistencia",
            "Interior": "Desmontable y lavable",
            "Condición": "Nuevo",
        },
    )
    db.session.add(prod)
    db.session.flush()

    for size, st in [("S", stock_s), ("M", stock_m), ("L", stock_l), ("XL", stock_xl)]:
        v = ProductVariant(
            product_id=prod.id,
            size=size,
            color=color,
            sku=f"{sku_prefix}-{size}",
            stock=st,
        )
        db.session.add(v)
        db.session.flush()
        if st > 0:
            record_stock_movement(v, st, "INGRESO", reason="Stock inicial al crear producto")
    db.session.commit()
    return jsonify({"ok": True, "product": prod.to_dict()})


@app.route("/api/admin/order/<int:order_id>", methods=["PATCH"])
def api_admin_update_order(order_id):
    unauth = require_admin()
    if unauth:
        return unauth
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"ok": False, "error": "Pedido no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    if "payment_status" in data:
        order.payment_status = data["payment_status"]
    if "shipping_status" in data:
        order.shipping_status = data["shipping_status"]
    if "tracking_code" in data:
        order.tracking_code = (data["tracking_code"] or "").strip()
        if order.tracking_code and order.shipping_status in ("UNFULFILLED", "PREPARING"):
            order.shipping_status = "SHIPPED"

    db.session.commit()
    return jsonify({"ok": True, "order": order.to_dict()})


@app.route("/api/admin/order/<int:order_id>/restore-stock", methods=["POST"])
def api_admin_restore_stock(order_id):
    unauth = require_admin()
    if unauth:
        return unauth
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"ok": False, "error": "Pedido no encontrado"}), 404
    if order.stock_restored:
        return jsonify({"ok": True, "order": order.to_dict()})

    for item in order.items:
        if item.variant_id:
            variant = db.session.get(ProductVariant, item.variant_id)
            if variant:
                variant.stock += item.quantity
                record_stock_movement(
                    variant,
                    item.quantity,
                    "DEVOLUCION",
                    reason=f"Anulación Pedido #{order.order_number}",
                    order_id=order.id,
                )

    order.payment_status = "CANCELLED"
    order.stock_restored = True
    db.session.commit()
    return jsonify({"ok": True, "order": order.to_dict()})


# ---------------------------------------------------------------------------
# API POS LOCAL (/api/pos/*) — Punto de Venta, Caja Diaria e Historial Stock
# ---------------------------------------------------------------------------


@app.route("/api/pos/state")
def api_pos_state():
    unauth = require_admin()
    if unauth:
        return unauth

    products = Product.query.order_by(Product.is_active.desc(), Product.brand.asc(), Product.name.asc()).all()
    active_session = CashSession.query.filter_by(status="OPEN").order_by(CashSession.id.desc()).first()
    closed_sessions = CashSession.query.filter_by(status="CLOSED").order_by(CashSession.id.desc()).limit(10).all()
    recent_sales = Order.query.order_by(Order.id.desc()).limit(60).all()
    recent_movements = StockMovement.query.order_by(StockMovement.id.desc()).limit(80).all()

    low_stock = []
    for p in products:
        if not p.is_active:
            continue
        for v in p.variants:
            if v.stock <= 2:
                low_stock.append(
                    {
                        "product_id": p.id,
                        "product_name": p.name,
                        "brand": p.brand,
                        "variant_id": v.id,
                        "size": v.size,
                        "sku": v.sku,
                        "stock": v.stock,
                    }
                )
    low_stock.sort(key=lambda x: x["stock"])

    return jsonify(
        {
            "ok": True,
            "products": [p.to_dict() for p in products],
            "low_stock": low_stock,
            "active_session": active_session.to_dict(include_movements=True) if active_session else None,
            "closed_sessions": [s.to_dict(include_movements=False) for s in closed_sessions],
            "recent_sales": [o.to_dict() for o in recent_sales],
            "recent_movements": [m.to_dict() for m in recent_movements],
        }
    )


@app.route("/api/pos/lookup")
def api_pos_lookup():
    """Búsqueda rápida para lector de código de barras (SKU exacto o parcial)."""
    unauth = require_admin()
    if unauth:
        return unauth

    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Código vacío."}), 400

    variant = ProductVariant.query.filter(ProductVariant.sku.ilike(code)).first()
    if not variant:
        variant = ProductVariant.query.filter(ProductVariant.sku.ilike(f"%{code}%")).first()
    if not variant or not variant.product:
        return jsonify({"ok": False, "error": f"No se encontró ningún producto con código/SKU '{code}'."}), 404

    return jsonify(
        {
            "ok": True,
            "variant": variant.to_dict(),
            "product": variant.product.to_dict(),
        }
    )


@app.route("/api/pos/sales", methods=["POST"])
def api_pos_create_sale():
    unauth = require_admin()
    if unauth:
        return unauth

    data = request.get_json(silent=True) or {}
    items_req = data.get("items") or []
    if not items_req:
        return jsonify({"ok": False, "error": "Agregá al menos un producto al ticket."}), 400

    channel = (data.get("channel") or "LOCAL").upper()
    if channel not in ("LOCAL", "WHATSAPP", "INSTAGRAM"):
        channel = "LOCAL"

    payment_method = (data.get("payment_method") or "EFECTIVO").upper()
    if payment_method not in ("EFECTIVO", "TRANSFERENCIA", "DEBITO", "CREDITO", "MERCADOPAGO"):
        payment_method = "EFECTIVO"

    customer_name = (data.get("customer_name") or "").strip() or "Cliente Mostrador"
    customer_phone = (data.get("customer_phone") or "").strip() or "-"
    notes = (data.get("notes") or "").strip()

    try:
        subtotal = 0
        order_items_to_create = []

        for item in items_req:
            variant_id = int(item.get("variant_id", 0))
            qty = int(item.get("quantity", 1))
            if qty <= 0:
                return jsonify({"ok": False, "error": "Cantidad inválida."}), 400

            variant = db.session.get(ProductVariant, variant_id)
            if not variant or not variant.product:
                return jsonify({"ok": False, "error": "Variante no encontrada."}), 404

            if variant.stock < qty:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": f"Stock insuficiente para {variant.product.name} ({variant.size}). Disponible: {variant.stock}.",
                        }
                    ),
                    409,
                )

            unit_price = int(item.get("unit_price") or variant.product.price)
            subtotal += unit_price * qty
            order_items_to_create.append((variant, qty, unit_price))

        manual_discount = max(0, int(data.get("discount_amount") or 0))
        apply_transfer_discount = bool(data.get("apply_transfer_discount", False))
        auto_discount = round(subtotal * (TRANSFER_DISCOUNT_PCT / 100)) if apply_transfer_discount else 0
        discount_amount = min(subtotal, manual_discount + auto_discount)
        total = max(0, subtotal - discount_amount)

        last_order = Order.query.order_by(Order.order_number.desc()).first()
        next_number = (last_order.order_number + 1) if last_order else 1001

        new_order = Order(
            order_number=next_number,
            customer_name=customer_name,
            customer_email="mostrador@whip-helmets.com.ar",
            customer_phone=customer_phone,
            shipping_address="Retiro en Local / Showroom",
            postal_code="-",
            city="Local Whip",
            province="Argentina",
            payment_method=payment_method,
            payment_status="PAID",
            shipping_status="DELIVERED" if channel == "LOCAL" else "PREPARING",
            channel=channel,
            notes=notes,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_cost=0,
            total=total,
        )
        db.session.add(new_order)
        db.session.flush()

        for variant, qty, unit_price in order_items_to_create:
            variant.stock -= qty
            db.session.add(
                OrderItem(
                    order_id=new_order.id,
                    variant_id=variant.id,
                    product_name=variant.product.name,
                    variant_label=f"Talle {variant.size} · {variant.color}",
                    image_url=(variant.product.images_json or ["/static/images/cat-cascos.jpg"])[0],
                    quantity=qty,
                    unit_price=unit_price,
                )
            )
            record_stock_movement(
                variant,
                -qty,
                "VENTA_LOCAL",
                reason=f"Venta {channel} #{new_order.order_number} ({payment_method})",
                order_id=new_order.id,
            )

        # Registrar ingreso en la caja abierta (si existe una sesión abierta)
        active_session = CashSession.query.filter_by(status="OPEN").order_by(CashSession.id.desc()).first()
        if active_session:
            db.session.add(
                CashMovement(
                    session_id=active_session.id,
                    order_id=new_order.id,
                    movement_type="VENTA",
                    payment_method=payment_method,
                    amount=total,
                    description=f"Venta #{new_order.order_number} · {customer_name} ({channel})",
                )
            )

        db.session.commit()
        return jsonify({"ok": True, "order": new_order.to_dict(), "cash_recorded": bool(active_session)})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error al registrar venta: {exc}"}), 500


@app.route("/api/pos/cash/open", methods=["POST"])
def api_pos_cash_open():
    unauth = require_admin()
    if unauth:
        return unauth

    existing = CashSession.query.filter_by(status="OPEN").first()
    if existing:
        return jsonify({"ok": False, "error": "Ya hay una caja abierta."}), 409

    data = request.get_json(silent=True) or {}
    opening_amount = max(0, int(data.get("opening_amount") or 0))
    notes = (data.get("notes") or "").strip()

    new_session = CashSession(opening_amount=opening_amount, notes=notes, status="OPEN")
    db.session.add(new_session)
    db.session.commit()
    return jsonify({"ok": True, "session": new_session.to_dict(include_movements=True)})


@app.route("/api/pos/cash/movement", methods=["POST"])
def api_pos_cash_movement():
    unauth = require_admin()
    if unauth:
        return unauth

    active_session = CashSession.query.filter_by(status="OPEN").order_by(CashSession.id.desc()).first()
    if not active_session:
        return jsonify({"ok": False, "error": "Abrí la caja antes de registrar movimientos."}), 400

    data = request.get_json(silent=True) or {}
    movement_type = (data.get("movement_type") or "EGRESO").upper()
    if movement_type not in ("INGRESO", "EGRESO"):
        return jsonify({"ok": False, "error": "Tipo de movimiento inválido."}), 400

    amount = int(data.get("amount") or 0)
    if amount <= 0:
        return jsonify({"ok": False, "error": "Ingresá un monto mayor a 0."}), 400

    payment_method = (data.get("payment_method") or "EFECTIVO").upper()
    description = (data.get("description") or "").strip() or ("Ingreso manual" if movement_type == "INGRESO" else "Gasto / retiro")

    mov = CashMovement(
        session_id=active_session.id,
        movement_type=movement_type,
        payment_method=payment_method,
        amount=amount,
        description=description,
    )
    db.session.add(mov)
    db.session.commit()
    return jsonify({"ok": True, "session": active_session.to_dict(include_movements=True)})


@app.route("/api/pos/cash/close", methods=["POST"])
def api_pos_cash_close():
    unauth = require_admin()
    if unauth:
        return unauth

    active_session = CashSession.query.filter_by(status="OPEN").order_by(CashSession.id.desc()).first()
    if not active_session:
        return jsonify({"ok": False, "error": "No hay ninguna caja abierta."}), 400

    data = request.get_json(silent=True) or {}
    closing_amount = max(0, int(data.get("closing_amount") or 0))
    notes = (data.get("notes") or "").strip()

    summary = active_session.summary()
    active_session.expected_cash = summary["expected_cash"]
    active_session.closing_amount = closing_amount
    if notes:
        active_session.notes = (active_session.notes + " | " + notes).strip(" |")
    active_session.status = "CLOSED"
    active_session.closed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({"ok": True, "session": active_session.to_dict(include_movements=True)})


@app.route("/api/pos/stock-movement", methods=["POST"])
def api_pos_stock_movement():
    unauth = require_admin()
    if unauth:
        return unauth

    data = request.get_json(silent=True) or {}
    variant_id = int(data.get("variant_id") or 0)
    delta = int(data.get("quantity_delta") or 0)
    movement_type = (data.get("movement_type") or "INGRESO").upper()
    reason = (data.get("reason") or "").strip()

    if delta == 0:
        return jsonify({"ok": False, "error": "La cantidad no puede ser 0."}), 400

    variant = db.session.get(ProductVariant, variant_id)
    if not variant:
        return jsonify({"ok": False, "error": "Variante no encontrada."}), 404

    if variant.stock + delta < 0:
        return jsonify({"ok": False, "error": f"No podés descontar más del stock actual ({variant.stock})."}), 400

    variant.stock += delta
    record_stock_movement(
        variant,
        delta,
        movement_type if movement_type in ("INGRESO", "AJUSTE", "DEVOLUCION") else "AJUSTE",
        reason=reason or "Movimiento desde POS Local",
    )
    db.session.commit()
    return jsonify({"ok": True, "variant": variant.to_dict()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
