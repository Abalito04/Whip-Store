(function () {
  const CART_KEY = "whip_py_cart_v1";
  const FREE_SHIPPING_THRESHOLD = 250000;
  const TRANSFER_DISCOUNT_PCT = 15;

  const ANNOUNCEMENTS = [
    "🚚 Envío GRATIS a todo el país en compras superiores a $250.000",
    "💳 Hasta 6 CUOTAS SIN INTERÉS con todas las tarjetas",
    "💸 15% OFF abonando por Transferencia Bancaria",
  ];

  function formatARS(amount) {
    const num = Math.round(Number(amount) || 0);
    return "$ " + num.toLocaleString("es-AR");
  }

  function getCart() {
    try {
      const raw = localStorage.getItem(CART_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    renderCartUI();
  }

  function addToCart(item) {
    const cart = getCart();
    const existing = cart.find((c) => c.variant_id === item.variant_id);
    const nextQty = (existing ? existing.quantity : 0) + (item.quantity || 1);

    if (item.max_stock <= 0) {
      return { ok: false, error: "Sin stock disponible para este talle." };
    }
    if (nextQty > item.max_stock) {
      return {
        ok: false,
        error: `Solo quedan ${item.max_stock} unidad(es) en stock para talle ${item.size}.`,
      };
    }

    if (existing) {
      existing.quantity = nextQty;
      existing.max_stock = item.max_stock;
    } else {
      cart.push({
        product_id: item.product_id,
        variant_id: item.variant_id,
        name: item.name,
        slug: item.slug,
        size: item.size,
        color: item.color,
        price: item.price,
        image: item.image,
        max_stock: item.max_stock,
        quantity: item.quantity || 1,
      });
    }

    saveCart(cart);
    openCart();
    return { ok: true };
  }

  function updateQty(variantId, delta) {
    const cart = getCart();
    const idx = cart.findIndex((c) => c.variant_id === variantId);
    if (idx === -1) return;
    const next = cart[idx].quantity + delta;
    if (next <= 0) {
      cart.splice(idx, 1);
    } else {
      cart[idx].quantity = Math.min(next, Math.max(1, cart[idx].max_stock || 99));
    }
    saveCart(cart);
  }

  function removeItem(variantId) {
    const cart = getCart().filter((c) => c.variant_id !== variantId);
    saveCart(cart);
  }

  function clearCart() {
    saveCart([]);
  }

  function openCart() {
    document.getElementById("cartBackdrop")?.classList.add("open");
    document.getElementById("cartDrawer")?.classList.add("open");
  }

  function closeCart() {
    document.getElementById("cartBackdrop")?.classList.remove("open");
    document.getElementById("cartDrawer")?.classList.remove("open");
  }

  function renderCartUI() {
    const cart = getCart();
    const totalCount = cart.reduce((acc, i) => acc + i.quantity, 0);
    const subtotal = cart.reduce((acc, i) => acc + i.price * i.quantity, 0);

    const badge = document.getElementById("headerCartCount");
    const headerTotal = document.getElementById("headerCartTotal");
    if (badge) badge.textContent = String(totalCount);
    if (headerTotal) headerTotal.textContent = formatARS(subtotal);

    // Progress bar
    const progressText = document.getElementById("cartFreeShippingText");
    const progressFill = document.getElementById("cartFreeShippingFill");
    if (progressText && progressFill) {
      const missing = Math.max(0, FREE_SHIPPING_THRESHOLD - subtotal);
      const pct = Math.min(100, (subtotal / FREE_SHIPPING_THRESHOLD) * 100);
      progressFill.style.width = `${pct}%`;
      if (subtotal > 0 && missing === 0) {
        progressText.innerHTML = `<span style="color:#00A650">🎉 ¡Genial! Tenés <strong>ENVÍO GRATIS</strong> a todo el país</span>`;
      } else {
        progressText.innerHTML = `🚚 Te faltan <strong>${formatARS(missing)}</strong> para <span style="color:#00A650">envío gratis</span>`;
      }
    }

    const listEl = document.getElementById("cartItemsList");
    const footEl = document.getElementById("cartFooter");
    if (!listEl || !footEl) return;

    if (cart.length === 0) {
      listEl.innerHTML = `
        <div style="text-align:center; padding: 48px 16px;">
          <div style="font-size:36px; margin-bottom:10px;">🛍️</div>
          <p style="font-weight:800; margin:0 0 6px;">Tu carrito está vacío</p>
          <p style="font-size:13px; color:#6b7280; margin:0 0 20px;">Elegí tu casco favorito y aprovechá hasta 6 cuotas sin interés.</p>
          <button type="button" class="btn btn-dark" onclick="window.WhipStore.closeCart()">Seguir comprando</button>
        </div>
      `;
      footEl.style.display = "none";
      return;
    }

    footEl.style.display = "block";
    listEl.innerHTML = cart
      .map(
        (item) => `
      <div class="cart-item">
        <a href="/producto/${item.slug}">
          <img src="${item.image}" alt="${item.name}">
        </a>
        <div style="flex:1; min-width:0;">
          <div style="display:flex; justify-content:space-between; gap:8px;">
            <a href="/producto/${item.slug}" style="font-size:13px; font-weight:700; line-height:1.3;">${item.name}</a>
            <button type="button" onclick="window.WhipStore.removeItem(${item.variant_id})" style="background:none; border:none; color:#9ca3af; cursor:pointer;" title="Quitar">✕</button>
          </div>
          <div style="font-size:11.5px; color:#6b7280; margin-top:2px;">Talle <strong>${item.size}</strong> · ${item.color}</div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
            <div class="qty-box">
              <button type="button" onclick="window.WhipStore.updateQty(${item.variant_id}, -1)">−</button>
              <span>${item.quantity}</span>
              <button type="button" onclick="window.WhipStore.updateQty(${item.variant_id}, 1)" ${item.quantity >= item.max_stock ? "disabled style='opacity:0.35'" : ""}>+</button>
            </div>
            <strong style="font-size:14px;">${formatARS(item.price * item.quantity)}</strong>
          </div>
        </div>
      </div>
    `
      )
      .join("");

    const transferTotal = Math.round(subtotal * (1 - TRANSFER_DISCOUNT_PCT / 100));
    const subEl = document.getElementById("cartSubtotal");
    const trEl = document.getElementById("cartTransferTotal");
    if (subEl) subEl.textContent = formatARS(subtotal);
    if (trEl) trEl.textContent = formatARS(transferTotal);
  }

  // Topbar rotation
  function initTopbar() {
    const el = document.getElementById("topbarText");
    if (!el) return;
    let idx = 0;
    const render = () => (el.textContent = ANNOUNCEMENTS[idx]);
    document.getElementById("topbarPrev")?.addEventListener("click", () => {
      idx = (idx - 1 + ANNOUNCEMENTS.length) % ANNOUNCEMENTS.length;
      render();
    });
    document.getElementById("topbarNext")?.addEventListener("click", () => {
      idx = (idx + 1) % ANNOUNCEMENTS.length;
      render();
    });
    setInterval(() => {
      idx = (idx + 1) % ANNOUNCEMENTS.length;
      render();
    }, 4500);
  }

  // Live search
  function initSearch() {
    const input = document.getElementById("desktopSearchInput");
    const dropdown = document.getElementById("desktopSearchDropdown");
    if (!input || !dropdown) return;

    let timer = null;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) {
        dropdown.classList.remove("open");
        dropdown.innerHTML = "";
        return;
      }
      timer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
          const items = await res.json();
          if (!items.length) {
            dropdown.innerHTML = `<div style="padding:14px; font-size:13px; color:#6b7280; text-align:center;">Sin resultados para "${q}"</div>`;
          } else {
            dropdown.innerHTML = items
              .map(
                (p) => `
              <a class="search-item" href="/producto/${p.slug}">
                <img src="${p.images[0] || "/static/images/cat-cascos.jpg"}" alt="${p.name}">
                <div class="search-item-info">
                  <div class="search-item-title">${p.name}</div>
                  <div class="search-item-brand">${p.brand}</div>
                </div>
                <div class="search-item-price">${formatARS(p.price)}</div>
              </a>
            `
              )
              .join("");
          }
          dropdown.classList.add("open");
        } catch {
          // ignore
        }
      }, 180);
    });

    document.addEventListener("click", (e) => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("open");
      }
    });
  }

  // Mobile menu
  function initMobileMenu() {
    const btn = document.getElementById("mobileMenuBtn");
    const backdrop = document.getElementById("mobileDrawerBackdrop");
    const drawer = document.getElementById("mobileDrawer");
    const closeBtn = document.getElementById("mobileDrawerClose");
    if (!btn || !backdrop || !drawer) return;

    const close = () => {
      backdrop.classList.remove("open");
      drawer.classList.remove("open");
    };
    btn.addEventListener("click", () => {
      backdrop.classList.add("open");
      drawer.classList.add("open");
    });
    backdrop.addEventListener("click", close);
    closeBtn?.addEventListener("click", close);
  }

  window.WhipStore = {
    formatARS,
    getCart,
    addToCart,
    updateQty,
    removeItem,
    clearCart,
    openCart,
    closeCart,
    FREE_SHIPPING_THRESHOLD,
    TRANSFER_DISCOUNT_PCT,
  };

  document.addEventListener("DOMContentLoaded", () => {
    initTopbar();
    initSearch();
    initMobileMenu();
    renderCartUI();
  });
})();
