(function () {
  const fmt = (n) => "$ " + Math.round(Number(n) || 0).toLocaleString("es-AR");

  const state = {
    products: [],
    lowStock: [],
    activeSession: null,
    closedSessions: [],
    recentSales: [],
    recentMovements: [],
    cart: [], // { variant_id, product_id, name, size, color, sku, price, stock, quantity }
    selectedCategory: "todas",
    selectedSubcat: "",
    selectedBrand: "TODAS",
    salesFilter: "ALL",
    stockPage: 1,
    stockPageSize: 10,
    channel: "LOCAL",
    paymentMethod: "EFECTIVO",
  };

  function toast(msg, isError = false) {
    const el = document.getElementById("posToast");
    if (!el) return;
    el.textContent = msg;
    el.className = "pos-toast show" + (isError ? " error" : "");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 2800);
  }

  // ---------------- LOGIN ----------------
  const loginForm = document.getElementById("posLoginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("posLoginEmail").value.trim();
      const password = document.getElementById("posLoginPassword").value.trim();
      const err = document.getElementById("posLoginError");
      err.textContent = "";
      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (data.ok) {
          window.location.reload();
        } else {
          err.textContent = data.error || "Error de acceso";
        }
      } catch {
        err.textContent = "Error de conexión.";
      }
    });
    return;
  }

  // ---------------- STATE FETCH ----------------
  async function loadState() {
    try {
      const res = await fetch("/api/pos/state");
      if (res.status === 401) {
        window.location.reload();
        return;
      }
      const data = await res.json();
      if (!data.ok) return;

      state.products = data.products || [];
      state.lowStock = data.low_stock || [];
      state.activeSession = data.active_session || null;
      state.closedSessions = data.closed_sessions || [];
      state.recentSales = data.recent_sales || [];
      state.recentMovements = data.recent_movements || [];

      renderHeaderStatus();
      renderBrands();
      renderCatalog();
      renderStockTab();
      renderCart();
      renderCashTab();
      renderStockMovementsTab();
      renderRecentSalesTab();
    } catch (e) {
      toast("No se pudo actualizar el estado del POS", true);
    }
  }

  function renderHeaderStatus() {
    const pill = document.getElementById("cashStatusPill");
    const dot = document.getElementById("cashStatusDot");
    const txt = document.getElementById("cashStatusText");
    if (!pill) return;
    if (state.activeSession) {
      pill.className = "pos-status-pill open";
      dot.textContent = "🟢";
      txt.textContent = "Caja Abierta · " + fmt(state.activeSession.expected_cash);
    } else {
      pill.className = "pos-status-pill closed";
      dot.textContent = "🔴";
      txt.textContent = "Caja Cerrada (Abrir)";
    }
  }

  // ---------------- CATALOG & SCANNER ----------------
  function matchesPosCategory(p, cat) {
    if (cat === "todas") return true;
    if (cat === "outlet") return Boolean(p.is_outlet);
    if (p.category_slug !== cat) return false;
    if (cat === "indumentaria" && state.selectedSubcat) {
      return (p.subcategory || "") === state.selectedSubcat;
    }
    return true;
  }

  function renderBrands() {
    const activeProds = state.products.filter((p) => p.is_active);
    const setCnt = (id, n) => {
      const el = document.getElementById(id);
      if (el) el.textContent = `${n} u.`;
    };
    setCnt("posCatCountTodas", activeProds.length);
    setCnt("posCatCountCascos", activeProds.filter((p) => p.category_slug === "cascos").length);
    setCnt("posCatCountIndumentaria", activeProds.filter((p) => p.category_slug === "indumentaria").length);
    setCnt("posCatCountAntiparras", activeProds.filter((p) => p.category_slug === "antiparras").length);
    setCnt("posCatCountOutlet", activeProds.filter((p) => p.is_outlet).length);

    const drawer = document.getElementById("posBrandDrawer");
    const subWrap = document.getElementById("posSubcatWrap");
    const wrap = document.getElementById("posBrandPills");
    if (!drawer || !wrap) return;

    if (state.selectedCategory === "todas") {
      drawer.style.display = "none";
      return;
    }
    if (subWrap) {
      subWrap.style.display = state.selectedCategory === "indumentaria" ? "block" : "none";
    }
    const catProds = activeProds.filter((p) => matchesPosCategory(p, state.selectedCategory));
    const brands = ["TODAS", ...Array.from(new Set(catProds.map((p) => p.brand))).sort()];
    wrap.innerHTML = brands
      .map(
        (b) =>
          `<button type="button" class="pill-btn ${state.selectedBrand === b ? "active" : ""}" onclick="window.WhipPOS.setBrand('${b.replace(/'/g, "\\'")}')">${b === "TODAS" ? "Todas las marcas" : b}</button>`
      )
      .join("");
    drawer.style.display = "block";
  }

  function renderCatalog() {
    const grid = document.getElementById("posCatalogGrid");
    if (!grid) return;
    const q = (document.getElementById("posScannerInput")?.value || "").trim().toLowerCase();

    const filtered = state.products.filter((p) => {
      if (!p.is_active) return false;
      if (!matchesPosCategory(p, state.selectedCategory)) return false;
      if (state.selectedBrand !== "TODAS" && p.brand !== state.selectedBrand) return false;
      if (!q) return true;
      const inMeta = p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q);
      const inSku = p.variants.some((v) => v.sku.toLowerCase().includes(q));
      return inMeta || inSku;
    });

    if (!filtered.length) {
      grid.innerHTML = `<div class="card-panel" style="grid-column:1/-1; padding:26px; text-align:center; color:var(--muted);">No se encontraron productos con ese filtro.</div>`;
      return;
    }

    grid.innerHTML = filtered
      .map((p) => {
        const img = (p.images && p.images[0]) || "/static/images/cat-cascos.jpg";
        const variantsHtml = p.variants
          .map((v) => {
            const disabled = v.stock <= 0 ? "disabled" : "";
            const lowCls = v.stock > 0 && v.stock <= 2 ? "low" : "";
            return `<button type="button" class="pos-size-btn ${lowCls}" ${disabled} title="SKU: ${v.sku}" onclick="event.stopPropagation(); window.WhipPOS.addVariant(${v.id})">
              <span>${v.size}</span>
              <span class="st-qty">${v.stock}</span>
            </button>`;
          })
          .join("");

        return `<article class="pos-card" onclick="window.WhipPOS.clickProductCard(${p.id})" title="Clic para agregar o elegir talle">
          <div class="pos-card-top">
            <div class="pos-card-thumb"><img src="${img}" alt="${p.name}"></div>
            <div class="pos-card-info">
              <div class="pos-card-brand">${p.brand}</div>
              <div class="pos-card-name">${p.name}</div>
              <div class="pos-card-price">${fmt(p.price)}</div>
              <div style="font-size:11px; color:#00a650; font-weight:700;">Ef/Tr: ${fmt(p.transfer_price)}</div>
            </div>
          </div>
          <div class="pos-variants">${variantsHtml}</div>
        </article>`;
      })
      .join("");
  }

  function clickProductCard(productId) {
    const p = state.products.find((x) => x.id === productId);
    if (!p) return;
    const available = (p.variants || []).filter((v) => v.stock > 0);
    if (available.length === 0) {
      toast("Sin stock disponible para " + p.name, true);
      return;
    }
    if (available.length === 1) {
      addVariant(available[0].id);
      return;
    }
    // Múltiples talles disponibles -> abrir selector rápido
    document.getElementById("pickVariantTitle").textContent = p.name;
    document.getElementById("pickVariantSub").textContent = `${p.brand} · Lista: ${fmt(p.price)} · Ef/Tr: ${fmt(p.transfer_price)}`;
    document.getElementById("pickVariantButtons").innerHTML = available
      .map(
        (v) => `<button type="button" class="btn btn-outline" style="height:52px; flex-direction:column; gap:2px; border-color:#111; color:#111;" onclick="window.WhipPOS.addVariant(${v.id}); document.getElementById('posPickVariantModal').classList.remove('open');">
          <strong style="font-size:15px;">Talle ${v.size}</strong>
          <span style="font-size:11px; color:#00a650; font-weight:700;">Stock: ${v.stock} u.</span>
        </button>`
      )
      .join("");
    document.getElementById("posPickVariantModal").classList.add("open");
  }

  function findVariantLocally(variantId) {
    for (const p of state.products) {
      const v = p.variants.find((x) => x.id === variantId);
      if (v) return { product: p, variant: v };
    }
    return null;
  }

  function addVariant(variantId) {
    const found = findVariantLocally(variantId);
    if (!found) return;
    const { product, variant } = found;
    if (variant.stock <= 0) {
      toast("Sin stock disponible para " + product.name + " (" + variant.size + ")", true);
      return;
    }
    const existing = state.cart.find((c) => c.variant_id === variant.id);
    if (existing) {
      if (existing.quantity >= variant.stock) {
        toast("Stock máximo alcanzado (" + variant.stock + " u.)", true);
        return;
      }
      existing.quantity += 1;
    } else {
      state.cart.push({
        variant_id: variant.id,
        product_id: product.id,
        name: product.name,
        size: variant.size,
        color: variant.color,
        sku: variant.sku,
        price: product.price,
        transfer_price: product.transfer_price,
        stock: variant.stock,
        quantity: 1,
      });
    }
    renderCart();
    toast(`+1 ${product.name} (${variant.size})`);
  }

  async function scanLookup() {
    const input = document.getElementById("posScannerInput");
    const code = (input?.value || "").trim();
    if (!code) return;
    try {
      const res = await fetch(`/api/pos/lookup?code=${encodeURIComponent(code)}`);
      const data = await res.json();
      if (data.ok && data.variant) {
        addVariant(data.variant.id);
        input.value = "";
        renderCatalog();
        input.focus();
      } else {
        toast(data.error || "SKU no encontrado", true);
      }
    } catch {
      toast("Error buscando SKU", true);
    }
  }

  const scannerInput = document.getElementById("posScannerInput");
  if (scannerInput) {
    scannerInput.addEventListener("input", renderCatalog);
    scannerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        scanLookup();
      }
    });
  }

  // ---------------- CART & CHECKOUT ----------------
  function renderCart() {
    const wrap = document.getElementById("posCartItems");
    const countLabel = document.getElementById("posCartCountLabel");
    if (!wrap) return;

    const totalUnits = state.cart.reduce((acc, i) => acc + i.quantity, 0);
    countLabel.textContent = `${totalUnits} ${totalUnits === 1 ? "ítem" : "ítems"}`;

    if (!state.cart.length) {
      wrap.innerHTML = `<div style="text-align:center; padding:28px 12px; color:var(--muted); font-size:13px;">Escaneá un SKU o tocá un talle para agregar productos al ticket.</div>`;
    } else {
      wrap.innerHTML = state.cart
        .map(
          (item) => `<div class="pos-cart-row">
            <div class="pos-cart-row-info">
              <div class="pos-cart-row-title">${item.name}</div>
              <div class="pos-cart-row-sub">Talle ${item.size} · ${item.sku} · ${fmt(item.price)}</div>
            </div>
            <div class="pos-qty-ctrl">
              <button type="button" onclick="window.WhipPOS.changeQty(${item.variant_id}, -1)">-</button>
              <strong style="min-width:20px; text-align:center; font-size:13px;">${item.quantity}</strong>
              <button type="button" onclick="window.WhipPOS.changeQty(${item.variant_id}, 1)">+</button>
            </div>
          </div>`
        )
        .join("");
    }

    const subtotal = state.cart.reduce((acc, i) => acc + i.price * i.quantity, 0);
    const applyCashPrice = Boolean(document.getElementById("posApplyTransferDiscount")?.checked);
    const manualDesc = Math.max(0, parseInt(document.getElementById("posManualDiscount")?.value || "0", 10) || 0);
    const autoCashDisc = applyCashPrice
      ? state.cart.reduce((acc, i) => acc + Math.max(0, i.price - (i.transfer_price ?? i.price)) * i.quantity, 0)
      : 0;
    const discount = Math.min(subtotal, autoCashDisc + manualDesc);
    const total = Math.max(0, subtotal - discount);

    document.getElementById("posSubtotal").textContent = fmt(subtotal);
    document.getElementById("posDiscount").textContent = "-" + fmt(discount);
    document.getElementById("posTotal").textContent = fmt(total);
  }

  function changeQty(variantId, delta) {
    const idx = state.cart.findIndex((c) => c.variant_id === variantId);
    if (idx === -1) return;
    const item = state.cart[idx];
    const next = item.quantity + delta;
    if (next <= 0) {
      state.cart.splice(idx, 1);
    } else if (next > item.stock) {
      toast("Stock máximo disponible: " + item.stock, true);
      return;
    } else {
      item.quantity = next;
    }
    renderCart();
  }

  async function submitSale() {
    if (!state.cart.length) {
      toast("Agregá productos al ticket primero.", true);
      return;
    }
    const btn = document.getElementById("posSubmitBtn");
    btn.disabled = true;
    btn.textContent = "Procesando venta...";

    try {
      const payRef = (document.getElementById("posPaymentRef")?.value || "").trim();
      const payload = {
        items: state.cart.map((c) => ({ variant_id: c.variant_id, quantity: c.quantity, unit_price: c.price })),
        channel: state.channel,
        payment_method: state.paymentMethod,
        payment_ref: payRef,
        notes: payRef ? `Comp: ${payRef}` : "",
        apply_transfer_discount: Boolean(document.getElementById("posApplyTransferDiscount")?.checked),
        discount_amount: parseInt(document.getElementById("posManualDiscount")?.value || "0", 10) || 0,
        customer_name: document.getElementById("posCustomerName")?.value.trim() || "Cliente Mostrador",
        customer_phone: document.getElementById("posCustomerPhone")?.value.trim() || "-",
      };

      const res = await fetch("/api/pos/sales", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!data.ok) {
        toast(data.error || "No se pudo registrar la venta", true);
        return;
      }

      state.cart = [];
      document.getElementById("posManualDiscount").value = "0";
      document.getElementById("posCustomerName").value = "";
      document.getElementById("posCustomerPhone").value = "";
      if (document.getElementById("posPaymentRef")) document.getElementById("posPaymentRef").value = "";
      document.getElementById("posApplyTransferDiscount").checked = state.paymentMethod === "EFECTIVO" || state.paymentMethod === "TRANSFERENCIA";

      toast(`✅ Venta #${data.order.order_number} registrada` + (data.cash_recorded ? " y sumada a Caja" : ""));
      openReceiptModal(data.order);
      await loadState();
    } catch {
      toast("Error de conexión al cobrar.", true);
    } finally {
      btn.disabled = false;
      btn.textContent = "✅ Cobrar y Descontar Stock";
    }
  }

  let currentReceiptOrder = null;

  function openReceiptModal(order) {
    currentReceiptOrder = order;
    const area = document.getElementById("receiptPrintArea");
    const waBtn = document.getElementById("receiptWhatsappBtn");
    const itemsRows = (order.items || [])
      .map(
        (i) => `<div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <span>${i.quantity}x ${i.product_name}<br><small>${i.variant_label}</small></span>
          <strong>${fmt(i.unit_price * i.quantity)}</strong>
        </div>`
      )
      .join("");

    area.innerHTML = `
      <h3>WHIP HELMETS ARGENTINA</h3>
      <div style="text-align:center; font-size:11px;">Comprobante interno de venta</div>
      <div class="receipt-divider"></div>
      <div><strong>Ticket:</strong> #${order.order_number}</div>
      <div><strong>Fecha:</strong> ${order.created_at}</div>
      <div><strong>Canal:</strong> ${order.channel} · <strong>Pago:</strong> ${order.payment_method}</div>
      ${order.notes ? `<div><strong>Comprobante:</strong> ${order.notes.replace(/^Comp:\s*/i, "")}</div>` : ""}
      <div><strong>Cliente:</strong> ${order.customer_name}</div>
      <div class="receipt-divider"></div>
      ${itemsRows}
      <div class="receipt-divider"></div>
      <div style="display:flex; justify-content:space-between;"><span>Subtotal:</span><span>${fmt(order.subtotal)}</span></div>
      ${order.discount_amount > 0 ? `<div style="display:flex; justify-content:space-between;"><span>Descuento:</span><span>-${fmt(order.discount_amount)}</span></div>` : ""}
      <div style="display:flex; justify-content:space-between; font-size:16px; font-weight:800; margin-top:4px;"><span>TOTAL:</span><span>${fmt(order.total)}</span></div>
      <div class="receipt-divider"></div>
      <div style="text-align:center; font-size:11px;">¡Gracias por elegir Whip Store!<br>Santa Rosa, La Pampa</div>
    `;

    const waText = encodeURIComponent(
      `🏍️ *Whip Store — Comprobante #${order.order_number}*\n` +
        order.items.map((i) => `• ${i.quantity}x ${i.product_name} (${i.variant_label}) - ${fmt(i.unit_price * i.quantity)}`).join("\n") +
        `\n\n*Total:* ${fmt(order.total)} (${order.payment_method})\n¡Gracias por tu compra!`
    );
    const cleanPhone = (order.customer_phone || "").replace(/\D/g, "");
    waBtn.href = cleanPhone.length >= 8 ? `https://wa.me/549${cleanPhone}?text=${waText}` : `https://wa.me/?text=${waText}`;

    document.getElementById("receiptModal").classList.add("open");
  }

  function renderReceiptToBlob(order) {
    return new Promise((resolve) => {
      const items = order.items || [];
      const W = 440;
      const lineH = 22;
      const H = 310 + items.length * 46 + (order.discount_amount > 0 ? 24 : 0);

      const canvas = document.createElement("canvas");
      canvas.width = W * 2;
      canvas.height = H * 2;
      const ctx = canvas.getContext("2d");
      ctx.scale(2, 2);

      // Fondo blanco
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, W - 1, H - 1);

      let y = 34;
      const pad = 24;

      const drawDash = () => {
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "#9ca3af";
        ctx.beginPath();
        ctx.moveTo(pad, y);
        ctx.lineTo(W - pad, y);
        ctx.stroke();
        ctx.restore();
        y += 18;
      };

      ctx.fillStyle = "#111111";
      ctx.font = "bold 18px 'Courier New', monospace";
      ctx.textAlign = "center";
      ctx.fillText("WHIP HELMETS ARGENTINA", W / 2, y);
      y += 18;
      ctx.fillStyle = "#6b7280";
      ctx.font = "12px 'Courier New', monospace";
      ctx.fillText("Comprobante interno de venta", W / 2, y);
      y += 14;
      drawDash();

      ctx.textAlign = "left";
      ctx.fillStyle = "#111111";
      ctx.font = "13px 'Courier New', monospace";
      ctx.fillText(`Ticket:  #${order.order_number}`, pad, y); y += lineH;
      ctx.fillText(`Fecha:   ${order.created_at}`, pad, y); y += lineH;
      ctx.fillText(`Canal:   ${order.channel}  |  Pago: ${order.payment_method}`, pad, y); y += lineH;
      ctx.fillText(`Cliente: ${order.customer_name}`, pad, y); y += 16;
      drawDash();

      for (const i of items) {
        const title = `${i.quantity}x ${i.product_name}`.slice(0, 32);
        ctx.fillStyle = "#111111";
        ctx.font = "bold 13px 'Courier New', monospace";
        ctx.textAlign = "left";
        ctx.fillText(title, pad, y);
        ctx.textAlign = "right";
        ctx.fillText(fmt(i.unit_price * i.quantity), W - pad, y);
        y += 17;
        ctx.fillStyle = "#6b7280";
        ctx.font = "11.5px 'Courier New', monospace";
        ctx.textAlign = "left";
        ctx.fillText(String(i.variant_label || "").slice(0, 40), pad, y);
        y += 24;
      }

      drawDash();
      ctx.fillStyle = "#4b5563";
      ctx.font = "13px 'Courier New', monospace";
      ctx.textAlign = "left";
      ctx.fillText("Subtotal:", pad, y);
      ctx.textAlign = "right";
      ctx.fillText(fmt(order.subtotal), W - pad, y);
      y += lineH;

      if (order.discount_amount > 0) {
        ctx.fillStyle = "#00a650";
        ctx.textAlign = "left";
        ctx.fillText("Descuento:", pad, y);
        ctx.textAlign = "right";
        ctx.fillText("-" + fmt(order.discount_amount), W - pad, y);
        y += lineH;
      }

      ctx.fillStyle = "#111111";
      ctx.font = "bold 18px 'Courier New', monospace";
      ctx.textAlign = "left";
      ctx.fillText("TOTAL:", pad, y + 4);
      ctx.textAlign = "right";
      ctx.fillText(fmt(order.total), W - pad, y + 4);
      y += 22;
      drawDash();

      ctx.fillStyle = "#4b5563";
      ctx.font = "12px 'Courier New', monospace";
      ctx.textAlign = "center";
      ctx.fillText("¡Gracias por elegir Whip Store!", W / 2, y);
      y += 17;
      ctx.fillText("Santa Rosa, La Pampa", W / 2, y);

      canvas.toBlob((blob) => resolve(blob), "image/png");
    });
  }

  async function shareReceiptImage() {
    if (!currentReceiptOrder) return;
    const blob = await renderReceiptToBlob(currentReceiptOrder);
    if (!blob) return;

    const filename = `ticket-whip-${currentReceiptOrder.order_number}.png`;
    const file = new File([blob], filename, { type: "image/png" });

    // 1. En celular: compartir directo a WhatsApp como imagen
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: `Ticket #${currentReceiptOrder.order_number}` });
        return;
      } catch {
        // si el usuario cancela, seguimos al fallback
      }
    }

    // 2. En PC: copiar imagen al portapapeles (listo para Ctrl+V en WhatsApp Web)
    if (navigator.clipboard && window.ClipboardItem) {
      try {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        toast("📋 Ticket copiado como imagen — pegalo con Ctrl+V en WhatsApp");
        return;
      } catch {
        // fallback a descarga
      }
    }

    // 3. Fallback universal: descargar PNG
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast("📥 Ticket descargado como imagen PNG");
  }

  // ---------------- CAJA DIARIA ----------------
  function renderCashTab() {
    const openGate = document.getElementById("cashOpenGate");
    const activeWrap = document.getElementById("cashActiveWrap");
    if (!openGate || !activeWrap) return;

    if (!state.activeSession) {
      openGate.style.display = "block";
      activeWrap.style.display = "none";
    } else {
      openGate.style.display = "none";
      activeWrap.style.display = "block";

      const s = state.activeSession;
      const sum = s.summary;
      const digitalTotal =
        (sum.by_method.TRANSFERENCIA || 0) +
        (sum.by_method.DEBITO || 0) +
        (sum.by_method.CREDITO || 0) +
        (sum.by_method.MERCADOPAGO || 0);

      document.getElementById("cashOpenedAt").textContent = `· Desde ${s.opened_at}`;
      document.getElementById("kpiCashExpected").textContent = fmt(s.expected_cash);
      document.getElementById("kpiCashOpeningSub").textContent = `Apertura: ${fmt(s.opening_amount)} + Efectivo: ${fmt(sum.by_method.EFECTIVO || 0)}`;
      document.getElementById("kpiCashSales").textContent = fmt(sum.sales_total);
      document.getElementById("kpiCashSalesCount").textContent = `${sum.sales_count} ventas registradas`;
      document.getElementById("kpiCashDigital").textContent = fmt(digitalTotal);
      document.getElementById("kpiCashDigitalSub").textContent = `Transf: ${fmt(sum.by_method.TRANSFERENCIA || 0)} · Tarj/MP: ${fmt((sum.by_method.DEBITO || 0) + (sum.by_method.CREDITO || 0) + (sum.by_method.MERCADOPAGO || 0))}`;
      document.getElementById("kpiCashOut").textContent = fmt(sum.cash_out);

      const movBody = document.getElementById("cashMovementsBody");
      const movs = s.movements || [];
      movBody.innerHTML = movs.length
        ? movs
            .map((m) => {
              const isOut = m.movement_type === "EGRESO";
              return `<tr>
                <td>${m.created_at}</td>
                <td><span class="ch-badge ${isOut ? "" : "ch-WHATSAPP"}" style="${isOut ? "background:rgba(239,68,68,0.18);color:#fca5a5;" : ""}">${m.movement_type}</span></td>
                <td>${m.payment_method}</td>
                <td>${m.description}</td>
                <td style="text-align:right;" class="${isOut ? "mov-neg" : "mov-pos"}">${isOut ? "-" : "+"}${fmt(m.amount)}</td>
              </tr>`;
            })
            .join("")
        : `<tr><td colspan="5" style="text-align:center; color:var(--muted); padding:20px;">Sin movimientos aún en este turno.</td></tr>`;
    }

    const closedBody = document.getElementById("closedSessionsBody");
    closedBody.innerHTML = state.closedSessions.length
      ? state.closedSessions
          .map((c) => {
            const diff = c.difference || 0;
            const diffCls = diff === 0 ? "" : diff > 0 ? "mov-pos" : "mov-neg";
            return `<tr>
              <td>${c.opened_at}</td>
              <td>${c.closed_at || "-"}</td>
              <td>${fmt(c.summary.sales_total)} (${c.summary.sales_count})</td>
              <td>${fmt(c.expected_cash)}</td>
              <td>${fmt(c.closing_amount)}</td>
              <td class="${diffCls}">${diff > 0 ? "+" : ""}${fmt(diff)}</td>
            </tr>`;
          })
          .join("")
      : `<tr><td colspan="6" style="text-align:center; color:var(--muted); padding:20px;">Todavía no hay cierres de caja registrados.</td></tr>`;
  }

  document.getElementById("openCashForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const opening_amount = parseInt(document.getElementById("cashOpeningAmount").value || "0", 10) || 0;
    const notes = document.getElementById("cashOpeningNotes").value.trim();
    const res = await fetch("/api/pos/cash/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ opening_amount, notes }),
    });
    const data = await res.json();
    if (data.ok) {
      toast("🟢 Caja abierta correctamente");
      await loadState();
    } else {
      toast(data.error || "Error al abrir caja", true);
    }
  });

  document.getElementById("cashMovementForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const movement_type = document.getElementById("cmType").value;
    const amount = parseInt(document.getElementById("cmAmount").value || "0", 10) || 0;
    const description = document.getElementById("cmDesc").value.trim();
    const res = await fetch("/api/pos/cash/movement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movement_type, amount, description, payment_method: "EFECTIVO" }),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById("cmAmount").value = "";
      document.getElementById("cmDesc").value = "";
      toast("Movimiento registrado en caja");
      await loadState();
    } else {
      toast(data.error || "Error al registrar movimiento", true);
    }
  });

  function openCloseCashModal() {
    if (!state.activeSession) return;
    document.getElementById("closeExpectedLabel").textContent = fmt(state.activeSession.expected_cash);
    document.getElementById("closeCountedAmount").value = state.activeSession.expected_cash;
    document.getElementById("closeNotes").value = "";
    updateCloseDiff();
    document.getElementById("closeCashModal").classList.add("open");
  }

  function updateCloseDiff() {
    if (!state.activeSession) return;
    const counted = parseInt(document.getElementById("closeCountedAmount").value || "0", 10) || 0;
    const diff = counted - state.activeSession.expected_cash;
    const lbl = document.getElementById("closeDiffLabel");
    if (diff === 0) {
      lbl.style.color = "#00a650";
      lbl.textContent = "✅ Caja cuadrada ($ 0 diferencia)";
    } else if (diff > 0) {
      lbl.style.color = "#d97706";
      lbl.textContent = `⚠️ Sobrante de ${fmt(diff)}`;
    } else {
      lbl.style.color = "#e63946";
      lbl.textContent = `❌ Faltante de ${fmt(Math.abs(diff))}`;
    }
  }

  document.getElementById("closeCashForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const closing_amount = parseInt(document.getElementById("closeCountedAmount").value || "0", 10) || 0;
    const notes = document.getElementById("closeNotes").value.trim();
    const res = await fetch("/api/pos/cash/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ closing_amount, notes }),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById("closeCashModal").classList.remove("open");
      toast("🔒 Caja cerrada y arqueo guardado");
      await loadState();
    } else {
      toast(data.error || "Error al cerrar caja", true);
    }
  });

  // ---------------- STOCK MOVEMENTS (KARDEX) ----------------
  function renderStockMovementsTab() {
    const sel = document.getElementById("smVariantSelect");
    if (sel) {
      const prev = sel.value;
      const opts = [];
      for (const p of state.products) {
        for (const v of p.variants) {
          opts.push(`<option value="${v.id}">${p.brand} ${p.name} — Talle ${v.size} [${v.sku}] (Stock: ${v.stock})</option>`);
        }
      }
      sel.innerHTML = opts.join("");
      if (prev) sel.value = prev;
    }

    const wrap = document.getElementById("stockMovementsGrouped");
    if (!wrap) return;
    if (!state.recentMovements.length) {
      wrap.innerHTML = `<div class="card-panel" style="padding:24px; text-align:center; color:#6b7280;">Aún no hay movimientos de stock registrados.</div>`;
      return;
    }

    const groups = new Map();
    for (const m of state.recentMovements) {
      const dateKey = (m.created_at || "Sin fecha").split(" ")[0];
      if (!groups.has(dateKey)) groups.set(dateKey, []);
      groups.get(dateKey).push(m);
    }

    let gIdx = 0;
    const htmlParts = [];
    for (const [dateKey, list] of groups.entries()) {
      const openAttr = gIdx === 0 ? "open" : "";
      gIdx++;
      const rowsHtml = list
        .map((m) => {
          const pos = m.quantity_delta > 0;
          const timePart = (m.created_at || "").split(" ")[1] || "";
          return `<tr>
            <td style="white-space:nowrap;">${timePart || m.created_at}</td>
            <td><span class="ch-badge ${m.movement_type === "VENTA_WEB" ? "ch-WEB" : m.movement_type === "VENTA_LOCAL" ? "ch-LOCAL" : "ch-WHATSAPP"}">${m.movement_type}</span></td>
            <td><strong>${m.product_name}</strong><div style="font-size:11.5px; color:#6b7280;">${m.variant_label}</div></td>
            <td style="font-family:monospace; font-size:12px;">${m.sku}</td>
            <td class="${pos ? "mov-pos" : "mov-neg"}">${pos ? "+" : ""}${m.quantity_delta}</td>
            <td><strong>${m.stock_after}</strong></td>
            <td style="color:#6b7280; font-size:12.5px;">${m.reason}</td>
          </tr>`;
        })
        .join("");

      htmlParts.push(`
        <details class="card-panel" style="padding:0; overflow:hidden; margin-bottom:0;" ${openAttr}>
          <summary style="padding:13px 18px; background:#f8f9fa; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; cursor:pointer; list-style:none;">
            <div style="display:flex; align-items:center; gap:10px;">
              <strong style="font-size:14px; color:#111;">📅 ${dateKey}</strong>
              <span style="font-size:12px; font-weight:700; color:#6b7280;">${list.length} movimiento(s)</span>
            </div>
            <span style="font-size:12px; color:#4b5563; font-weight:700;">Desplegar ▾</span>
          </summary>
          <div style="overflow-x:auto; border-top:1px solid #e5e7eb;">
            <table class="data-table">
              <thead><tr><th>Hora</th><th>Tipo</th><th>Producto / Talle</th><th>SKU</th><th>Cambio</th><th>Stock Final</th><th>Motivo</th></tr></thead>
              <tbody>${rowsHtml}</tbody>
            </table>
          </div>
        </details>
      `);
    }
    wrap.innerHTML = htmlParts.join("");
  }

  document.getElementById("stockMovementForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const variant_id = parseInt(document.getElementById("smVariantSelect").value || "0", 10);
    const movement_type = document.getElementById("smType").value;
    let quantity_delta = parseInt(document.getElementById("smQty").value || "0", 10);
    const reason = document.getElementById("smReason").value.trim();

    if ((movement_type === "INGRESO" || movement_type === "DEVOLUCION") && quantity_delta < 0) {
      quantity_delta = Math.abs(quantity_delta);
    }

    const res = await fetch("/api/pos/stock-movement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant_id, movement_type, quantity_delta, reason }),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById("smReason").value = "";
      toast("✅ Stock actualizado y registrado en historial");
      await loadState();
    } else {
      toast(data.error || "Error actualizando stock", true);
    }
  });

  // ---------------- STOCK & PRODUCTS (UNIFICADO) ----------------
  function renderStockTab() {
    const badgeLow = document.getElementById("posBadgeLowStock");
    if (badgeLow) badgeLow.textContent = state.lowStock.length ? `(${state.lowStock.length})` : "";

    const lowCard = document.getElementById("posLowStockCard");
    const lowBody = document.getElementById("posLowStockBody");
    const lowCount = document.getElementById("posLowStockCount");
    if (lowCard && lowBody) {
      if (!state.lowStock.length) {
        lowCard.style.display = "none";
      } else {
        lowCard.style.display = "block";
        lowCount.textContent = `${state.lowStock.length} variantes con bajo stock`;
        lowBody.innerHTML = state.lowStock
          .slice(0, 12)
          .map(
            (x) => `<tr>
              <td><strong>${x.product_name}</strong> <span style="font-size:11.5px; color:var(--muted);">(${x.brand})</span></td>
              <td><strong>${x.size}</strong></td>
              <td style="font-family:monospace; font-size:12px;">${x.sku}</td>
              <td><span class="${x.stock === 0 ? "mov-neg" : ""}" style="${x.stock > 0 ? "color:#d97706;font-weight:800;" : ""}">${x.stock} u.</span></td>
              <td style="text-align:right;">
                <button type="button" class="btn btn-cta" style="height:28px; padding:0 10px; font-size:11.5px;" onclick="window.WhipPOS.quickRestock(${x.variant_id}, ${x.stock + 3})">+3 u.</button>
              </td>
            </tr>`
          )
          .join("");
      }
    }

    const tbody = document.getElementById("posStockProductsBody");
    const pagWrap = document.getElementById("posStockPagination");
    if (!tbody) return;
    const q = (document.getElementById("posStockSearch")?.value || "").trim().toLowerCase();
    const list = state.products.filter((p) => {
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.variants.some((v) => v.sku.toLowerCase().includes(q))
      );
    });

    const totalPages = Math.max(1, Math.ceil(list.length / state.stockPageSize));
    if (state.stockPage > totalPages) state.stockPage = totalPages;
    if (state.stockPage < 1) state.stockPage = 1;

    const startIdx = (state.stockPage - 1) * state.stockPageSize;
    const pageItems = list.slice(startIdx, startIdx + state.stockPageSize);

    tbody.innerHTML = pageItems.length
      ? pageItems
          .map((p) => {
            const img = (p.images && p.images[0]) || "/static/images/cat-cascos.jpg";
            const variantsHtml = p.variants
              .map(
                (v) => `<div style="display:inline-flex; align-items:center; gap:4px; margin:2px 4px 2px 0; padding:3px 6px; border-radius:7px; background:#f8f9fa; border:1px solid #e5e7eb; font-size:12px;">
                  <strong style="min-width:20px; color:#111;">${v.size}</strong>
                  <button type="button" onclick="window.WhipPOS.setVariantStock(${v.id}, ${Math.max(0, v.stock - 1)})" style="width:22px;height:22px;border-radius:5px;border:1px solid #d1d5db;background:#fff;color:#111;cursor:pointer;font-weight:800;">-</button>
                  <span style="min-width:18px;text-align:center;font-weight:800;color:${v.stock === 0 ? "#e63946" : v.stock <= 2 ? "#d97706" : "#00a650"};">${v.stock}</span>
                  <button type="button" onclick="window.WhipPOS.setVariantStock(${v.id}, ${v.stock + 1})" style="width:22px;height:22px;border-radius:5px;border:1px solid #d1d5db;background:#fff;color:#111;cursor:pointer;font-weight:800;">+</button>
                </div>`
              )
              .join("");

            return `<tr>
              <td>
                <div style="display:flex; align-items:center; gap:10px;">
                  <img src="${img}" alt="" style="width:40px;height:40px;border-radius:7px;object-fit:contain;background:#f8f9fa;border:1px solid #e5e7eb;padding:2px;">
                  <div>
                    <div style="font-weight:700; font-size:13px; color:#111;">${p.name}</div>
                    <div style="font-size:11.5px; color:#6b7280;">${p.brand} · Total: ${p.total_stock} u.</div>
                  </div>
                </div>
              </td>
              <td>
                <div style="display:flex; flex-direction:column; gap:5px;">
                  <div style="display:flex; align-items:center; gap:5px;">
                    <span style="font-size:10.5px; color:#6b7280; min-width:38px;">Lista:</span>
                    <input type="number" id="price-in-${p.id}" value="${p.price}" style="width:98px; height:28px; padding:0 7px; border-radius:6px; border:1px solid #d1d5db; background:#fff; color:#111; font-weight:700; font-size:12px;">
                  </div>
                  <div style="display:flex; align-items:center; gap:5px;">
                    <span style="font-size:10.5px; color:#00a650; min-width:38px; font-weight:700;">Ef/Tr:</span>
                    <input type="number" id="cash-in-${p.id}" value="${p.cash_price || p.transfer_price}" style="width:98px; height:28px; padding:0 7px; border-radius:6px; border:1px solid #86efac; background:#f0fdf4; color:#065f46; font-weight:700; font-size:12px;">
                    <button type="button" class="btn btn-outline" style="height:28px; padding:0 8px; font-size:11px;" onclick="window.WhipPOS.savePrice(${p.id})">Guardar</button>
                  </div>
                </div>
              </td>
              <td>${variantsHtml}</td>
              <td>
                <div style="display:flex; flex-direction:column; gap:5px; align-items:flex-start;">
                  <button type="button" class="ch-badge ${p.is_active ? "ch-WHATSAPP" : ""}" style="border:none; cursor:pointer; ${p.is_active ? "" : "background:#fee2e2;color:#b91c1c;"}" onclick="window.WhipPOS.toggleActive(${p.id}, ${!p.is_active})">
                    ${p.is_active ? "● Activo" : "○ Pausado"}
                  </button>
                  <button type="button" class="ch-badge" style="border:1px solid ${p.is_outlet ? "#111" : "#d1d5db"}; cursor:pointer; background:${p.is_outlet ? "#111" : "#f8f9fa"}; color:${p.is_outlet ? "#fff" : "#6b7280"};" onclick="window.WhipPOS.toggleOutlet(${p.id}, ${!p.is_outlet})" title="Clic para marcar o quitar de Outlet">
                    ${p.is_outlet ? "🏷️ Outlet" : "Nuevo"}
                  </button>
                </div>
              </td>
              <td style="text-align:right; white-space:nowrap;">
                <button type="button" class="btn btn-outline" style="height:30px; padding:0 9px; font-size:11.5px; margin-right:4px;" title="Generar e imprimir códigos de barras" onclick="window.WhipPOS.openBarcodeModal(${p.id})">🏷️ Códigos</button>
                <button type="button" class="btn btn-outline" style="height:30px; padding:0 9px; font-size:11.5px; margin-right:4px;" onclick="window.WhipPOS.openEditProduct(${p.id})">✏️ Editar</button>
                <button type="button" class="btn btn-outline" style="height:30px; padding:0 9px; font-size:11px; border-color:#e63946; color:#e63946;" onclick="window.WhipPOS.deleteProduct(${p.id}, '${p.name.replace(/'/g, "\\'")}')">Eliminar</button>
              </td>
            </tr>`;
          })
          .join("")
      : `<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--muted);">No se encontraron productos.</td></tr>`;

    if (pagWrap) {
      if (!list.length) {
        pagWrap.innerHTML = "";
      } else {
        const from = startIdx + 1;
        const to = Math.min(startIdx + state.stockPageSize, list.length);
        let pageBtns = "";
        for (let i = 1; i <= totalPages; i++) {
          pageBtns += `<button type="button" class="pill-btn ${i === state.stockPage ? "active" : ""}" style="min-width:32px; height:30px; padding:0 10px; font-size:12px;" onclick="window.WhipPOS.setStockPage(${i})">${i}</button>`;
        }
        pagWrap.innerHTML = `
          <span>Mostrando <strong>${from}–${to}</strong> de <strong>${list.length}</strong> productos</span>
          <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
            <button type="button" class="btn btn-outline" style="height:30px; padding:0 10px; font-size:12px;" ${state.stockPage <= 1 ? "disabled" : ""} onclick="window.WhipPOS.setStockPage(${state.stockPage - 1})">← Anterior</button>
            ${pageBtns}
            <button type="button" class="btn btn-outline" style="height:30px; padding:0 10px; font-size:12px;" ${state.stockPage >= totalPages ? "disabled" : ""} onclick="window.WhipPOS.setStockPage(${state.stockPage + 1})">Siguiente →</button>
          </div>
        `;
      }
    }
  }

  async function setVariantStock(variantId, newStock) {
    const res = await fetch(`/api/admin/variant/${variantId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stock: newStock }),
    });
    const data = await res.json();
    if (data.ok) {
      toast(`Stock actualizado a ${data.variant.stock} u.`);
      await loadState();
    } else {
      toast(data.error || "Error actualizando stock", true);
    }
  }

  async function savePrice(productId) {
    const val = parseInt(document.getElementById(`price-in-${productId}`)?.value || "0", 10);
    const cashVal = parseInt(document.getElementById(`cash-in-${productId}`)?.value || "0", 10) || null;
    if (val <= 0) return toast("Precio lista inválido", true);
    const res = await fetch(`/api/admin/product/${productId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ price: val, cash_price: cashVal }),
    });
    const data = await res.json();
    if (data.ok) {
      toast("Precios actualizados en Local y Web");
      await loadState();
    } else {
      toast(data.error || "Error actualizando precios", true);
    }
  }

  async function toggleActive(productId, isActive) {
    const res = await fetch(`/api/admin/product/${productId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    });
    const data = await res.json();
    if (data.ok) {
      toast(isActive ? "Producto visible en la web" : "Producto pausado en la web");
      await loadState();
    }
  }

  async function toggleOutlet(productId, isOutlet) {
    const res = await fetch(`/api/admin/product/${productId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_outlet: isOutlet }),
    });
    const data = await res.json();
    if (data.ok) {
      toast(isOutlet ? "🏷️ Marcado como Outlet (Usado)" : "Quitado de Outlet (Nuevo)");
      await loadState();
    }
  }

  async function deleteProduct(productId, name) {
    if (!confirm(`¿Eliminar "${name}" de la base de datos?`)) return;
    const res = await fetch(`/api/admin/product/${productId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.ok) {
      toast("Producto eliminado");
      await loadState();
    }
  }

  // ---------------- EDITAR PRODUCTO COMPLETO ----------------
  let editImages = [];

  function renderImageListHtml(images, mode) {
    if (!images.length) {
      return `<div style="font-size:12px; color:#6b7280;">Sin fotos cargadas todavía. La primera que subas será la <strong>Portada</strong>.</div>`;
    }
    return images
      .map((url, idx) => {
        const isCover = idx === 0;
        return `<div style="position:relative; width:96px; border-radius:10px; background:#ffffff; padding:5px; border:${isCover ? "2px solid #111111" : "1px solid #d1d5db"}; display:flex; flex-direction:column; gap:4px; align-items:center;">
          <div style="width:84px; height:72px; border-radius:6px; background:#f8f9fa; padding:3px; display:flex; align-items:center; justify-content:center; overflow:hidden;">
            <img src="${url}" alt="" style="width:100%; height:100%; object-fit:contain;">
          </div>
          <button type="button" onclick="window.WhipPOS.removeImage('${mode}', ${idx})" title="Quitar foto" style="position:absolute; top:-7px; right:-7px; width:20px; height:20px; border-radius:50%; border:none; background:#e63946; color:#fff; font-size:11px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center;">✕</button>
          ${
            isCover
              ? `<span style="width:100%; text-align:center; font-size:10px; font-weight:800; background:#111111; color:#ffffff; padding:2px 4px; border-radius:5px;">★ PORTADA</span>`
              : `<button type="button" onclick="window.WhipPOS.setCoverImage('${mode}', ${idx})" title="Usar como foto principal" style="width:100%; font-size:10px; font-weight:700; background:#f3f4f6; color:#111; border:1px solid #d1d5db; padding:2px 4px; border-radius:5px; cursor:pointer;">★ Portada</button>`
          }
          <div style="display:flex; justify-content:space-between; align-items:center; width:100%; gap:3px;">
            <button type="button" ${idx === 0 ? "disabled" : ""} onclick="window.WhipPOS.moveImage('${mode}', ${idx}, -1)" title="Mover a la izquierda" style="flex:1; height:20px; font-size:11px; font-weight:800; border-radius:4px; border:1px solid #d1d5db; background:#fff; color:#111; cursor:pointer; opacity:${idx === 0 ? "0.35" : "1"};">‹</button>
            <span style="font-size:10px; color:#6b7280; font-weight:700;">#${idx + 1}</span>
            <button type="button" ${idx === images.length - 1 ? "disabled" : ""} onclick="window.WhipPOS.moveImage('${mode}', ${idx}, 1)" title="Mover a la derecha" style="flex:1; height:20px; font-size:11px; font-weight:800; border-radius:4px; border:1px solid #d1d5db; background:#fff; color:#111; cursor:pointer; opacity:${idx === images.length - 1 ? "0.35" : "1"};">›</button>
          </div>
        </div>`;
      })
      .join("");
  }

  function renderEditImages() {
    const wrap = document.getElementById("epImagesList");
    if (wrap) wrap.innerHTML = renderImageListHtml(editImages, "edit");
  }

  function setCoverImage(mode, idx) {
    const arr = mode === "new" ? newImages : editImages;
    if (idx <= 0 || idx >= arr.length) return;
    const [picked] = arr.splice(idx, 1);
    arr.unshift(picked);
    mode === "new" ? renderNewImages() : renderEditImages();
  }

  function moveImage(mode, idx, delta) {
    const arr = mode === "new" ? newImages : editImages;
    const target = idx + delta;
    if (target < 0 || target >= arr.length) return;
    const tmp = arr[idx];
    arr[idx] = arr[target];
    arr[target] = tmp;
    mode === "new" ? renderNewImages() : renderEditImages();
  }

  function removeImage(mode, idx) {
    const arr = mode === "new" ? newImages : editImages;
    arr.splice(idx, 1);
    mode === "new" ? renderNewImages() : renderEditImages();
  }

  function addEditVariantRow(v = { id: "", size: "", color: "Negro Mate", sku: "", stock: 0 }) {
    const wrap = document.getElementById("epVariantsList");
    if (!wrap) return;
    const row = document.createElement("div");
    row.className = "ep-variant-row";
    row.style.cssText = "display:grid; grid-template-columns:75px 1fr 1.1fr 75px 32px; gap:6px; align-items:center;";
    row.innerHTML = `
      <input type="hidden" class="ev-id" value="${v.id || ""}">
      <input type="text" class="ev-size" value="${(v.size || "").replace(/"/g, "&quot;")}" placeholder="M" required style="height:34px; padding:0 8px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-size:12.5px;">
      <input type="text" class="ev-color" value="${(v.color || "").replace(/"/g, "&quot;")}" placeholder="Negro" style="height:34px; padding:0 8px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-size:12.5px;">
      <input type="text" class="ev-sku" value="${(v.sku || "").replace(/"/g, "&quot;")}" placeholder="Auto SKU" style="height:34px; padding:0 8px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-size:12px; font-family:monospace;">
      <input type="number" class="ev-stock" value="${v.stock ?? 0}" min="0" style="height:34px; padding:0 8px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-weight:700; font-size:12.5px;">
      <button type="button" onclick="this.parentElement.remove()" title="Quitar talle" style="width:30px; height:34px; border-radius:7px; border:1px solid #fecaca; background:#fef2f2; color:#e63946; cursor:pointer; font-weight:800;">✕</button>
    `;
    wrap.appendChild(row);
  }

  function openEditProduct(productId) {
    const p = state.products.find((x) => x.id === productId);
    if (!p) return;

    document.getElementById("epId").value = p.id;
    document.getElementById("epName").value = p.name || "";
    document.getElementById("epBrand").value = p.brand || "";
    document.getElementById("epCategory").value = p.category_slug || "cascos";
    const epSubField = document.getElementById("epSubcatField");
    if (epSubField) epSubField.style.display = (p.category_slug === "indumentaria") ? "block" : "none";
    const epSubSel = document.getElementById("epSubcategory");
    if (epSubSel) epSubSel.value = p.subcategory || "competicion";
    document.getElementById("epPrice").value = p.price || 0;
    document.getElementById("epCashPrice").value = p.cash_price || p.transfer_price || "";
    document.getElementById("epComparePrice").value = p.compare_at_price || "";
    document.getElementById("epIsActive").checked = Boolean(p.is_active);
    document.getElementById("epIsFeatured").checked = Boolean(p.is_featured);
    document.getElementById("epIsOutlet").checked = Boolean(p.is_outlet);
    document.getElementById("epDescription").value = p.description || "";
    document.getElementById("epImageUrlInput").value = "";

    editImages = [...(p.images || [])];
    renderEditImages();

    const vWrap = document.getElementById("epVariantsList");
    vWrap.innerHTML = "";
    (p.variants || []).forEach((v) => addEditVariantRow(v));

    document.getElementById("posEditProductModal").classList.add("open");
  }

  async function uploadEditImage(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/admin/upload-image", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok && data.url) {
        editImages.push(data.url);
        renderEditImages();
        toast("📷 Foto subida correctamente");
      } else {
        toast(data.error || "Error subiendo imagen", true);
      }
    } catch {
      toast("Error de conexión al subir imagen", true);
    } finally {
      input.value = "";
    }
  }

  function addEditImageUrl() {
    const inp = document.getElementById("epImageUrlInput");
    const url = (inp?.value || "").trim();
    if (!url) return;
    editImages.push(url);
    inp.value = "";
    renderEditImages();
  }

  function removeEditImage(idx) {
    editImages.splice(idx, 1);
    renderEditImages();
  }

  document.getElementById("posEditProductForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = parseInt(document.getElementById("epId").value, 10);
    const btn = document.getElementById("epSaveBtn");
    btn.disabled = true;
    btn.textContent = "Guardando...";

    const variants = Array.from(document.querySelectorAll("#epVariantsList .ep-variant-row")).map((row) => ({
      id: row.querySelector(".ev-id").value || null,
      size: row.querySelector(".ev-size").value.trim(),
      color: row.querySelector(".ev-color").value.trim(),
      sku: row.querySelector(".ev-sku").value.trim(),
      stock: parseInt(row.querySelector(".ev-stock").value || "0", 10) || 0,
    }));

    const payload = {
      name: document.getElementById("epName").value.trim(),
      brand: document.getElementById("epBrand").value.trim(),
      category_slug: document.getElementById("epCategory").value,
      subcategory: document.getElementById("epCategory").value === "indumentaria" ? (document.getElementById("epSubcategory")?.value || "competicion") : "",
      price: parseInt(document.getElementById("epPrice").value || "0", 10) || 0,
      cash_price: parseInt(document.getElementById("epCashPrice").value || "0", 10) || null,
      compare_at_price: parseInt(document.getElementById("epComparePrice").value || "0", 10) || null,
      is_active: document.getElementById("epIsActive").checked,
      is_featured: document.getElementById("epIsFeatured").checked,
      is_outlet: document.getElementById("epIsOutlet").checked,
      description: document.getElementById("epDescription").value.trim(),
      images: editImages,
      variants,
    };

    try {
      const res = await fetch(`/api/admin/product/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        document.getElementById("posEditProductModal").classList.remove("open");
        toast("✅ Producto actualizado en Local y Web");
        await loadState();
      } else {
        toast(data.error || "Error al guardar cambios", true);
      }
    } catch {
      toast("Error de conexión al guardar.", true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Guardar Cambios";
    }
  });

  let newImages = [];

  function renderNewImages() {
    const wrap = document.getElementById("pnpImagesList");
    if (wrap) wrap.innerHTML = renderImageListHtml(newImages, "new");
  }

  async function uploadNewImage(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/admin/upload-image", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok && data.url) {
        newImages.push(data.url);
        renderNewImages();
        toast("📷 Foto subida correctamente");
      } else {
        toast(data.error || "Error subiendo imagen", true);
      }
    } catch {
      toast("Error de conexión al subir imagen", true);
    } finally {
      input.value = "";
    }
  }

  function addNewImageUrl() {
    const inp = document.getElementById("pnpImageUrlInput");
    const url = (inp?.value || "").trim();
    if (!url) return;
    newImages.push(url);
    inp.value = "";
    renderNewImages();
  }

  function removeNewImage(idx) {
    newImages.splice(idx, 1);
    renderNewImages();
  }

  async function importProductsFile(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    toast("⏳ Importando productos...");
    try {
      const res = await fetch("/api/admin/import-products", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        toast(data.error || "Error importando archivo", true);
        return;
      }
      let msg = `✅ ${data.created} producto(s) y ${data.variants} variante(s) importados.`;
      if (data.errors && data.errors.length) {
        msg += ` (${data.errors.length} fila(s) omitidas)`;
        alert(msg + "\n\nObservaciones:\n" + data.errors.join("\n"));
      } else {
        toast(msg);
      }
      await loadState();
    } catch {
      toast("Error de conexión al importar.", true);
    } finally {
      input.value = "";
    }
  }

  document.getElementById("posNewProductForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("pnpName").value.trim(),
      brand: document.getElementById("pnpBrand").value.trim(),
      category_slug: document.getElementById("pnpCategory").value,
      subcategory: document.getElementById("pnpCategory").value === "indumentaria" ? (document.getElementById("pnpSubcategory")?.value || "competicion") : "",
      price: parseInt(document.getElementById("pnpPrice").value || "0", 10),
      cash_price: parseInt(document.getElementById("pnpCashPrice").value || "0", 10) || null,
      compare_at_price: parseInt(document.getElementById("pnpComparePrice").value || "0", 10) || null,
      color: document.getElementById("pnpColor").value.trim(),
      description: document.getElementById("pnpDescription").value.trim(),
      images: newImages,
      is_outlet: Boolean(document.getElementById("pnpIsOutlet")?.checked),
      stock_s: parseInt(document.getElementById("pnpStockS").value || "0", 10),
      stock_m: parseInt(document.getElementById("pnpStockM").value || "0", 10),
      stock_l: parseInt(document.getElementById("pnpStockL").value || "0", 10),
      stock_xl: parseInt(document.getElementById("pnpStockXL").value || "0", 10),
    };
    const res = await fetch("/api/admin/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById("posNewProductModal").classList.remove("open");
      document.getElementById("pnpName").value = "";
      document.getElementById("pnpComparePrice").value = "";
      document.getElementById("pnpCashPrice").value = "";
      document.getElementById("pnpDescription").value = "";
      document.getElementById("pnpImageUrlInput").value = "";
      newImages = [];
      renderNewImages();
      toast("✅ Producto creado y publicado en la tienda");
      await loadState();
    } else {
      toast(data.error || "Error creando producto", true);
    }
  });

  // ---------------- CÓDIGOS DE BARRAS (CODE 128) ----------------
  let barcodeProduct = null;

  function openBarcodeModal(productId) {
    const p = state.products.find((x) => x.id === productId);
    if (!p) return;
    barcodeProduct = p;

    document.getElementById("barcodeProductTitle").textContent = `${p.brand} — ${p.name}`;
    const qtyWrap = document.getElementById("barcodeQtyControls");
    qtyWrap.innerHTML = (p.variants || [])
      .map(
        (v) => `<div style="display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border-radius:8px; background:#fff; border:1px solid #d1d5db; font-size:12px;">
          <strong style="color:#111;">Talle ${v.size}</strong>
          <span style="font-family:monospace; color:#6b7280; font-size:11px;">${v.sku}</span>
          <input type="number" class="bc-qty-input" data-variant-id="${v.id}" value="${v.stock > 0 ? v.stock : 1}" min="0" max="50" oninput="window.WhipPOS.renderBarcodePreview()" style="width:52px; height:28px; padding:0 6px; border-radius:6px; border:1px solid #d1d5db; background:#f8f9fa; color:#111; font-weight:700; text-align:center;">
        </div>`
      )
      .join("");

    renderBarcodePreview();
    document.getElementById("barcodeModal").classList.add("open");
  }

  function renderBarcodePreview() {
    const area = document.getElementById("barcodePrintArea");
    if (!area || !barcodeProduct) return;

    const showList = Boolean(document.getElementById("bcShowListPrice")?.checked);
    const showCash = Boolean(document.getElementById("bcShowCashPrice")?.checked);
    const inputs = Array.from(document.querySelectorAll("#barcodeQtyControls .bc-qty-input"));

    area.innerHTML = "";
    let totalLabels = 0;

    for (const inp of inputs) {
      const vid = parseInt(inp.dataset.variantId, 10);
      const qty = Math.min(50, Math.max(0, parseInt(inp.value || "0", 10) || 0));
      const v = (barcodeProduct.variants || []).find((x) => x.id === vid);
      if (!v || qty <= 0) continue;

      for (let i = 0; i < qty; i++) {
        totalLabels++;
        const card = document.createElement("div");
        card.className = "barcode-label";
        const svgId = `bc-svg-${vid}-${i}`;
        const priceParts = [];
        if (showList) priceParts.push(`<span>Lista: ${fmt(barcodeProduct.price)}</span>`);
        if (showCash) priceParts.push(`<span>Ef/Tr: ${fmt(barcodeProduct.transfer_price)}</span>`);

        card.innerHTML = `
          <div class="barcode-label-brand">WHIP STORE · ${barcodeProduct.brand}</div>
          <div class="barcode-label-name">${barcodeProduct.name}</div>
          <div class="barcode-label-meta">Talle ${v.size} · ${v.color}</div>
          <svg id="${svgId}"></svg>
          ${priceParts.length ? `<div class="barcode-label-prices">${priceParts.join("")}</div>` : ""}
        `;
        area.appendChild(card);

        if (window.JsBarcode) {
          try {
            window.JsBarcode(`#${svgId}`, v.sku, {
              format: "CODE128",
              width: 1.5,
              height: 40,
              displayValue: true,
              fontSize: 11,
              margin: 4,
              background: "#ffffff",
              lineColor: "#000000",
            });
          } catch {
            // fallback si el SKU tuviera caracteres no válidos
          }
        }
      }
    }

    if (totalLabels === 0) {
      area.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:20px; color:var(--muted); font-size:13px;">Elegí al menos 1 etiqueta para previsualizar.</div>`;
    }
  }

  function printBarcodes() {
    document.body.classList.add("printing-barcodes");
    window.print();
    setTimeout(() => document.body.classList.remove("printing-barcodes"), 400);
  }

  // ---------------- RECENT SALES & WEB ORDERS ----------------
  function renderRecentSalesTab() {
    const wrap = document.getElementById("recentSalesGrouped");
    if (!wrap) return;

    const pendingCount = state.recentSales.filter(
      (o) => o.payment_status === "PENDING" || (o.payment_status === "PAID" && o.shipping_status !== "DELIVERED" && o.shipping_status !== "SHIPPED")
    ).length;
    const badgePending = document.getElementById("posBadgePending");
    if (badgePending) badgePending.textContent = pendingCount ? `(${pendingCount})` : "";

    const filtered = state.recentSales.filter((o) => {
      const ch = o.channel || "WEB";
      if (state.salesFilter === "LOCAL") return ch !== "WEB";
      if (state.salesFilter === "WEB") return ch === "WEB";
      if (state.salesFilter === "PENDING") return o.payment_status === "PENDING";
      if (state.salesFilter === "TO_SHIP") return o.payment_status === "PAID" && o.shipping_status !== "DELIVERED" && o.shipping_status !== "SHIPPED";
      return true;
    });

    if (!filtered.length) {
      wrap.innerHTML = `<div class="card-panel" style="padding:24px; text-align:center; color:#6b7280;">No hay ventas/pedidos para este filtro.</div>`;
      return;
    }

    const groups = new Map();
    for (const o of filtered) {
      const dateKey = (o.created_at || "Sin fecha").split(" ")[0];
      if (!groups.has(dateKey)) groups.set(dateKey, []);
      groups.get(dateKey).push(o);
    }

    let gIdx = 0;
    const htmlParts = [];
    for (const [dateKey, list] of groups.entries()) {
      const openAttr = gIdx === 0 ? "open" : "";
      gIdx++;
      const dayPaidTotal = list.filter((o) => o.payment_status === "PAID").reduce((s, o) => s + (o.total || 0), 0);

      const rowsHtml = list
        .map((o) => {
          const ch = o.channel || "WEB";
          const timePart = (o.created_at || "").split(" ")[1] || "";
          const itemsSummary = (o.items || []).map((i) => `${i.quantity}x ${i.product_name} (${i.variant_label})`).join(" · ");
          return `<tr>
            <td><strong>#${o.order_number}</strong></td>
            <td>
              <span class="ch-badge ch-${ch}">${ch}</span>
              <div style="font-size:11px; color:#6b7280; margin-top:3px;">${timePart || o.created_at}</div>
            </td>
            <td>
              <strong>${o.customer_name}</strong>
              <div style="font-size:11.5px; color:#6b7280; max-width:260px;">${itemsSummary}</div>
            </td>
            <td>
              <strong>${fmt(o.total)}</strong>
              <div style="font-size:11px; color:#6b7280;">${o.payment_method}</div>
              ${o.notes ? `<div style="font-size:10.5px; color:#111; font-family:monospace;">${o.notes}</div>` : ""}
            </td>
            <td>
              <select onchange="window.WhipPOS.updateOrderField(${o.id}, 'payment_status', this.value)" style="height:30px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-size:12px; padding:0 6px;">
                <option value="PENDING" ${o.payment_status === "PENDING" ? "selected" : ""}>Pendiente</option>
                <option value="PAID" ${o.payment_status === "PAID" ? "selected" : ""}>Pagado</option>
                <option value="CANCELLED" ${o.payment_status === "CANCELLED" ? "selected" : ""}>Cancelado</option>
              </select>
            </td>
            <td>
              <div style="display:flex; flex-direction:column; gap:4px;">
                <select onchange="window.WhipPOS.updateOrderField(${o.id}, 'shipping_status', this.value)" style="height:28px; border-radius:7px; border:1px solid #d1d5db; background:#fff; color:#111; font-size:11.5px; padding:0 6px;">
                  <option value="UNFULFILLED" ${o.shipping_status === "UNFULFILLED" ? "selected" : ""}>Sin preparar</option>
                  <option value="PREPARING" ${o.shipping_status === "PREPARING" ? "selected" : ""}>Preparando</option>
                  <option value="SHIPPED" ${o.shipping_status === "SHIPPED" ? "selected" : ""}>Enviado</option>
                  <option value="DELIVERED" ${o.shipping_status === "DELIVERED" ? "selected" : ""}>Entregado</option>
                </select>
                ${ch === "WEB" ? `<div style="display:flex; gap:4px;">
                  <input type="text" id="trk-${o.id}" value="${o.tracking_code || ""}" placeholder="Tracking..." style="width:110px; height:26px; font-size:11px; padding:0 6px; border-radius:6px; border:1px solid #d1d5db; background:#fff; color:#111;">
                  <button type="button" class="btn btn-outline" style="height:26px; padding:0 6px; font-size:10.5px;" onclick="window.WhipPOS.saveTracking(${o.id})">OK</button>
                </div>` : ""}
              </div>
            </td>
            <td style="text-align:right; white-space:nowrap;">
              <button type="button" class="btn btn-outline" style="height:30px; padding:0 10px; font-size:11.5px;" onclick="window.WhipPOS.reprintOrder(${o.id})">🧾 Ticket</button>
              ${o.payment_status !== "CANCELLED" ? `<button type="button" class="btn btn-outline" style="height:30px; padding:0 10px; font-size:11.5px; border-color:#e63946; color:#e63946;" onclick="window.WhipPOS.cancelOrder(${o.id})">Anular</button>` : `<span style="font-size:11.5px; font-weight:700; color:#e63946; margin-left:6px;">Anulado</span>`}
            </td>
          </tr>`;
        })
        .join("");

      htmlParts.push(`
        <details class="card-panel" style="padding:0; overflow:hidden; margin-bottom:0;" ${openAttr}>
          <summary style="padding:13px 18px; background:#f8f9fa; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; cursor:pointer; list-style:none;">
            <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
              <strong style="font-size:14px; color:#111;">📅 ${dateKey}</strong>
              <span style="font-size:12px; font-weight:700; color:#6b7280;">${list.length} pedido(s)</span>
              <span style="font-size:12.5px; font-weight:800; color:#00a650;">Pagado: ${fmt(dayPaidTotal)}</span>
            </div>
            <span style="font-size:12px; color:#4b5563; font-weight:700;">Desplegar ▾</span>
          </summary>
          <div style="overflow-x:auto; border-top:1px solid #e5e7eb;">
            <table class="data-table">
              <thead><tr><th>Pedido</th><th>Canal / Hora</th><th>Cliente y Productos</th><th>Total / Pago</th><th>Estado Pago</th><th>Envío / Tracking</th><th style="text-align:right;">Acciones</th></tr></thead>
              <tbody>${rowsHtml}</tbody>
            </table>
          </div>
        </details>
      `);
    }
    wrap.innerHTML = htmlParts.join("");
  }

  async function updateOrderField(orderId, field, value) {
    const res = await fetch(`/api/admin/order/${orderId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
    const data = await res.json();
    if (data.ok) {
      toast("Pedido actualizado");
      await loadState();
    }
  }

  async function saveTracking(orderId) {
    const val = document.getElementById(`trk-${orderId}`)?.value.trim() || "";
    await updateOrderField(orderId, "tracking_code", val);
  }

  async function cancelOrder(orderId) {
    if (!confirm("¿Anular esta venta y devolver las unidades al stock?")) return;
    const res = await fetch(`/api/admin/order/${orderId}/restore-stock`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      toast("Venta anulada y stock reintegrado");
      await loadState();
    } else {
      toast(data.error || "Error al anular", true);
    }
  }

  // ---------------- PUBLIC API ----------------
  window.WhipPOS = {
    switchTab(name) {
      document.querySelectorAll(".pos-tab-panel").forEach((el) => (el.style.display = "none"));
      document.querySelectorAll(".admin-tab").forEach((el) => el.classList.toggle("active", el.dataset.tab === name));
      const target = document.getElementById("pos-tab-" + name);
      if (target) target.style.display = "block";
      if (name === "mostrador") {
        setTimeout(() => document.getElementById("posScannerInput")?.focus(), 50);
      }
    },
    setPosCategory(cat, btn) {
      state.selectedCategory = cat;
      state.selectedSubcat = "";
      state.selectedBrand = "TODAS";
      document.querySelectorAll("#posCategoryCards .pos-cat-card").forEach((b) => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      document.querySelectorAll("#posSubcatPills .pill-btn").forEach((b) => b.classList.toggle("active", b.dataset.sub === ""));
      renderBrands();
      renderCatalog();
    },
    setPosSubcat(sub, btn) {
      state.selectedSubcat = sub;
      state.selectedBrand = "TODAS";
      document.querySelectorAll("#posSubcatPills .pill-btn").forEach((b) => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      renderBrands();
      renderCatalog();
    },
    setBrand(b) {
      state.selectedBrand = b;
      renderBrands();
      renderCatalog();
    },
    clickProductCard,
    setChannel(ch, btn) {
      state.channel = ch;
      document.querySelectorAll("#posChannelGroup .pos-choice-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    },
    setPayment(pm, btn) {
      state.paymentMethod = pm;
      document.querySelectorAll("#posPaymentGroup .pos-choice-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const chk = document.getElementById("posApplyTransferDiscount");
      if (chk) chk.checked = pm === "EFECTIVO" || pm === "TRANSFERENCIA";

      const refWrap = document.getElementById("posPaymentRefWrap");
      const refLabel = document.getElementById("posPaymentRefLabel");
      const refInput = document.getElementById("posPaymentRef");
      if (refWrap) {
        if (pm === "EFECTIVO") {
          refWrap.style.display = "none";
          if (refInput) refInput.value = "";
        } else {
          refWrap.style.display = "block";
          if (pm === "TRANSFERENCIA") {
            if (refLabel) refLabel.textContent = "Nro. de transferencia";
            if (refInput) refInput.placeholder = "Ej: Nro. de operación / transferencia";
          } else if (pm === "MERCADOPAGO") {
            if (refLabel) refLabel.textContent = "Nro. de operación Mercado Pago";
            if (refInput) refInput.placeholder = "Ej: 1234567890";
          } else {
            if (refLabel) refLabel.textContent = "Nro. de ticket / cupón tarjeta";
            if (refInput) refInput.placeholder = "Ej: Cupón / lote posnet";
          }
        }
      }
      renderCart();
    },
    addVariant,
    scanLookup,
    changeQty,
    clearCart() {
      state.cart = [];
      renderCart();
    },
    renderCart,
    submitSale,
    openCloseCashModal,
    updateCloseDiff,
    reprintOrder(orderId) {
      const o = state.recentSales.find((x) => x.id === orderId);
      if (o) openReceiptModal(o);
    },
    shareReceiptImage,
    renderStockTab,
    onStockSearch() {
      state.stockPage = 1;
      renderStockTab();
    },
    setStockPage(page) {
      state.stockPage = page;
      renderStockTab();
    },
    quickRestock: setVariantStock,
    setVariantStock,
    savePrice,
    toggleActive,
    toggleOutlet,
    deleteProduct,
    openEditProduct,
    openBarcodeModal,
    renderBarcodePreview,
    printBarcodes,
    uploadEditImage,
    addEditImageUrl,
    removeEditImage,
    uploadNewImage,
    addNewImageUrl,
    removeNewImage,
    setCoverImage,
    moveImage,
    removeImage,
    importProductsFile,
    addEditVariantRow,
    setSalesFilter(f, btn) {
      state.salesFilter = f;
      document.querySelectorAll(".sales-filter-btn").forEach((b) => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      renderRecentSalesTab();
    },
    updateOrderField,
    saveTracking,
    cancelOrder,
    async logout() {
      await fetch("/api/admin/logout", { method: "POST" });
      window.location.reload();
    },
  };

  loadState();
})();
