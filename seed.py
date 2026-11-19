from models import Category, Order, OrderItem, Product, ProductVariant, db


def seed_database():
    if Category.query.first():
        return

    cats = {
        "cascos": Category(
            name="Cascos",
            slug="cascos",
            description="Motocross, Enduro y DH de las mejores marcas mundiales.",
            image_url="/static/images/cat-cascos.jpg",
        ),
        "antiparras": Category(
            name="Antiparras",
            slug="antiparras",
            description="Lentes de alta definición con sistema anti-empañante.",
            image_url="/static/images/cat-gafas.jpg",
        ),
        "indumentaria": Category(
            name="Indumentaria",
            slug="indumentaria",
            description="Equipos, jerseys, pantalones y guantes off-road.",
            image_url="/static/images/cat-indumentaria.jpg",
        ),
        "accesorios": Category(
            name="Accesorios",
            slug="accesorios",
            description="Bolsos portacascos, viseras de repuesto y cuidados.",
            image_url="/static/images/header-bg.jpg",
        ),
    }
    db.session.add_all(cats.values())
    db.session.flush()

    products_data = [
        {
            "name": "Casco Troy Lee Designs SE5 Carbono",
            "slug": "troy-lee-designs-se5-carbono",
            "brand": "Troy Lee Designs",
            "category": cats["cascos"],
            "price": 759700,
            "compare_at_price": 849000,
            "is_featured": True,
            "description": "El tope de gama de Troy Lee Designs. Calota en fibra de carbono con protección rotacional MIPS Integra, ventilación forzada en mentonera y almohadillas desmontables de liberación rápida.",
            "images": [
                "/static/images/cascos/Troy Lee Designs-SE5-Carbono frontal.png",
                "/static/images/cascos/Troy Lee Designs-SE5-Carbono izquierda.png",
                "/static/images/cascos/Troy Lee Designs-SE5-Carbono derecha.png",
                "/static/images/cascos/Troy Lee Designs-SE5-Carbono trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.325 g (± 50 g)",
                "Material": "Fibra de Carbono + EPS Dual Density + MIPS Integra",
                "Interior": "Dri-Lex® desmontable, lavable y antibacteriano",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro Carbono", "TLD-SE5-CAR-S", 0),
                ("M", "Negro Carbono", "TLD-SE5-CAR-M", 2),
                ("L", "Negro Carbono", "TLD-SE5-CAR-L", 3),
                ("XL", "Negro Carbono", "TLD-SE5-CAR-XL", 1),
            ],
        },
        {
            "name": "Casco Bell Moto-9 Flex Carbono",
            "slug": "bell-moto-9-flex-carbono",
            "brand": "Bell",
            "category": cats["cascos"],
            "price": 685000,
            "compare_at_price": 760000,
            "is_featured": True,
            "description": "Diseñado para gestionar impactos a baja, media y alta velocidad gracias a su calota interna segmentada Flex de 3 capas. Fibra de carbono 3K ultra liviana y cierre magnético Magnefusion.",
            "images": [
                "/static/images/cascos/Bell Moto-9 Flex Carbono frontal.png",
                "/static/images/cascos/Bell Moto-9 Flex Carbono izquierda.png",
                "/static/images/cascos/Bell Moto-9 Flex Carbono derecha.png",
                "/static/images/cascos/Bell Moto-9 Flex Carbono trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.05 / SNELL M2020 / DOT",
                "Peso aproximado": "1.450 g (± 50 g)",
                "Material": "Fibra de Carbono 3K + Sistema Flex 3 capas",
                "Interior": "X-Static® XT2 plata desmontable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Blanco / Carbono", "BELL-M9F-S", 1),
                ("M", "Blanco / Carbono", "BELL-M9F-M", 4),
                ("L", "Blanco / Carbono", "BELL-M9F-L", 2),
                ("XL", "Blanco / Carbono", "BELL-M9F-XL", 0),
            ],
        },
        {
            "name": "Casco Fox V3 Motif MIPS",
            "slug": "fox-v3-motif-mips",
            "brand": "Fox",
            "category": cats["cascos"],
            "price": 465000,
            "compare_at_price": 520000,
            "is_featured": True,
            "description": "Casco profesional de motocross con tecnología MIPS™ y calota MCT (Multi Composite Technology) que combina carbono y resinas FRP para lograr un peso pluma.",
            "images": [
                "/static/images/cascos/Fox-V3-Motif frontal.png",
                "/static/images/cascos/Fox-V3-Motif izquierda.png",
                "/static/images/cascos/Fox-V3-Motif derecha.png",
                "/static/images/cascos/Fox-V3-Motif trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.280 g (± 50 g)",
                "Material": "Compuesto MCT Carbono / FRP + Varizorb™ EPS",
                "Interior": "Ionic+® antimicrobiano y lavable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Gris / Azul", "FOX-V3M-S", 2),
                ("M", "Gris / Azul", "FOX-V3M-M", 5),
                ("L", "Gris / Azul", "FOX-V3M-L", 3),
                ("XL", "Gris / Azul", "FOX-V3M-XL", 1),
            ],
        },
        {
            "name": "Casco Troy Lee Designs GP",
            "slug": "troy-lee-designs-gp",
            "brand": "Troy Lee Designs",
            "category": cats["cascos"],
            "price": 455000,
            "compare_at_price": None,
            "is_featured": True,
            "description": "La línea GP ofrece protección líder en su clase a un precio imbatible. Calota de poliacrilita liviana, barra de mentón EPP y 16 puertos de admisión.",
            "images": [
                "/static/images/cascos/Troy Lee Designs-GP frontal.png",
                "/static/images/cascos/Troy Lee Designs-GP izquierda.png",
                "/static/images/cascos/Troy Lee Designs-GP derecha.png",
            ],
            "specs": {
                "Homologación": "ECE 22.05 / DOT",
                "Peso aproximado": "1.450 g (± 50 g)",
                "Material": "Poliacrilita reforzada + Mentonera EPP",
                "Interior": "Almohadillas 3D con liberación de emergencia",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro / Blanco", "TLD-GP-S", 3),
                ("M", "Negro / Blanco", "TLD-GP-M", 4),
                ("L", "Negro / Blanco", "TLD-GP-L", 6),
                ("XL", "Negro / Blanco", "TLD-GP-XL", 2),
            ],
        },
        {
            "name": "Casco Alpinestars S-M5 Negro / Rojo",
            "slug": "alpinestars-sm5-negro-rojo",
            "brand": "Alpinestars",
            "category": cats["cascos"],
            "price": 395000,
            "compare_at_price": 445000,
            "is_featured": True,
            "description": "Desarrollado tras 5 años de investigación en competición. Calota termoinyectada ligera, visera patentada que se libera ante impactos y máxima ventilación.",
            "images": [
                "/static/images/cascos/Alpinestars-SM5 frontal.png",
                "/static/images/cascos/Alpinestars-SM5 izquierda.png",
                "/static/images/cascos/Alpinestars-SM5 derecha.png",
                "/static/images/cascos/Alpinestars-SM5 trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.260 g (± 50 g)",
                "Material": "Polímero termoinyectado + EPS de 5 densidades",
                "Interior": "Silverplus® antibacteriano y desmontable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro / Rojo", "ALP-SM5-NR-S", 2),
                ("M", "Negro / Rojo", "ALP-SM5-NR-M", 5),
                ("L", "Negro / Rojo", "ALP-SM5-NR-L", 3),
                ("XL", "Negro / Rojo", "ALP-SM5-NR-XL", 0),
            ],
        },
        {
            "name": "Casco Bell Moto-9 MIPS Fasthouse",
            "slug": "bell-moto-9-mips-fasthouse",
            "brand": "Bell",
            "category": cats["cascos"],
            "price": 510000,
            "compare_at_price": 575000,
            "is_featured": True,
            "description": "Colaboración oficial Bell x Fasthouse. Calota en Tri-Matrix ultraliviana con protección rotacional MIPS, cierre Doble D acolchado y estética californiana.",
            "images": [
                "/static/images/cascos/Bell-Moto-9-Mips Fasthouse frontal.png",
                "/static/images/cascos/Bell-Moto-9-Mips Fasthouse izquierda.png",
                "/static/images/cascos/Bell-Moto-9-Mips Fasthouse derecha.png",
                "/static/images/cascos/Bell-Moto-9-Mips Fasthouse trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.05 / DOT",
                "Peso aproximado": "1.450 g (± 50 g)",
                "Material": "Tri-Matrix Composite + MIPS",
                "Interior": "X-Static® desmontable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro Mate", "BELL-FH-S", 2),
                ("M", "Negro Mate", "BELL-FH-M", 2),
                ("L", "Negro Mate", "BELL-FH-L", 0),
                ("XL", "Negro Mate", "BELL-FH-XL", 1),
            ],
        },
        {
            "name": "Casco Fox V1 Azul Racing",
            "slug": "fox-v1-azul-racing",
            "brand": "Fox",
            "category": cats["cascos"],
            "price": 320000,
            "compare_at_price": 365000,
            "is_featured": True,
            "description": "El referente de entrada de gama profesional. Homologación ECE 22.06, sistema MIPS y visera magnética MVRS™.",
            "images": [
                "/static/images/cascos/Fox-V1-Azul frontal.png",
                "/static/images/cascos/Fox-V1-Azul izquierda.png",
                "/static/images/cascos/Fox-V1-Azul derecha.png",
                "/static/images/cascos/Fox-V1-Azul trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.390 g (± 50 g)",
                "Material": "Policarbonato / ABS inyectado + MIPS",
                "Interior": "Desmontable y lavable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Azul", "FOX-V1-AZ-S", 4),
                ("M", "Azul", "FOX-V1-AZ-M", 5),
                ("L", "Azul", "FOX-V1-AZ-L", 4),
                ("XL", "Azul", "FOX-V1-AZ-XL", 2),
            ],
        },
        {
            "name": "Casco Troy Lee Designs SE4 Pinstripe Carbono",
            "slug": "troy-lee-designs-se4-pinstripe-carbono",
            "brand": "Troy Lee Designs",
            "category": cats["cascos"],
            "price": 620000,
            "compare_at_price": 690000,
            "is_featured": True,
            "description": "Edición Pinstripe en Carbono con detalles dorados. Incluye bolso oficial TLD, visera adicional y sistema MIPS integrado.",
            "images": [
                "/static/images/cascos/Troy Lee Designs-SE4-Pinstripe-Carbono frontal.png",
                "/static/images/cascos/Troy Lee Designs-SE4-Pinstripe-Carbono izquierda.png",
                "/static/images/cascos/Troy Lee Designs-SE4-Pinstripe-Carbono derecha.png",
                "/static/images/cascos/Troy Lee Designs-SE4-Pinstripe-Carbono trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.05 / DOT",
                "Peso aproximado": "1.325 g (± 50 g)",
                "Material": "Fibra de Carbono / Aramida + MIPS",
                "Interior": "Coolmax® y Dri-Lex® desmontable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro / Dorado", "TLD-SE4P-S", 0),
                ("M", "Negro / Dorado", "TLD-SE4P-M", 1),
                ("L", "Negro / Dorado", "TLD-SE4P-L", 2),
                ("XL", "Negro / Dorado", "TLD-SE4P-XL", 0),
            ],
        },
        {
            "name": "Casco Alpinestars S-M5 Tricolor",
            "slug": "alpinestars-sm5-tricolor",
            "brand": "Alpinestars",
            "category": cats["cascos"],
            "price": 395000,
            "compare_at_price": None,
            "is_featured": False,
            "description": "Edición gráfica Tricolor del aclamado Alpinestars S-M5. Diseño de perfil lateral elevado para proteger la clavícula y doble anillo D en acero inoxidable.",
            "images": [
                "/static/images/cascos/Alpinestars-SM5 Tricolor frontal.png",
                "/static/images/cascos/Alpinestars-SM5 Tricolor izquierda.png",
                "/static/images/cascos/Alpinestars-SM5 Tricolor derecha.png",
                "/static/images/cascos/Alpinestars-SM5 Tricolor trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.260 g (± 50 g)",
                "Material": "Polímero termoinyectado + EPS de 5 densidades",
                "Interior": "Silverplus® desmontable y lavable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Tricolor", "ALP-SM5-TRI-S", 1),
                ("M", "Tricolor", "ALP-SM5-TRI-M", 3),
                ("L", "Tricolor", "ALP-SM5-TRI-L", 2),
                ("XL", "Tricolor", "ALP-SM5-TRI-XL", 2),
            ],
        },
        {
            "name": "Casco Fox V1 Rojo Pro",
            "slug": "fox-v1-rojo-pro",
            "brand": "Fox",
            "category": cats["cascos"],
            "price": 320000,
            "compare_at_price": None,
            "is_featured": False,
            "description": "Fox V1 en combinación Rojo / Negro de alto contraste. Máxima visibilidad en pista, 7 entradas de aire frontales y 4 salidas traseras.",
            "images": [
                "/static/images/cascos/Fox-V1-Rojo frontal.png",
                "/static/images/cascos/Fox-V1-Rojo izquierda.png",
                "/static/images/cascos/Fox-V1-Rojo derecha.png",
                "/static/images/cascos/Fox-V1-Rojo trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.06 / DOT",
                "Peso aproximado": "1.390 g (± 50 g)",
                "Material": "Policarbonato / ABS inyectado + MIPS",
                "Interior": "Desmontable y lavable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Rojo / Negro", "FOX-V1-RJ-S", 3),
                ("M", "Rojo / Negro", "FOX-V1-RJ-M", 6),
                ("L", "Rojo / Negro", "FOX-V1-RJ-L", 3),
                ("XL", "Rojo / Negro", "FOX-V1-RJ-XL", 1),
            ],
        },
        {
            "name": "Casco Airoh Switch Spacer",
            "slug": "airoh-switch-spacer",
            "brand": "Airoh",
            "category": cats["cascos"],
            "price": 215000,
            "compare_at_price": 259000,
            "is_featured": False,
            "description": "Diseño italiano con excelente relación peso-precio. Ideal para enduro y motocross recreativo o iniciación competitiva.",
            "images": [
                "/static/images/cascos/Airoh-Switch Spacer frontal.png",
                "/static/images/cascos/Airoh-Switch Spacer izquierda.png",
                "/static/images/cascos/Airoh-Switch Spacer derecha.png",
                "/static/images/cascos/Airoh-Switch Spacer trasera.png",
            ],
            "specs": {
                "Homologación": "ECE 22.05",
                "Peso aproximado": "1.270 g (± 50 g)",
                "Material": "Termoplástico HRT de alta resistencia",
                "Interior": "Hipoalergénico, desmontable y lavable",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro / Naranja", "AIR-SW-S", 3),
                ("M", "Negro / Naranja", "AIR-SW-M", 2),
                ("L", "Negro / Naranja", "AIR-SW-L", 1),
                ("XL", "Negro / Naranja", "AIR-SW-XL", 0),
            ],
        },
        {
            "name": "Casco Troy Lee Designs D4 Downhill / BMX",
            "slug": "troy-lee-designs-d4-dh",
            "brand": "Troy Lee Designs",
            "category": cats["cascos"],
            "price": 350000,
            "compare_at_price": 410000,
            "is_featured": False,
            "description": "El rey indiscutido del Downhill y BMX Race. Ultraliviano, con protección MIPS C2 y sistema de protección de clavícula integrado.",
            "images": [
                "/static/images/cascos/Troy Lee Designs-D4 frontal.png",
                "/static/images/cascos/Troy Lee Designs-D4 izquierda.png",
                "/static/images/cascos/Troy Lee Designs-D4 derecha.png",
                "/static/images/cascos/Troy Lee Designs-D4 trasera.png",
            ],
            "specs": {
                "Homologación": "ASTM F1952 DH / CPSC 1203 / CE EN1078",
                "Peso aproximado": "1.050 g (± 50 g)",
                "Material": "Compuesto aeroespacial + MIPS C2",
                "Interior": "X-Static® XT2 antimicrobiano",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Azul / Negro", "TLD-D4-S", 2),
                ("M", "Azul / Negro", "TLD-D4-M", 3),
                ("L", "Azul / Negro", "TLD-D4-L", 1),
                ("XL", "Azul / Negro", "TLD-D4-XL", 0),
            ],
        },
        {
            "name": "Antiparras 100% Armega HiPER Mirror",
            "slug": "antiparras-100-armega-hiper",
            "brand": "100%",
            "category": cats["antiparras"],
            "price": 145000,
            "compare_at_price": 169000,
            "is_featured": False,
            "description": "Lente inyectado Ultra HD irrompible de 2mm con tecnología HiPER que realza el contraste del terreno. Espuma facial perforada de triple capa.",
            "images": ["/static/images/cat-gafas.jpg"],
            "specs": {
                "Homologación": "Impact Rated Ultra HD",
                "Peso aproximado": "185 g",
                "Material": "Marco dual-injected + Lente policarbonato 2mm",
                "Interior": "Espuma triple capa con manejo de sudor",
                "Condición": "Nuevo",
            },
            "variants": [
                ("Único", "Espejado Azul", "100-ARM-AZ", 7),
                ("Único", "Espejado Rojo", "100-ARM-RJ", 2),
            ],
        },
        {
            "name": "Conjunto Off-Road Whip Pro Jersey + Pantalón",
            "slug": "conjunto-off-road-whip-pro",
            "brand": "Fox",
            "category": cats["indumentaria"],
            "price": 265000,
            "compare_at_price": 298000,
            "is_featured": False,
            "description": "Conjunto liviano y respirable para motocross y enduro. Pantalón con paneles elásticos TruMotion® y refuerzos en cuero bovino en rodillas.",
            "images": ["/static/images/cat-indumentaria.jpg"],
            "specs": {
                "Homologación": "Uso Off-Road / Competición",
                "Peso aproximado": "920 g (conjunto)",
                "Material": "Poliéster 600D + TruMotion® + Cuero en rodillas",
                "Interior": "Malla ventilada anti-rozaduras",
                "Condición": "Nuevo",
            },
            "variants": [
                ("S", "Negro / Gris", "WHIP-SET-S", 3),
                ("M", "Negro / Gris", "WHIP-SET-M", 4),
                ("L", "Negro / Gris", "WHIP-SET-L", 2),
                ("XL", "Negro / Gris", "WHIP-SET-XL", 1),
            ],
        },
    ]

    variant_lookup = {}
    for pdata in products_data:
        prod = Product(
            name=pdata["name"],
            slug=pdata["slug"],
            brand=pdata["brand"],
            category=pdata["category"],
            price=pdata["price"],
            compare_at_price=pdata["compare_at_price"],
            transfer_discount=15,
            is_active=True,
            is_featured=pdata["is_featured"],
            description=pdata["description"],
            images_json=pdata["images"],
            specs_json=pdata["specs"],
        )
        db.session.add(prod)
        db.session.flush()

        for size, color, sku, stock in pdata["variants"]:
            var = ProductVariant(
                product_id=prod.id, size=size, color=color, sku=sku, stock=stock
            )
            db.session.add(var)
            db.session.flush()
            variant_lookup[sku] = (prod, var)

    # Pedidos de ejemplo iniciales para el panel /admin
    p1, v1 = variant_lookup["TLD-GP-L"]
    ord1 = Order(
        order_number=1001,
        customer_name="Lucas Fernández",
        customer_email="lucas.fernandez@gmail.com",
        customer_phone="+54 9 11 5432-8891",
        shipping_address="Av. Libertador 4250, Piso 3",
        postal_code="1426",
        city="Palermo",
        province="CABA",
        payment_method="TRANSFERENCIA",
        payment_status="PAID",
        shipping_status="SHIPPED",
        tracking_code="CA-889421004AR",
        subtotal=455000,
        discount_amount=68250,
        shipping_cost=0,
        total=386750,
    )
    db.session.add(ord1)
    db.session.flush()
    db.session.add(
        OrderItem(
            order_id=ord1.id,
            variant_id=v1.id,
            product_name=p1.name,
            variant_label=f"Talle {v1.size} · {v1.color}",
            image_url=p1.images_json[0],
            quantity=1,
            unit_price=p1.price,
        )
    )

    p2, v2 = variant_lookup["ALP-SM5-NR-M"]
    ord2 = Order(
        order_number=1002,
        customer_name="Martín Gómez",
        customer_email="martin.mx@hotmail.com",
        customer_phone="+54 9 351 612-3340",
        shipping_address="Bv. San Juan 890",
        postal_code="5000",
        city="Córdoba",
        province="Córdoba",
        payment_method="MERCADOPAGO",
        payment_status="PAID",
        shipping_status="PREPARING",
        subtotal=395000,
        discount_amount=0,
        shipping_cost=0,
        total=395000,
    )
    db.session.add(ord2)
    db.session.flush()
    db.session.add(
        OrderItem(
            order_id=ord2.id,
            variant_id=v2.id,
            product_name=p2.name,
            variant_label=f"Talle {v2.size} · {v2.color}",
            image_url=p2.images_json[0],
            quantity=1,
            unit_price=p2.price,
        )
    )

    db.session.commit()
