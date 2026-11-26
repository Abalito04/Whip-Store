import csv
import hmac
import io
import os
import re
import time
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session
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

STORE_ORIGIN_CP = "6300"
STORE_CITY = "Santa Rosa, La Pampa"
STORE_WHATSAPP = os.environ.get("WSP_NUMERO", "549295454401").strip()
STORE_INSTAGRAM = "https://www.instagram.com/whip.helmets/"
TRANSFERENCIA_ALIAS = os.environ.get("TRANSFERENCIA_ALIAS", "WHIP.HELMETS").strip()
TRANSFERENCIA_CBU = os.environ.get("TRANSFERENCIA_CBU", "Consultar por WhatsApp").strip()
TRANSFERENCIA_TITULAR = os.environ.get("TRANSFERENCIA_TITULAR", "Whip Helmets Argentina").strip()
TRANSFERENCIA_CUIL = os.environ.get("TRANSFERENCIA_CUIL", "").strip()
TRANSFER_DISCOUNT_PCT = 15


def calculate_correo_argentino_quotes(postal_code):
    """Cotizador de envíos Correo Argentino desde Santa Rosa, La Pampa (CP 6300)."""
    cp_digits = re.sub(r"\D", "", str(postal_code or ""))
    if len(cp_digits) < 4:
        return None
    cp_num = int(cp_digits[:4])

    if cp_num == 6300:
        zone = "Local (Santa Rosa, La Pampa)"
        suc, dom, exp = 6800, 9200, None
        eta_suc, eta_dom, eta_exp = "1 a 2 días hábiles", "1 a 2 días hábiles", ""
    elif (6000 <= cp_num <= 6999) or (8000 <= cp_num <= 8399) or (5700 <= cp_num <= 5999):
        zone = "Regional (La Pampa y alrededores)"
        suc, dom, exp = 8500, 11400, 15900
        eta_suc, eta_dom, eta_exp = "2 a 4 días hábiles", "2 a 4 días hábiles", "1 a 3 días hábiles"
    elif (1000 <= cp_num <= 3299) or (5000 <= cp_num <= 5699) or (7000 <= cp_num <= 7699):
        zone = "Nacional Centro (Bs. As. / CABA / Cba / Sta Fe / Mza)"
        suc, dom, exp = 10200, 13800, 18900
        eta_suc, eta_dom, eta_exp = "3 a 5 días hábiles", "3 a 6 días hábiles", "2 a 4 días hábiles"
    else:
        zone = "Nacional Larga Distancia (Patagonia / NOA / NEA)"
        suc, dom, exp = 12600, 16500, 22800
        eta_suc, eta_dom, eta_exp = "4 a 7 días hábiles", "5 a 8 días hábiles", "3 a 5 días hábiles"

    options = [
        {
            "code": "CA_SUCURSAL",
            "name": "Correo Argentino — Clásico a Sucursal",
            "eta": eta_suc,
            "price": suc,
        },
        {
            "code": "CA_DOMICILIO",
            "name": "Correo Argentino — Clásico a Domicilio",
            "eta": eta_dom,
            "price": dom,
        },
    ]
    if exp is not None:
        options.append(
            {
                "code": "CA_EXPRESO",
                "name": "Correo Argentino — Expreso a Domicilio",
                "eta": eta_exp,
                "price": exp,
            }
        )
    options.append(
        {
            "code": "RETIRO_LOCAL",
            "name": "Retiro en Local — Santa Rosa, La Pampa",
            "eta": "Coordinamos horario por WhatsApp",
            "price": 0,
        }
    )
    return {
        "origin": f"{STORE_CITY} (CP {STORE_ORIGIN_CP})",
        "postal_code": cp_digits[:4],
        "zone": zone,
        "options": options,
    }

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "whip-store-dev-secret-2026")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB máx. por subida
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

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
    tables = inspector.get_table_names()
    if "orders" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("orders")}
        if "channel" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN channel VARCHAR(20) DEFAULT 'WEB'"))
        if "notes" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN notes VARCHAR(255) DEFAULT ''"))
        if "mp_payment_id" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN mp_payment_id VARCHAR(100) DEFAULT ''"))
        if "stock_deducted" not in existing_cols:
            db.session.execute(text("ALTER TABLE orders ADD COLUMN stock_deducted BOOLEAN DEFAULT TRUE"))
    if "products" in tables:
        prod_cols = {c["name"] for c in inspector.get_columns("products")}
        if "cash_price" not in prod_cols:
            db.session.execute(text("ALTER TABLE products ADD COLUMN cash_price INTEGER"))
        if "is_outlet" not in prod_cols:
            db.session.execute(text("ALTER TABLE products ADD COLUMN is_outlet BOOLEAN DEFAULT FALSE"))
        if "subcategory" not in prod_cols:
            db.session.execute(text("ALTER TABLE products ADD COLUMN subcategory VARCHAR(40) DEFAULT ''"))
    if "categories" in tables:
        db.session.execute(text("UPDATE categories SET name = 'Gafas / Antiparras' WHERE slug = 'antiparras'"))
        db.session.execute(
            text(
                "UPDATE categories SET image_url = '/static/images/banner2.png' "
                "WHERE slug IN ('cascos', 'indumentaria', 'antiparras')"
            )
        )
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


def _site_base_url():
    env_url = os.environ.get("BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url
    try:
        return request.url_root.rstrip("/")
    except RuntimeError:
        return ""


@app.context_processor
def inject_globals():
    return {
        "SITE_URL": _site_base_url(),
        "TRANSFER_DISCOUNT_PCT": TRANSFER_DISCOUNT_PCT,
        "STORE_CITY": STORE_CITY,
        "STORE_WHATSAPP": os.environ.get("WSP_NUMERO", STORE_WHATSAPP).strip(),
        "STORE_INSTAGRAM": STORE_INSTAGRAM,
        "TRANSFERENCIA_ALIAS": os.environ.get("TRANSFERENCIA_ALIAS", TRANSFERENCIA_ALIAS).strip(),
        "TRANSFERENCIA_CBU": os.environ.get("TRANSFERENCIA_CBU", TRANSFERENCIA_CBU).strip(),
        "TRANSFERENCIA_TITULAR": os.environ.get("TRANSFERENCIA_TITULAR", TRANSFERENCIA_TITULAR).strip(),
        "TRANSFERENCIA_CUIL": os.environ.get("TRANSFERENCIA_CUIL", TRANSFERENCIA_CUIL).strip(),
        "MP_PUBLIC_KEY": os.environ.get("MP_PUBLIC_KEY", "").strip(),
    }


# ---------------------------------------------------------------------------
# RUTAS STOREFRONT (HTML) + SEO (robots.txt / sitemap.xml)
# ---------------------------------------------------------------------------


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")


@app.route("/robots.txt")
def robots_txt():
    base = _site_base_url()
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /pos",
        "Disallow: /admin",
        "Disallow: /checkout",
        "Disallow: /pago/",
        "Disallow: /api/",
        "",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    from xml.sax.saxutils import escape as xml_esc

    base = _site_base_url()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    urls = [
        (f"{base}/", today, "daily", "1.0"),
        (f"{base}/categoria/cascos", today, "daily", "0.8"),
        (f"{base}/categoria/indumentaria", today, "daily", "0.8"),
        (f"{base}/categoria/indumentaria-competicion", today, "daily", "0.7"),
        (f"{base}/categoria/indumentaria-casual", today, "daily", "0.7"),
        (f"{base}/categoria/antiparras", today, "daily", "0.8"),
        (f"{base}/categoria/outlet", today, "daily", "0.8"),
        (f"{base}/legales", today, "monthly", "0.3"),
    ]
    active_products = [p for p in Product.query.filter_by(is_active=True).all() if p.total_stock > 0]
    for p in active_products:
        lastmod = p.created_at.strftime("%Y-%m-%d") if getattr(p, "created_at", None) else today
        urls.append((f"{base}/producto/{p.slug}", lastmod, "daily", "0.9"))

    xml_items = "".join(
        f"<url><loc>{xml_esc(loc)}</loc><lastmod>{lm}</lastmod><changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for loc, lm, cf, pr in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{xml_items}"
        "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/")
def home():
    cat_order = {"cascos": 0, "indumentaria": 1, "antiparras": 2, "accesorios": 3}
    active_products = [p for p in Product.query.filter_by(is_active=True).all() if p.total_stock > 0]
    active_products.sort(
        key=lambda p: (
            1 if p.is_outlet else 0,  # Nuevos primero, Outlet después
            cat_order.get(p.category.slug if p.category else "", 9),  # Cascos -> Indumentaria -> Gafas/Antiparras
            0 if p.is_featured else 1,
            p.id,
        )
    )
    featured_products = [p for p in active_products if p.is_featured][:8]
    all_cats = Category.query.all()
    categories = sorted(
        [c for c in all_cats if c.slug in ("cascos", "indumentaria", "antiparras")],
        key=lambda c: cat_order.get(c.slug, 9),
    )
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
        "cascos": ("Cascos", ""),
        "antiparras": ("Gafas / Antiparras", ""),
        "indumentaria": ("Indumentaria", ""),
        "indumentaria-casual": ("Indumentaria · Casual / Informal", ""),
        "indumentaria-competicion": ("Indumentaria · Competición", ""),
        "accesorios": ("Accesorios", ""),
        "outlet": ("Outlet", ""),
    }
    title, subtitle = meta_map.get(slug, ("Catálogo", ""))

    query = Product.query.filter_by(is_active=True)
    if slug == "outlet":
        query = query.filter(Product.is_outlet.is_(True))
    elif slug in ("indumentaria-casual", "indumentaria-competicion"):
        sub_val = "casual" if slug == "indumentaria-casual" else "competicion"
        cat = Category.query.filter_by(slug="indumentaria").first()
        if cat:
            query = query.filter_by(category_id=cat.id, subcategory=sub_val)
        else:
            query = query.filter(False)
    elif slug == "ofertas":
        query = query.filter(Product.compare_at_price.isnot(None), Product.compare_at_price > Product.price)
    elif slug != "todos":
        cat = Category.query.filter_by(slug=slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
        else:
            query = query.filter(False)

    base_products = [p for p in query.all() if p.total_stock > 0]
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
    else:
        filtered.sort(key=lambda p: (1 if p.is_outlet else 0, 0 if p.is_featured else 1, p.id))

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
    related = [
        p
        for p in Product.query.filter(
            Product.is_active.is_(True),
            Product.id != product.id,
            Product.category_id == product.category_id,
        ).all()
        if p.total_stock > 0
    ][:4]
    return render_template(
        "producto.html",
        product=product,
        product_dict=product.to_dict(),
        related_products=related,
    )


@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


@app.route("/legales")
def legales():
    return render_template("legales.html")


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
    products = [p for p in Product.query.filter_by(is_active=True).all() if p.total_stock > 0]
    matches = [
        p.to_dict()
        for p in products
        if q in p.name.lower() or q in p.brand.lower() or q in (p.category.slug if p.category else "")
    ][:6]
    return jsonify(matches)


@app.route("/api/products")
def api_products():
    products = [p for p in Product.query.filter_by(is_active=True).all() if p.total_stock > 0]
    return jsonify([p.to_dict() for p in products])


@app.route("/api/shipping/quote")
def api_shipping_quote():
    cp = (request.args.get("cp") or "").strip()
    quote = calculate_correo_argentino_quotes(cp)
    if not quote:
        return jsonify({"ok": False, "error": "Ingresá un código postal válido de 4 dígitos (ej: 6300, 1425, 5000)."}), 400
    return jsonify({"ok": True, **quote})


_CHECKOUT_ATTEMPTS = {}
CHECKOUT_MAX_ATTEMPTS = 8
CHECKOUT_WINDOW_SECONDS = 600  # 10 minutos


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or "unknown"


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    ip = _client_ip()
    now = time.time()
    recent_co = [t for t in _CHECKOUT_ATTEMPTS.get(ip, []) if now - t < CHECKOUT_WINDOW_SECONDS]
    if len(recent_co) >= CHECKOUT_MAX_ATTEMPTS:
        return jsonify({"ok": False, "error": "Demasiados intentos de compra seguidos. Esperá unos minutos."}), 429
    recent_co.append(now)
    _CHECKOUT_ATTEMPTS[ip] = recent_co

    data = request.get_json(silent=True) or {}
    items_req = data.get("items") or []
    if not items_req:
        return jsonify({"ok": False, "error": "Tu carrito está vacío."}), 400

    shipping_option = str(data.get("shipping_option") or "").strip().upper()
    if not shipping_option:
        return jsonify({"ok": False, "error": "Elegí si querés envío o retiro en sucursal."}), 400

    is_pickup = shipping_option == "RETIRO_LOCAL"
    required_fields = [
        "customer_name",
        "customer_email",
        "customer_phone",
        "payment_method",
    ]
    if not is_pickup:
        required_fields.extend(["shipping_address", "postal_code", "city", "province"])

    for field in required_fields:
        if not str(data.get(field, "")).strip():
            return jsonify({"ok": False, "error": "Completá todos los campos obligatorios."}), 400

    if str(data.get("payment_method", "")).strip() not in ("TRANSFERENCIA", "MERCADOPAGO"):
        return jsonify({"ok": False, "error": "Seleccioná un medio de pago válido."}), 400

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
        if payment_method == "TRANSFERENCIA":
            discount_amount = sum(
                max(0, (v.product.price - v.product.transfer_price)) * q for v, q in order_items_to_create
            )
        else:
            discount_amount = 0
        if is_pickup:
            shipping_cost = 0
            ship_addr = "Retiro en sucursal (Santa Rosa, La Pampa)"
            ship_cp = "6300"
            ship_city = "Santa Rosa"
            ship_prov = "La Pampa"
        else:
            quote = calculate_correo_argentino_quotes(data.get("postal_code"))
            if quote:
                opt_match = next((o for o in quote["options"] if o["code"] == shipping_option), None)
                shipping_cost = opt_match["price"] if opt_match else quote["options"][1]["price"]
            else:
                shipping_cost = 13800
            ship_addr = data["shipping_address"].strip()
            ship_cp = data["postal_code"].strip()
            ship_city = data["city"].strip()
            ship_prov = data["province"].strip()
        total = max(0, subtotal - discount_amount + shipping_cost)

        last_order = Order.query.order_by(Order.order_number.desc()).first()
        next_number = (last_order.order_number + 1) if last_order else 1001

        mp_access_token = os.environ.get("MP_ACCESS_TOKEN", "").strip()
        is_mp_real = payment_method == "MERCADOPAGO" and bool(mp_access_token)

        new_order = Order(
            order_number=next_number,
            customer_name=data["customer_name"].strip(),
            customer_email=data["customer_email"].strip(),
            customer_phone=data["customer_phone"].strip(),
            shipping_address=ship_addr,
            postal_code=ship_cp,
            city=ship_city,
            province=ship_prov,
            payment_method=payment_method,
            payment_status="PENDING",
            shipping_status="UNFULFILLED",
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_cost=shipping_cost,
            total=total,
            # Para Mercado Pago real NO se descuenta stock hasta que MP confirme el pago aprobado
            stock_deducted=not is_mp_real,
        )
        db.session.add(new_order)
        db.session.flush()

        for variant, qty in order_items_to_create:
            if not is_mp_real:
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
            if not is_mp_real:
                record_stock_movement(
                    variant,
                    -qty,
                    "VENTA_WEB",
                    reason=f"Pedido Web #{new_order.order_number}",
                    order_id=new_order.id,
                )

        db.session.commit()

        # Si hay MP_ACCESS_TOKEN configurado, crear Preferencia real de Mercado Pago Checkout Pro
        if is_mp_real:
            try:
                import mercadopago

                sdk = mercadopago.SDK(mp_access_token)
                base_url = (os.environ.get("BASE_URL") or request.host_url).rstrip("/")
                mp_items = [
                    {
                        "title": f"{variant.product.name} (Talle {variant.size})",
                        "quantity": int(qty),
                        "unit_price": float(variant.product.price),
                        "currency_id": "ARS",
                    }
                    for variant, qty in order_items_to_create
                ]
                if shipping_cost > 0:
                    mp_items.append(
                        {
                            "title": "Envío Correo Argentino",
                            "quantity": 1,
                            "unit_price": float(shipping_cost),
                            "currency_id": "ARS",
                        }
                    )

                pref_data = {
                    "items": mp_items,
                    "payer": {
                        "name": new_order.customer_name,
                        "email": new_order.customer_email,
                    },
                    "external_reference": str(new_order.order_number),
                    "back_urls": {
                        "success": f"{base_url}/pago/exitoso",
                        "pending": f"{base_url}/pago/pendiente",
                        "failure": f"{base_url}/pago/fallido",
                    },
                    "notification_url": f"{base_url}/api/webhooks/mercadopago",
                }
                if base_url.startswith("https://"):
                    pref_data["auto_return"] = "approved"

                pref_res = sdk.preference().create(pref_data)
                pref = pref_res.get("response") or {}
                init_point = pref.get("init_point") or pref.get("sandbox_init_point")
                if init_point:
                    return jsonify({"ok": True, "order": new_order.to_dict(), "init_point": init_point})
                print(f"Mercado Pago no devolvió link de pago para Pedido #{new_order.order_number}: {pref}")
                return jsonify({"ok": False, "error": "No pudimos generar el link de Mercado Pago. Intentá nuevamente o elegí Transferencia."}), 502
            except Exception as mp_exc:
                print(f"Error al conectar con Mercado Pago para Pedido #{new_order.order_number}: {mp_exc}")
                return jsonify({"ok": False, "error": "Error al conectar con Mercado Pago. Intentá nuevamente en unos instantes."}), 502

        return jsonify({"ok": True, "order": new_order.to_dict()})
    except Exception as exc:
        db.session.rollback()
        print(f"Error al procesar pedido en /api/checkout: {exc}")
        return jsonify({"ok": False, "error": "No pudimos procesar tu pedido. Intentá nuevamente."}), 500


def _deduct_order_stock_if_needed(order, reason_prefix="Pago MP aprobado Pedido"):
    """Descuenta el stock de un pedido una única vez cuando se confirma el pago."""
    if not order or order.stock_deducted:
        return
    for item in order.items:
        if item.variant_id:
            variant = db.session.get(ProductVariant, item.variant_id)
            if variant:
                deducted = min(variant.stock, item.quantity)
                variant.stock = max(0, variant.stock - item.quantity)
                if deducted > 0:
                    record_stock_movement(
                        variant,
                        -deducted,
                        "VENTA_WEB",
                        reason=f"{reason_prefix} #{order.order_number}",
                        order_id=order.id,
                    )
    order.stock_deducted = True


def _restore_order_stock_if_needed(order, reason_prefix="Pago cancelado/rechazado"):
    """Devuelve el stock solo si previamente llegó a descontarse."""
    if not order or order.stock_restored or not order.stock_deducted:
        return
    for item in order.items:
        if item.variant_id:
            variant = db.session.get(ProductVariant, item.variant_id)
            if variant:
                variant.stock += item.quantity
                record_stock_movement(
                    variant,
                    item.quantity,
                    "DEVOLUCION",
                    reason=f"{reason_prefix} #{order.order_number}",
                    order_id=order.id,
                )
    order.stock_restored = True


def _verify_and_apply_mp_payment(payment_id, expected_order_number=None, source_label="MP"):
    """Consulta la API oficial de Mercado Pago para verificar estado y monto real del pago."""
    mp_access_token = os.environ.get("MP_ACCESS_TOKEN", "").strip()
    if not mp_access_token or not payment_id:
        return None
    try:
        import mercadopago

        sdk = mercadopago.SDK(mp_access_token)
        pay_res = sdk.payment().get(payment_id)
        payment = pay_res.get("response") or {}
        mp_status = str(payment.get("status") or "").lower()
        ext_ref = str(payment.get("external_reference") or "").strip()
        paid_amount = float(payment.get("transaction_amount") or 0)

        if not ext_ref.isdigit():
            return None
        order_num = int(ext_ref)
        if expected_order_number is not None and order_num != int(expected_order_number):
            return None

        order = Order.query.filter_by(order_number=order_num).first()
        if not order:
            return None

        order.mp_payment_id = str(payment_id)
        if mp_status == "approved" and paid_amount >= float(order.total) * 0.99:
            order.payment_status = "PAID"
            if order.shipping_status == "UNFULFILLED":
                order.shipping_status = "PREPARING"
            _deduct_order_stock_if_needed(order, f"{source_label} aprobado Pedido")
        elif mp_status in ("rejected", "cancelled", "refunded", "charged_back"):
            if order.payment_status != "PAID" or mp_status in ("refunded", "charged_back"):
                order.payment_status = "CANCELLED"
                _restore_order_stock_if_needed(order, f"{source_label} ({mp_status}) Pedido")
        db.session.commit()
        return order
    except Exception as exc:
        print(f"Error verificando pago MP #{payment_id}: {exc}")
        return None


@app.route("/pago/<status>")
def pago_resultado(status):
    if status not in ("exitoso", "pendiente", "fallido"):
        status = "pendiente"
    payment_id = (request.args.get("payment_id") or request.args.get("collection_id") or "").strip()
    ext_ref = (request.args.get("external_reference") or "").strip()
    order = None
    mp_configured = bool(os.environ.get("MP_ACCESS_TOKEN", "").strip())

    if ext_ref.isdigit():
        expected_num = int(ext_ref)
        if mp_configured and payment_id:
            # Solo actualiza el pedido verificando contra la API real de Mercado Pago
            order = _verify_and_apply_mp_payment(payment_id, expected_order_number=expected_num, source_label="Retorno MP")
        if not order:
            order = Order.query.filter_by(order_number=expected_num).first()

    return render_template("pago_resultado.html", status=status, order=order, payment_id=payment_id)


@app.route("/api/webhooks/mercadopago", methods=["POST", "GET"])
def api_webhook_mercadopago():
    """Webhook oficial de Mercado Pago: verifica el pago contra la API de MP antes de confirmar o revertir stock."""
    mp_access_token = os.environ.get("MP_ACCESS_TOKEN", "").strip()
    if not mp_access_token:
        return jsonify({"ok": True, "ignored": True}), 200

    data = request.get_json(silent=True) or {}
    payment_id = (
        request.args.get("data.id")
        or request.args.get("id")
        or (data.get("data") or {}).get("id")
        or data.get("id")
    )
    topic = request.args.get("type") or request.args.get("topic") or data.get("type") or data.get("topic") or ""

    if not payment_id or (topic and "payment" not in str(topic)):
        return jsonify({"ok": True}), 200

    _verify_and_apply_mp_payment(payment_id, source_label="Webhook MP")
    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------------
# API ADMIN (/api/admin/*)
# ---------------------------------------------------------------------------


def require_admin():
    if not session.get("admin_authed"):
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return None


_LOGIN_ATTEMPTS = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 600  # 10 minutos


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    ip = _client_ip()
    now = time.time()
    recent = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    if len(recent) >= LOGIN_MAX_ATTEMPTS:
        wait_min = max(1, int((LOGIN_WINDOW_SECONDS - (now - recent[0])) // 60) + 1)
        return jsonify({"ok": False, "error": f"Demasiados intentos fallidos. Esperá {wait_min} min."}), 429

    if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("ADMIN_PASSWORD", "").strip():
        return jsonify({"ok": False, "error": "Configurá ADMIN_PASSWORD en las variables de Railway."}), 503

    data = request.get_json(silent=True) or {}
    user_in = (data.get("email") or data.get("username") or "").strip().lower()
    password = (data.get("password") or "").strip()

    expected_user = (
        os.environ.get("ADMIN_USERNAME")
        or os.environ.get("ADMIN_EMAIL")
        or "admin@whip-helmets.com.ar"
    ).strip().lower()
    expected_password = os.environ.get("ADMIN_PASSWORD", "whip2026").strip()

    if hmac.compare_digest(user_in, expected_user) and hmac.compare_digest(password, expected_password):
        _LOGIN_ATTEMPTS.pop(ip, None)
        session.permanent = True
        session["admin_authed"] = True
        return jsonify({"ok": True})

    recent.append(now)
    _LOGIN_ATTEMPTS[ip] = recent
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


@app.route("/api/pos/web-orders-ping", methods=["GET"])
def api_pos_web_orders_ping():
    unauth = require_admin()
    if unauth:
        return unauth
    after_raw = request.args.get("after_id", "").strip()
    base_q = Order.query.filter(Order.channel == "WEB", Order.payment_status != "CANCELLED")
    latest = base_q.order_by(Order.id.desc()).first()
    latest_id = latest.id if latest else 0

    if not after_raw:
        return jsonify({"ok": True, "latest_id": latest_id, "new_orders": []})

    try:
        after_id = int(after_raw)
    except ValueError:
        return jsonify({"ok": True, "latest_id": latest_id, "new_orders": []})

    new_orders = base_q.filter(Order.id > after_id).order_by(Order.id.asc()).all()
    payload = []
    for o in new_orders:
        payload.append(
            {
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "total": o.total,
                "payment_method": o.payment_method,
                "payment_status": o.payment_status,
                "items": [
                    {
                        "product_name": it.product_name,
                        "variant_label": it.variant_label,
                        "quantity": it.quantity,
                    }
                    for it in o.items
                ],
            }
        )
    return jsonify({"ok": True, "latest_id": latest_id, "new_orders": payload})


@app.route("/api/admin/upload-image", methods=["POST"])
def api_admin_upload_image():
    unauth = require_admin()
    if unauth:
        return unauth

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "No se seleccionó ningún archivo."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return jsonify({"ok": False, "error": "Formato no permitido. Usá PNG, JPG o WEBP."}), 400

    # Si Cloudinary está configurado en variables de entorno, subir allí (persistente en Railway)
    cld_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
    cld_key = os.environ.get("CLOUDINARY_API_KEY", "").strip()
    cld_secret = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
    if cld_name and cld_key and cld_secret:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(cloud_name=cld_name, api_key=cld_key, api_secret=cld_secret, secure=True)
            res = cloudinary.uploader.upload(file, folder="whip-store")
            return jsonify({"ok": True, "url": res["secure_url"]})
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Error subiendo a Cloudinary: {exc}"}), 502

    upload_dir = os.path.join(app.static_folder, "images", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    safe_base = secure_filename(os.path.splitext(file.filename)[0]) or "producto"
    filename = f"{safe_base}-{int(time.time())}{ext}"
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    return jsonify({"ok": True, "url": f"/static/images/uploads/{filename}"})


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
    try:
        if "name" in data and str(data["name"]).strip():
            product.name = str(data["name"]).strip()
        if "brand" in data and str(data["brand"]).strip():
            product.brand = str(data["brand"]).strip()
        if "category_slug" in data:
            cat = Category.query.filter_by(slug=str(data["category_slug"]).strip()).first()
            if cat:
                product.category = cat
        if "description" in data:
            product.description = str(data["description"] or "").strip()
        if "price" in data:
            product.price = max(0, int(data["price"]))
        if "cash_price" in data:
            cp = data["cash_price"]
            product.cash_price = int(cp) if cp and int(cp) > 0 else None
        if "compare_at_price" in data:
            cap = data["compare_at_price"]
            product.compare_at_price = int(cap) if cap and int(cap) > 0 else None
        if "transfer_discount" in data:
            product.transfer_discount = max(0, min(90, int(data["transfer_discount"] or 0)))
        if "is_active" in data:
            product.is_active = bool(data["is_active"])
        if "is_featured" in data:
            product.is_featured = bool(data["is_featured"])
        if "is_outlet" in data:
            product.is_outlet = bool(data["is_outlet"])
        if "subcategory" in data:
            product.subcategory = str(data["subcategory"] or "").strip().lower()
        if "images" in data and isinstance(data["images"], list):
            cleaned_imgs = [str(u).strip() for u in data["images"] if str(u).strip()]
            product.images_json = cleaned_imgs

        if "variants" in data and isinstance(data["variants"], list):
            existing_map = {v.id: v for v in product.variants}
            kept_ids = set()

            for idx, vdata in enumerate(data["variants"]):
                size = str(vdata.get("size") or "").strip()
                if not size:
                    continue
                color = str(vdata.get("color") or "Único").strip()
                sku = str(vdata.get("sku") or "").strip()
                if not sku:
                    sku = f"{product.brand[:3].upper()}-{product.id}-{size}-{int(time.time()) % 1000}{idx}"
                new_stock = max(0, int(vdata.get("stock") or 0))
                vid = vdata.get("id")

                if vid and int(vid) in existing_map:
                    v = existing_map[int(vid)]
                    kept_ids.add(v.id)
                    old_stock = v.stock
                    v.size = size
                    v.color = color
                    v.sku = sku
                    v.stock = new_stock
                    delta = new_stock - old_stock
                    if delta != 0:
                        record_stock_movement(
                            v,
                            delta,
                            "INGRESO" if delta > 0 else "AJUSTE",
                            reason="Edición de producto desde POS",
                        )
                else:
                    v = ProductVariant(
                        product_id=product.id,
                        size=size,
                        color=color,
                        sku=sku,
                        stock=new_stock,
                    )
                    db.session.add(v)
                    db.session.flush()
                    kept_ids.add(v.id)
                    if new_stock > 0:
                        record_stock_movement(v, new_stock, "INGRESO", reason="Nueva variante desde POS")

            for old_id, old_v in existing_map.items():
                if old_id not in kept_ids:
                    OrderItem.query.filter_by(variant_id=old_id).update({"variant_id": None})
                    StockMovement.query.filter_by(variant_id=old_id).update({"variant_id": None})
                    db.session.delete(old_v)

        db.session.commit()
        return jsonify({"ok": True, "product": product.to_dict()})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error al guardar cambios: {exc}"}), 400


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
    cp_raw = data.get("cash_price")
    cash_price = int(cp_raw) if cp_raw and int(cp_raw) > 0 else None
    cap_raw = data.get("compare_at_price")
    compare_at_price = int(cap_raw) if cap_raw and int(cap_raw) > 0 else None
    color = (data.get("color") or "Negro Mate").strip()
    description = (data.get("description") or "").strip() or "Producto cargado desde el gestor Whip POS."
    raw_imgs = data.get("images") if isinstance(data.get("images"), list) else []
    cleaned_imgs = [str(u).strip() for u in raw_imgs if str(u).strip()]
    if not cleaned_imgs:
        cleaned_imgs = ["/static/images/cat-cascos.jpg"]
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
        cash_price=cash_price,
        compare_at_price=compare_at_price,
        transfer_discount=15,
        is_active=True,
        is_featured=True,
        is_outlet=bool(data.get("is_outlet", False)),
        subcategory=str(data.get("subcategory") or "").strip().lower(),
        description=description,
        images_json=cleaned_imgs,
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


IMPORT_COLUMNS = [
    "nombre",
    "marca",
    "categoria",
    "subcategoria",
    "outlet",
    "color",
    "precio_lista",
    "precio_efectivo",
    "precio_tachado",
    "stock_s",
    "stock_m",
    "stock_l",
    "stock_xl",
    "stock_unico",
    "publicar",
]


def _build_import_template_bytes():
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"

    ws.append(IMPORT_COLUMNS)
    header_fill = PatternFill(start_color="111111", end_color="111111", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for col_idx in range(1, len(IMPORT_COLUMNS) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample_rows = [
        ["Casco Fox V1 Matte Black", "Fox", "cascos", "", "no", "Negro Mate", 450000, 380000, "", 1, 2, 2, 1, 0, "no"],
        ["Conjunto Thor Pulse Air", "Thor", "indumentaria", "competicion", "no", "Negro y Blanco", 240000, 200000, "", 0, 2, 1, 0, 0, "no"],
        ["Gafas Oakley Sutro", "Oakley", "antiparras", "", "no", "Negro", 110000, 95000, "", 0, 0, 0, 0, 3, "no"],
    ]
    for row in sample_rows:
        ws.append(row)

    widths = [30, 16, 14, 15, 9, 16, 14, 15, 15, 9, 9, 9, 9, 12, 10]
    for idx, w in enumerate(widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w
    ws.freeze_panes = "A2"

    # Hoja de instrucciones
    ws2 = wb.create_sheet("Instrucciones")
    ws2.append(["Columna", "Valores permitidos / Explicación"])
    ws2["A1"].font = Font(bold=True)
    ws2["B1"].font = Font(bold=True)
    guide = [
        ("nombre", "Obligatorio. Nombre del modelo (ej: Casco Fox V1 Matte)."),
        ("marca", "Obligatorio. Marca (ej: Fox, Bell, Alpinestars, Troy Lee Designs, Thor)."),
        ("categoria", "Obligatorio. Escribir: cascos, indumentaria o antiparras."),
        ("subcategoria", "Solo para indumentaria: competicion o casual (dejar vacío en otras categorías)."),
        ("outlet", "Opcional. Escribir 'si' si es usado/outlet, o 'no' (por defecto 'no')."),
        ("color", "Opcional. Color principal (ej: Negro Mate, Rojo y Azul)."),
        ("precio_lista", "Obligatorio. Precio de lista / tarjetas (solo números, ej: 450000)."),
        ("precio_efectivo", "Opcional. Precio efectivo / transferencia (si vacío, calcula -15%)."),
        ("precio_tachado", "Opcional. Precio anterior tachado para mostrar % OFF."),
        ("stock_s / m / l / xl", "Unidades disponibles por talle (0 o vacío si no hay)."),
        ("stock_unico", "Unidades en talle Único (ideal para gafas/antiparras)."),
        ("publicar", "Escribir 'no' para cargar Pausado (recomendado hasta subir fotos) o 'si' para publicar directo."),
    ]
    for k, v in guide:
        ws2.append([k, v])
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 82

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@app.route("/api/admin/import-template")
def api_admin_import_template():
    unauth = require_admin()
    if unauth:
        return unauth
    buf = _build_import_template_bytes()
    return send_file(
        buf,
        as_attachment=True,
        download_name="plantilla_productos_whip.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _clean_int(val, default=0):
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return int(round(val))
    digits = re.sub(r"[^\d]", "", str(val).split(",")[0].split(".")[0] if re.search(r"[.,]\d{1,2}$", str(val).strip()) else str(val))
    return int(digits) if digits else default


def _clean_bool(val, default=False):
    s = str(val or "").strip().lower()
    if not s:
        return default
    return s in ("si", "sí", "s", "true", "1", "yes", "usado", "outlet")


@app.route("/api/admin/import-products", methods=["POST"])
def api_admin_import_products():
    unauth = require_admin()
    if unauth:
        return unauth

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Seleccioná un archivo .xlsx o .csv."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    rows = []

    try:
        if ext == ".xlsx":
            import openpyxl

            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
            raw_rows = list(ws.iter_rows(values_only=True))
            if not raw_rows:
                return jsonify({"ok": False, "error": "El archivo Excel está vacío."}), 400
            headers = [re.sub(r"[^a-z0-9_]+", "_", str(h or "").strip().lower()).strip("_") for h in raw_rows[0]]
            for r in raw_rows[1:]:
                if not any(cell is not None and str(cell).strip() != "" for cell in r):
                    continue
                rows.append({headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))})
        elif ext == ".csv":
            raw_text = file.read().decode("utf-8-sig", errors="replace")
            sample = raw_text[:2048]
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            reader = csv.DictReader(io.StringIO(raw_text), delimiter=delimiter)
            for r in reader:
                norm = {re.sub(r"[^a-z0-9_]+", "_", str(k or "").strip().lower()).strip("_"): v for k, v in r.items()}
                if any(str(v or "").strip() for v in norm.values()):
                    rows.append(norm)
        else:
            return jsonify({"ok": False, "error": "Formato no soportado. Subí un archivo .xlsx o .csv."}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo leer el archivo: {exc}"}), 400

    if not rows:
        return jsonify({"ok": False, "error": "No se encontraron filas con productos en el archivo."}), 400

    cat_map = {
        "casco": "cascos",
        "cascos": "cascos",
        "indumentaria": "indumentaria",
        "ropa": "indumentaria",
        "antiparra": "antiparras",
        "antiparras": "antiparras",
        "gafa": "antiparras",
        "gafas": "antiparras",
        "gafas_antiparras": "antiparras",
    }

    created = 0
    created_variants = 0
    errors = []
    ts_base = int(time.time())

    try:
        for idx, r in enumerate(rows, start=2):
            name = str(r.get("nombre") or r.get("nombre_modelo") or "").strip()
            if not name:
                errors.append(f"Fila {idx}: falta el nombre.")
                continue

            brand = str(r.get("marca") or "Whip").strip() or "Whip"
            cat_raw = re.sub(r"[^a-z]+", "_", str(r.get("categoria") or "cascos").strip().lower()).strip("_")
            cat_slug = cat_map.get(cat_raw, "cascos")
            cat = Category.query.filter_by(slug=cat_slug).first() or Category.query.first()

            sub_raw = str(r.get("subcategoria") or "").strip().lower()
            subcategory = ""
            if cat_slug == "indumentaria":
                if "casual" in sub_raw or "informal" in sub_raw:
                    subcategory = "casual"
                elif sub_raw:
                    subcategory = "competicion"

            price = _clean_int(r.get("precio_lista") or r.get("precio"), 0)
            if price <= 0:
                errors.append(f"Fila {idx} ({name}): precio_lista inválido.")
                continue

            cash_price_val = _clean_int(r.get("precio_efectivo"), 0)
            cash_price = cash_price_val if 0 < cash_price_val < price else None
            compare_val = _clean_int(r.get("precio_tachado"), 0)
            compare_at_price = compare_val if compare_val > price else None
            transfer_discount = (
                max(1, min(90, round((1 - cash_price / price) * 100)))
                if cash_price and price > cash_price
                else 15
            )

            color = str(r.get("color") or "Único").strip() or "Único"
            is_outlet = _clean_bool(r.get("outlet"), False)
            is_active = _clean_bool(r.get("publicar"), False)

            slug_base = re.sub(r"[^a-z0-9]+", "-", f"{brand}-{name}".lower()).strip("-")
            slug = f"{slug_base}-{str(ts_base)[-4:]}-{idx}"
            sku_prefix = f"{re.sub(r'[^A-Z0-9]+', '', brand[:3].upper()) or 'WHP'}-{str(ts_base)[-4:]}{idx}"

            default_img = "/static/images/cat-gafas.jpg" if cat_slug == "antiparras" else (
                "/static/images/cat-indumentaria.jpg" if cat_slug == "indumentaria" else "/static/images/cat-cascos.jpg"
            )

            prod = Product(
                name=name,
                slug=slug,
                brand=brand,
                category=cat,
                subcategory=subcategory,
                price=price,
                cash_price=cash_price,
                compare_at_price=compare_at_price,
                transfer_discount=transfer_discount,
                is_active=is_active,
                is_featured=False,
                is_outlet=is_outlet,
                description="",
                images_json=[default_img],
                specs_json={"Condición": "Usado" if is_outlet else "Nuevo", "Color": color},
            )
            db.session.add(prod)
            db.session.flush()

            st_s = max(0, _clean_int(r.get("stock_s"), 0))
            st_m = max(0, _clean_int(r.get("stock_m"), 0))
            st_l = max(0, _clean_int(r.get("stock_l"), 0))
            st_xl = max(0, _clean_int(r.get("stock_xl"), 0))
            st_u = max(0, _clean_int(r.get("stock_unico"), 0))

            if cat_slug == "antiparras" or (st_u > 0 and (st_s + st_m + st_l + st_xl) == 0):
                sizes_to_create = [("Único", st_u)]
            else:
                sizes_to_create = [("S", st_s), ("M", st_m), ("L", st_l), ("XL", st_xl)]

            for size_lbl, st_qty in sizes_to_create:
                sku_size = "U" if size_lbl == "Único" else size_lbl
                v = ProductVariant(
                    product_id=prod.id,
                    size=size_lbl,
                    color=color,
                    sku=f"{sku_prefix}-{sku_size}",
                    stock=st_qty,
                )
                db.session.add(v)
                db.session.flush()
                created_variants += 1
                if st_qty > 0:
                    record_stock_movement(v, st_qty, "INGRESO", reason="Importación masiva desde Excel")

            created += 1

        db.session.commit()
        return jsonify({"ok": True, "created": created, "variants": created_variants, "errors": errors})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error durante la importación: {exc}"}), 500


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
        if order.payment_status == "PAID":
            _deduct_order_stock_if_needed(order, "Pago confirmado manualmente Pedido")
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

    _restore_order_stock_if_needed(order, "Anulación Pedido")
    order.payment_status = "CANCELLED"

    # Revertir impacto en la Caja Diaria abierta
    linked_movs = CashMovement.query.filter_by(order_id=order.id, movement_type="VENTA").all()
    if linked_movs:
        open_session = CashSession.query.filter_by(status="OPEN").order_by(CashSession.id.desc()).first()
        for mov in linked_movs:
            if open_session and mov.session_id == open_session.id:
                db.session.delete(mov)
            elif open_session and mov.payment_method == "EFECTIVO":
                db.session.add(
                    CashMovement(
                        session_id=open_session.id,
                        order_id=order.id,
                        movement_type="EGRESO",
                        payment_method="EFECTIVO",
                        amount=mov.amount,
                        description=f"Anulación Venta #{order.order_number} (turno anterior)",
                    )
                )

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
        auto_discount = (
            sum(max(0, (v.product.price - v.product.transfer_price)) * q for v, q, _ in order_items_to_create)
            if apply_transfer_discount
            else 0
        )
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
            pay_ref = (data.get("payment_ref") or "").strip()
            ref_suffix = f" · Comp: {pay_ref}" if pay_ref else ""
            db.session.add(
                CashMovement(
                    session_id=active_session.id,
                    order_id=new_order.id,
                    movement_type="VENTA",
                    payment_method=payment_method,
                    amount=total,
                    description=f"Venta #{new_order.order_number} · {customer_name} ({channel}){ref_suffix}",
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
    app.run(host="0.0.0.0", debug=os.environ.get("FLASK_DEBUG") == "1", port=5000)
