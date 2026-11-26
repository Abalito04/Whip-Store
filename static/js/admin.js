(function () {
  let state = { products: [], orders: [], low_stock: [] };
  let activeTab = "dashboard";
  let productSearch = "";
  let orderFilter = "ALL";

  function formatARS(n) {
    return "$ " + Math.round(Number(n) || 0).toLocaleString("es-AR");
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function loadState() {
    const res = await fetch("/api/admin/state");
    if (res.status === 401) {
      window.location.reload();
      return;
    }
    const data = await res.json();
    if (data.ok) {
      state = data;
      renderAll();
    }
  }

  function renderAll() {
    document.getElementById("tabCountProducts").textContent = `(${state.products.length})`;
    document.getElementById("tabCountOrders").textContent = `(${state.orders.length})`;
    renderDashboard();
    renderProducts();
    renderOrders();
  }

  function renderDashboard() {
    const paidOrders = state.orders.filter((o) => o.payment_status === "PAID");
    const totalSales = paidOrders.reduce((s, o) => s + o.total, 0);
    const pendingShip = state.orders.filter(
      (o) =>
        o.payment_status !== "CANCELLED" &&
        (o.shipping_status === "UNFULFILLED" || o.shipping_status === "PREPARING")
    ).length;
    const activeProds = state.products.filter((p) => p.is_active).length;

    document.getElementById("kpiSales").textContent = formatARS(totalSales);
    document.getElementById("kpiSalesSub").textContent = `${paidOrders.length} pedidos confirmados`;
    document.getElementById("kpiPending").textContent = String(pendingShip);
    document.getElementById("kpiProducts").textContent = `${activeProds} / ${state.products.length}`;
    document.getElementById("kpiLowStock").textContent = String(state.low_stock.length);

    const tbody = document.getElementById("lowStockTableBody");
    if (!tbody) return;
    tbody.innerHTML = state.low_stock
      .slice(0, 10)
      .map(
        (a) => `
      <tr>
        <td><strong>${a.product_name}</strong></td>
        <td><strong>${a.size}</strong></td>
        <td style="font-family:monospace; color:#6b7280; font-size:12px;">${a.sku}</td>
        <td>
          <span class="badge ${a.stock === 0 ? "badge-sale" : "badge-low"}">
            ${a.stock === 0 ? "SIN STOCK" : a.stock + " u."}
          </span>
        </td>
        <td style="text-align:right;">
          <button class="btn btn-dark" style="height:30px; padding:0 12px; font-size:12px;" onclick="window.WhipAdmin.setStock(${a.variant_id}, ${a.stock + 3})">+3 u.</button>
        </td>
      </tr>
    `
      )
      .join("");
  }

  function renderProducts() {
    const tbody = document.getElementById("productsTableBody");
    if (!tbody) return;

    const q = productSearch.trim().toLowerCase();
    const list = q
      ? state.products.filter(
          (p) =>
            p.name.toLowerCase().includes(q) ||
            p.brand.toLowerCase().includes(q) ||
            p.variants.some((v) => v.sku.toLowerCase().includes(q))
        )
      : state.products;

    tbody.innerHTML = list
      .map(
        (p) => `
      <tr>
        <td>
          <div style="display:flex; align-items:center; gap:10px;">
            <img src="${p.images[0] || "/static/images/cat-cascos.jpg"}" style="width:46px; height:46px; object-fit:contain; background:#f8f9fa; border:1px solid #e5e7eb; border-radius:8px; padding:3px;">
            <div>
              <strong>${p.name}</strong>
              <div style="font-size:11.5px; color:#6b7280;">${p.brand} · ${p.category_slug}</div>
            </div>
          </div>
        </td>
        <td>
          <input type="number" step="1000" value="${p.price}"
            onchange="window.WhipAdmin.setPrice(${p.id}, this.value)"
            style="width:115px; height:34px; padding:0 8px; border:1px solid #e5e7eb; border-radius:7px; font-weight:700; font-size:12.5px;">
        </td>
        <td>
          ${p.variants
            .map((v) => {
              const cls = v.stock === 0 ? "v-out" : v.stock <= 2 ? "v-low" : "v-ok";
              return `
                <span class="variant-chip ${cls}">
                  <span>${v.size}</span>
                  <button type="button" onclick="window.WhipAdmin.setStock(${v.id}, ${Math.max(0, v.stock - 1)})">−</button>
                  <span>${v.stock}</span>
                  <button type="button" onclick="window.WhipAdmin.setStock(${v.id}, ${v.stock + 1})">+</button>
                </span>
              `;
            })
            .join("")}
        </td>
        <td>
          <button type="button" onclick="window.WhipAdmin.toggleActive(${p.id}, ${!p.is_active})"
            class="badge ${p.is_active ? "badge-free" : "badge-out"}" style="border:none; cursor:pointer;">
            ${p.is_active ? "Activo" : "Pausado"}
          </button>
        </td>
        <td style="text-align:right; white-space:nowrap;">
          <a href="/producto/${p.slug}" target="_blank" style="font-size:12px; font-weight:700; margin-right:10px; color:#4b5563;">Ver ↗</a>
          <button type="button" onclick="window.WhipAdmin.deleteProduct(${p.id})" style="background:none; border:none; color:#e63946; cursor:pointer; font-weight:800;">✕</button>
        </td>
      </tr>
    `
      )
      .join("");
  }

  function renderOrders() {
    const wrap = document.getElementById("ordersListWrap");
    if (!wrap) return;

    const list =
      orderFilter === "ALL"
        ? state.orders
        : state.orders.filter((o) => o.payment_status === orderFilter);

    if (!list.length) {
      wrap.innerHTML = `<div class="card-panel" style="text-align:center; color:#6b7280;">No hay pedidos en este estado.</div>`;
      return;
    }

    wrap.innerHTML = list
      .map(
        (o) => `
      <div class="card-panel">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px; padding-bottom:12px; border-bottom:1px solid #f3f4f6;">
          <div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <strong style="font-size:16px;">Pedido #${o.order_number}</strong>
              <span class="badge ${o.payment_status === "PAID" ? "badge-free" : o.payment_status === "PENDING" ? "badge-low" : "badge-sale"}">
                ${o.payment_status === "PAID" ? "PAGADO" : o.payment_status === "PENDING" ? "PENDIENTE" : "CANCELADO"}
              </span>
              <span style="font-size:11px; font-weight:700; background:#f3f4f6; padding:3px 8px; border-radius:5px;">
                ${o.payment_method === "MERCADOPAGO" ? "Mercado Pago" : "Transferencia 15% OFF"}
              </span>
            </div>
            <div style="font-size:12.5px; color:#4b5563; margin-top:4px;">
              <strong>${esc(o.customer_name)}</strong> · ${esc(o.customer_email)} · ${esc(o.customer_phone)}
            </div>
            <div style="font-size:12px; color:#6b7280;">
              Envío: ${esc(o.shipping_address)}, ${esc(o.city)} (${esc(o.province)}) — CP ${esc(o.postal_code)}
            </div>
          </div>
          <div style="text-align:right;">
            <strong style="font-size:20px;">${formatARS(o.total)}</strong>
            <div style="font-size:11px; color:#9ca3af;">${esc(o.created_at)}</div>
          </div>
        </div>

        <div style="padding:12px 0; display:flex; flex-direction:column; gap:8px;">
          ${o.items
            .map(
              (item) => `
            <div style="display:flex; align-items:center; gap:10px; font-size:12.5px;">
              <img src="${esc(item.image_url)}" style="width:40px; height:40px; object-fit:contain; background:#f8f9fa; border:1px solid #e5e7eb; border-radius:6px; padding:2px;">
              <div style="flex:1;">
                <strong>${esc(item.product_name)}</strong>
                <div style="color:#6b7280; font-size:11.5px;">${esc(item.variant_label)} × ${item.quantity}</div>
              </div>
              <strong>${formatARS(item.unit_price * item.quantity)}</strong>
            </div>
          `
            )
            .join("")}
        </div>

        <div style="display:flex; flex-wrap:wrap; gap:10px; padding-top:12px; border-top:1px solid #f3f4f6; align-items:center;">
          <select onchange="window.WhipAdmin.updateOrder(${o.id}, {payment_status: this.value})" style="height:36px; padding:0 10px; border-radius:8px; border:1px solid #e5e7eb; font-size:12px; font-weight:700;">
            <option value="PENDING" ${o.payment_status === "PENDING" ? "selected" : ""}>Pago: Pendiente</option>
            <option value="PAID" ${o.payment_status === "PAID" ? "selected" : ""}>Pago: Pagado</option>
            <option value="CANCELLED" ${o.payment_status === "CANCELLED" ? "selected" : ""}>Pago: Cancelado</option>
          </select>

          <select onchange="window.WhipAdmin.updateOrder(${o.id}, {shipping_status: this.value})" style="height:36px; padding:0 10px; border-radius:8px; border:1px solid #e5e7eb; font-size:12px; font-weight:700;">
            <option value="UNFULFILLED" ${o.shipping_status === "UNFULFILLED" ? "selected" : ""}>Envío: Sin preparar</option>
            <option value="PREPARING" ${o.shipping_status === "PREPARING" ? "selected" : ""}>Envío: Preparando</option>
            <option value="SHIPPED" ${o.shipping_status === "SHIPPED" ? "selected" : ""}>Envío: Despachado</option>
            <option value="DELIVERED" ${o.shipping_status === "DELIVERED" ? "selected" : ""}>Envío: Entregado</option>
          </select>

          <input type="text" value="${esc(o.tracking_code || "")}" placeholder="Código tracking (ej: CA-12345AR)"
            onblur="window.WhipAdmin.updateOrder(${o.id}, {tracking_code: this.value})"
            style="height:36px; padding:0 10px; border-radius:8px; border:1px solid #e5e7eb; font-size:12px; font-family:monospace; flex:1; min-width:190px;">

          ${
            o.payment_status !== "CANCELLED" && !o.stock_restored
              ? `<button type="button" onclick="window.WhipAdmin.restoreStock(${o.id})" style="height:36px; padding:0 12px; border-radius:8px; border:1px solid #fecaca; background:#fef2f2; color:#e63946; font-size:12px; font-weight:700; cursor:pointer;">Cancelar y revertir stock</button>`
              : o.stock_restored
              ? `<span style="font-size:12px; font-weight:700; color:#00A650;">✓ Stock reintegrado</span>`
              : ""
          }
        </div>
      </div>
    `
      )
      .join("");
  }

  function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll(".admin-tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    document.querySelectorAll(".admin-panel").forEach((p) => {
      p.style.display = p.id === `panel-${tab}` ? "block" : "none";
    });
  }

  window.WhipAdmin = {
    switchTab,
    setOrderFilter(f, btn) {
      orderFilter = f;
      document.querySelectorAll(".order-filter-btn").forEach((b) => b.classList.remove("active"));
      btn?.classList.add("active");
      renderOrders();
    },
    async setStock(variantId, stock) {
      await fetch(`/api/admin/variant/${variantId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stock }),
      });
      await loadState();
    },
    async setPrice(productId, price) {
      await fetch(`/api/admin/product/${productId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price: Number(price) }),
      });
      await loadState();
    },
    async toggleActive(productId, is_active) {
      await fetch(`/api/admin/product/${productId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active }),
      });
      await loadState();
    },
    async deleteProduct(productId) {
      if (!confirm("¿Eliminar este producto del catálogo?")) return;
      await fetch(`/api/admin/product/${productId}`, { method: "DELETE" });
      await loadState();
    },
    async updateOrder(orderId, payload) {
      await fetch(`/api/admin/order/${orderId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await loadState();
    },
    async restoreStock(orderId) {
      await fetch(`/api/admin/order/${orderId}/restore-stock`, { method: "POST" });
      await loadState();
    },
    async logout() {
      await fetch("/api/admin/logout", { method: "POST" });
      window.location.reload();
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    // Login form
    const loginForm = document.getElementById("adminLoginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("loginEmail").value;
        const password = document.getElementById("loginPassword").value;
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (data.ok) {
          window.location.reload();
        } else {
          document.getElementById("loginError").textContent = data.error || "Error de acceso";
        }
      });
      return;
    }

    // Authenticated dashboard
    loadState();

    document.getElementById("adminProductSearch")?.addEventListener("input", (e) => {
      productSearch = e.target.value;
      renderProducts();
    });

    const newProdForm = document.getElementById("newProductForm");
    newProdForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById("npName").value,
        brand: document.getElementById("npBrand").value,
        category_slug: document.getElementById("npCategory").value,
        price: Number(document.getElementById("npPrice").value),
        color: document.getElementById("npColor").value,
        stock_m: Number(document.getElementById("npStockM").value),
        stock_l: Number(document.getElementById("npStockL").value),
      };
      await fetch("/api/admin/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      document.getElementById("newProductModal").classList.remove("open");
      newProdForm.reset();
      await loadState();
    });
  });
})();
