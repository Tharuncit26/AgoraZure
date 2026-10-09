/**
 * AgoraZure - Shopkeeper Merchant Dashboard Logic
 * Connected to Real Shared Backend (PostgreSQL / Supabase / SQLite)
 * Zéphyr 2026 AI Hackathon - PS-2: Smart Commerce
 */

function getApiBase() {
  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8000/api";
  }
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    if (window.location.port && window.location.port !== "8000") {
      return `http://${window.location.hostname}:8000/api`;
    }
  }
  return "/api";
}
const API_BASE = getApiBase();

// Application State
let currentShop = null;
let currentShopkeeper = null;
let shopCatalog = [];
let activeOffers = [];
let currentOrderFilter = "";
let ordersPollInterval = null;
let lastKnownOrdersCount = 0;
let audioNotificationsEnabled = true;

// POS Billing Session State
let billingSessions = {
  tab_1: { items: [], total: 0 },
  tab_2: { items: [], total: 0 }
};
let activeBillingTab = "tab_1";

// =========================================================================
// 1. INITIALIZATION & AUTHENTICATION
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
  initShopkeeperAuth();
});

function initShopkeeperAuth() {
  const saved = localStorage.getItem("agorazure_shopkeeper");
  if (saved) {
    try {
      const data = JSON.parse(saved);
      currentShopkeeper = data;
      currentShop = {
        id: data.shop_id,
        shop_id: data.shop_id,
        name: data.shop_name,
        owner_name: data.name,
        phone: data.phone,
        email: data.email,
        address: data.address,
        is_open: data.is_open !== undefined ? data.is_open : true
      };
      setupMerchantApp();
      return;
    } catch (e) {
      localStorage.removeItem("agorazure_shopkeeper");
    }
  }
  showModal("shopAuthModal");
}

function setupMerchantApp() {
  renderShopkeeperHeader();
  hideModal("shopAuthModal");
  document.getElementById("shopkeeperDashboardSection").style.display = "flex";

  // Load store data
  loadShopDashboardMetrics();
  loadShopkeeperOrders("");
  loadShopStock();
  loadOffers();
  loadSharedDelivery();
  loadDemandInsights();

  // Polling every 4 seconds for new incoming orders
  if (ordersPollInterval) clearInterval(ordersPollInterval);
  ordersPollInterval = setInterval(() => {
    if (currentShop) {
      loadShopkeeperOrders(currentOrderFilter, true);
    }
  }, 4000);
}

function renderShopkeeperHeader() {
  if (!currentShop) return;

  const authBar = document.getElementById("shopAuthBar");
  if (authBar) authBar.style.display = "flex";

  const nameEl = document.getElementById("shopNameDisplay");
  if (nameEl) nameEl.textContent = currentShop.name || "My Store";

  const ownerEl = document.getElementById("shopOwnerDisplay");
  if (ownerEl) ownerEl.textContent = `${currentShop.owner_name} • ${currentShop.address.split(',')[0]}`;

  updateOpenStatusBadge(currentShop.is_open);
}

function updateOpenStatusBadge(isOpen) {
  const badge = document.getElementById("shopOpenStatusBadge");
  if (badge) {
    if (isOpen) {
      badge.textContent = "OPEN";
      badge.style.background = "#dcfce7";
      badge.style.color = "#15803d";
    } else {
      badge.textContent = "CLOSED";
      badge.style.background = "#fee2e2";
      badge.style.color = "#b91c1c";
    }
  }
}

function switchShopAuthTab(tab) {
  const loginForm = document.getElementById("shopLoginFormContainer");
  const regForm = document.getElementById("shopRegisterFormContainer");
  const tabLogin = document.getElementById("tabShopLogin");
  const tabReg = document.getElementById("tabShopRegister");

  if (tab === "register") {
    loginForm.style.display = "none";
    regForm.style.display = "block";
    tabReg.style.color = "var(--primary)";
    tabReg.style.borderBottomColor = "var(--primary)";
    tabLogin.style.color = "var(--text-muted)";
    tabLogin.style.borderBottomColor = "transparent";
  } else {
    loginForm.style.display = "block";
    regForm.style.display = "none";
    tabLogin.style.color = "var(--primary)";
    tabLogin.style.borderBottomColor = "var(--primary)";
    tabReg.style.color = "var(--text-muted)";
    tabReg.style.borderBottomColor = "transparent";
  }
}

async function handleShopkeeperLogin(e) {
  e.preventDefault();
  const form = e.target;
  const identifier = form.identifier.value.trim();
  const password = form.password.value.trim();

  const payload = {
    phone: identifier.includes("@") ? null : identifier,
    email: identifier.includes("@") ? identifier : null,
    password: password
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopkeeper/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success && data.shopkeeper) {
      currentShopkeeper = data.shopkeeper;
      localStorage.setItem("agorazure_shopkeeper", JSON.stringify(currentShopkeeper));
      currentShop = {
        id: currentShopkeeper.shop_id,
        shop_id: currentShopkeeper.shop_id,
        name: currentShopkeeper.shop_name,
        owner_name: currentShopkeeper.name,
        phone: currentShopkeeper.phone,
        email: currentShopkeeper.email,
        address: currentShopkeeper.address,
        is_open: currentShopkeeper.is_open !== undefined ? currentShopkeeper.is_open : true
      };
      showToast(`Welcome back, ${currentShopkeeper.name}!`, "success");
      setupMerchantApp();
    } else {
      showToast(data.detail || "Invalid login credentials.", "danger");
    }
  } catch (err) {
    showToast("Network error. Unable to connect to server.", "danger");
  }
}

async function quickShopkeeperLogin(phone, password) {
  const res = await fetch(`${API_BASE}/auth/shopkeeper/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, password })
  });
  const data = await res.json();
  if (res.ok && data.success && data.shopkeeper) {
    currentShopkeeper = data.shopkeeper;
    localStorage.setItem("agorazure_shopkeeper", JSON.stringify(currentShopkeeper));
    currentShop = {
      id: currentShopkeeper.shop_id,
      shop_id: currentShopkeeper.shop_id,
      name: currentShopkeeper.shop_name,
      owner_name: currentShopkeeper.name,
      phone: currentShopkeeper.phone,
      email: currentShopkeeper.email,
      address: currentShopkeeper.address,
      is_open: currentShopkeeper.is_open !== undefined ? currentShopkeeper.is_open : true
    };
    showToast(`Logged into ${currentShop.name}`, "success");
    setupMerchantApp();
  } else {
    showToast(data.detail || "Quick login failed.", "danger");
  }
}

async function handleRegisterShop(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    shop_name: form.shop_name.value.trim(),
    owner_name: form.owner_name.value.trim(),
    phone: form.phone.value.trim(),
    email: form.email.value.trim() || null,
    password: form.password.value,
    address: form.address.value.trim(),
    category: form.category.value,
    opening_hours: form.opening_hours.value.trim(),
    photo_url: form.photo_url.value.trim() || null,
    latitude: 12.9716,
    longitude: 77.6412
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopkeeper/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(data.message || "Store registered successfully!", "success");
      await quickShopkeeperLogin(payload.phone, payload.password);
    } else {
      showToast(data.detail || "Registration failed. Phone may already be registered.", "danger");
    }
  } catch (err) {
    showToast("Network error registering store.", "danger");
  }
}

function shopkeeperLogout() {
  localStorage.removeItem("agorazure_shopkeeper");
  currentShop = null;
  currentShopkeeper = null;
  if (ordersPollInterval) clearInterval(ordersPollInterval);
  showToast("You have been signed out.", "info");
  location.reload();
}

async function toggleShopOpenState() {
  if (!currentShop) return;

  const targetState = !currentShop.is_open;
  try {
    const res = await fetch(`${API_BASE}/auth/shopkeeper/toggle-open?shop_id=${currentShop.shop_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_open: targetState })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      currentShop.is_open = targetState;
      currentShopkeeper.is_open = targetState;
      localStorage.setItem("agorazure_shopkeeper", JSON.stringify(currentShopkeeper));
      updateOpenStatusBadge(targetState);
      showToast(data.message || (targetState ? "Store is now OPEN" : "Store is now CLOSED"), targetState ? "success" : "warning");
    }
  } catch (err) {
    showToast("Error updating store status", "danger");
  }
}

// =========================================================================
// 2. NAVIGATION & TABS
// =========================================================================

function switchShopTab(tabName, linkEl) {
  document.querySelectorAll(".sidebar-link").forEach(el => el.classList.remove("active"));
  if (linkEl) linkEl.classList.add("active");

  const sections = ["dashboard", "orders", "inventory", "billing", "offers", "delivery"];
  sections.forEach(s => {
    const pane = document.getElementById(`pane-${s}`);
    if (pane) pane.style.display = s === tabName ? "block" : "none";
  });

  if (tabName === "orders") loadShopkeeperOrders(currentOrderFilter);
  if (tabName === "inventory") loadShopStock();
  if (tabName === "billing") setupPosBilling();
  if (tabName === "offers") loadOffers();
  if (tabName === "delivery") loadSharedDelivery();
  if (tabName === "dashboard") loadShopDashboardMetrics();
}

// =========================================================================
// 3. LIVE ORDERS MANAGEMENT & BUG 5 FIX
// =========================================================================

async function loadShopkeeperOrders(filterStatus = "", isSilent = false) {
  if (!currentShop) return;
  currentOrderFilter = filterStatus;
  const container = document.getElementById("ordersListContainer");
  const url = filterStatus 
    ? `${API_BASE}/orders/shopkeeper/list?shop_id=${currentShop.shop_id}&status_filter=${filterStatus}`
    : `${API_BASE}/orders/shopkeeper/list?shop_id=${currentShop.shop_id}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (res.ok && data.success) {
      const orders = data.orders || [];
      const counts = data.counts || {};

      // Update counters
      document.getElementById("countAll").textContent = counts.all || orders.length;
      document.getElementById("countPending").textContent = counts.pending || 0;
      document.getElementById("countAccepted").textContent = counts.accepted || 0;
      document.getElementById("countPreparing").textContent = counts.preparing || 0;
      document.getElementById("countReady").textContent = (counts.ready || 0) + (counts.out_for_delivery || 0);
      document.getElementById("countDelivered").textContent = counts.delivered || 0;
      document.getElementById("countRejected").textContent = counts.rejected || 0;

      // KPI cards update
      const kpiPending = document.getElementById("kpiPendingOrders");
      if (kpiPending) kpiPending.textContent = counts.pending || 0;
      const sidebarBadge = document.getElementById("sidebarOrderCount");
      if (sidebarBadge) {
        if ((counts.pending || 0) > 0) {
          sidebarBadge.textContent = counts.pending;
          sidebarBadge.style.display = "inline-block";
        } else {
          sidebarBadge.style.display = "none";
        }
      }

      // Check for incoming new order alert
      if (counts.pending > lastKnownOrdersCount && lastKnownOrdersCount !== 0) {
        playOrderNotificationChime();
        const alertBanner = document.getElementById("newOrderAlertBanner");
        if (alertBanner) alertBanner.style.display = "block";
        showToast(`🔔 New order received! Order action needed.`, "success");
      }
      lastKnownOrdersCount = counts.pending || 0;

      // Render cards
      if (orders.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">📭</div>
            <div style="font-weight: 700;">No Orders in this category</div>
            <p style="font-size: 0.85rem;">New orders from nearby shoppers will appear here in real time.</p>
          </div>
        `;
        return;
      }

      const statusBadgeStyles = {
        pending: "badge-pending",
        accepted: "badge-accepted",
        preparing: "badge-preparing",
        ready: "badge-ready",
        out_for_delivery: "badge-out",
        delivered: "badge-delivered",
        rejected: "badge-danger",
        cancelled: "badge-danger"
      };

      container.innerHTML = orders.map(o => {
        const orderId = o.id || o.orderId;
        const status = (o.status || "pending").toLowerCase();
        const badgeClass = statusBadgeStyles[status] || "badge-secondary";
        const items = o.items || [];
        const quantity = items.reduce((s, it) => s + it.quantity, 0);

        // Explicit Action Buttons: NO auto-rejection! ONLY manual clicks change status!
        let actionButtonsHtml = '';
        if (status === 'pending') {
          actionButtonsHtml = `
            <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${orderId}, 'accepted')">
              ✓ Accept Order
            </button>
            <button class="btn btn-outline-danger btn-sm" onclick="openRejectOrderModal(${orderId})">
              ✕ Reject
            </button>
          `;
        } else if (status === 'accepted') {
          actionButtonsHtml = `
            <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${orderId}, 'preparing')">
              🍳 Start Preparing
            </button>
            <button class="btn btn-accent btn-sm" onclick="updateOrderStatus(${orderId}, 'ready')">
              Mark Ready
            </button>
            <button class="btn btn-outline-danger btn-sm" onclick="openRejectOrderModal(${orderId})">
              Reject
            </button>
          `;
        } else if (status === 'preparing') {
          actionButtonsHtml = `
            <button class="btn btn-accent btn-sm" onclick="updateOrderStatus(${orderId}, 'ready')">
              ✓ Mark Ready for Pickup / Delivery
            </button>
            <button class="btn btn-outline-danger btn-sm" onclick="openRejectOrderModal(${orderId})">
              Reject
            </button>
          `;
        } else if (status === 'ready') {
          if (o.collect_option === 'home_delivery') {
            actionButtonsHtml = `
              <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${orderId}, 'out_for_delivery')">
                🛵 Out for Delivery
              </button>
              <button class="btn btn-success btn-sm" onclick="updateOrderStatus(${orderId}, 'delivered')">
                ✓ Mark Delivered
              </button>
            `;
          } else {
            actionButtonsHtml = `
              <button class="btn btn-success btn-sm" onclick="updateOrderStatus(${orderId}, 'delivered')">
                ✓ Customer Picked Up
              </button>
            `;
          }
        } else if (status === 'out_for_delivery') {
          actionButtonsHtml = `
            <button class="btn btn-success btn-sm" onclick="updateOrderStatus(${orderId}, 'delivered')">
              ✓ Mark Delivered
            </button>
          `;
        }

        return `
          <div class="order-card" style="border-left: 4px solid var(--primary);">
            <div class="card-header" style="flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
              <div>
                <strong style="font-size: 1.05rem;">${o.order_number}</strong>
                <span style="font-size: 0.78rem; color: var(--text-muted); margin-left: 0.35rem;">(ID: ${orderId})</span>
                <span class="badge ${badgeClass}" style="margin-left: 0.4rem;">
                  ${status.replace(/_/g, ' ')}
                </span>
              </div>
              <div style="font-size: 1.25rem; font-weight: 800; color: var(--primary);">
                ₹${Number(o.total_amount || o.total).toFixed(2)}
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">
              <div>Shopper: <strong>${escapeHtml(o.shopper_name)}</strong> ${o.shopper_phone ? `(${o.shopper_phone})` : ''}</div>
              <div>Fulfillment: <strong>${o.collect_option === 'home_delivery' ? '🛵 Home Delivery' : '🏬 Store Pickup'}</strong></div>
              <div>Time: <strong>${o.time || o.created_at}</strong></div>
            </div>

            ${o.delivery_address ? `
              <div style="font-size: 0.82rem; color: var(--text-body); background: var(--bg-subtle); padding: 0.4rem 0.6rem; border-radius: var(--radius-xs); margin-bottom: 0.6rem;">
                📍 <strong>Address:</strong> ${escapeHtml(o.delivery_address)}
              </div>
            ` : ''}

            <!-- Items -->
            <div style="background: var(--bg-subtle); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); font-size: 0.85rem; margin-bottom: 0.85rem;">
              <div style="font-weight: 700; margin-bottom: 0.3rem;">Items (${quantity} total qty):</div>
              ${items.map(it => `
                <div style="display: flex; justify-content: space-between; padding: 0.15rem 0;">
                  <span>• ${escapeHtml(it.product_name)} × <strong>${it.quantity}</strong></span>
                  <span>₹${Number(it.subtotal).toFixed(2)}</span>
                </div>
              `).join("")}
            </div>

            ${status === 'rejected' ? `
              <div style="color: var(--danger); font-size: 0.84rem; font-weight: 600; margin-bottom: 0.5rem;">
                Rejection Reason: "${escapeHtml(o.reject_reason || 'Store could not fulfill items')}"
              </div>
            ` : ''}

            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; border-top: 1px solid var(--border-light); padding-top: 0.65rem;">
              <!-- Quick manual action buttons -->
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                ${actionButtonsHtml}
              </div>

              <!-- Manual Status Override Selector -->
              <div style="display: flex; align-items: center; gap: 0.4rem;">
                <span style="font-size: 0.8rem; color: var(--text-muted);">Change:</span>
                <select class="form-control" style="width: auto; padding: 0.25rem 0.5rem; font-size: 0.82rem;" onchange="updateOrderStatus(${orderId}, this.value)">
                  <option value="pending" ${status === 'pending' ? 'selected' : ''}>Pending</option>
                  <option value="accepted" ${status === 'accepted' ? 'selected' : ''}>Accepted</option>
                  <option value="preparing" ${status === 'preparing' ? 'selected' : ''}>Preparing</option>
                  <option value="ready" ${status === 'ready' ? 'selected' : ''}>Ready</option>
                  <option value="out_for_delivery" ${status === 'out_for_delivery' ? 'selected' : ''}>Out for Delivery</option>
                  <option value="delivered" ${status === 'delivered' ? 'selected' : ''}>Delivered</option>
                  <option value="rejected" ${status === 'rejected' ? 'selected' : ''}>Rejected</option>
                </select>
              </div>
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    if (!isSilent) console.error("Error loading orders:", err);
  }
}

function filterOrdersByStatus(st, btnEl) {
  document.querySelectorAll(".order-filter-bar .btn").forEach(el => el.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");
  const alertBanner = document.getElementById("newOrderAlertBanner");
  if (alertBanner) alertBanner.style.display = "none";
  loadShopkeeperOrders(st);
}

// UPDATE ORDER STATUS: Strictly updates to the chosen status!
async function updateOrderStatus(orderId, newStatus, reason = null) {
  if (!currentShop) return;

  const payload = {
    status: newStatus,
    reject_reason: reason
  };

  try {
    const res = await fetch(`${API_BASE}/orders/status/${orderId}?shop_id=${currentShop.shop_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(data.message || `Order status updated to ${newStatus.toUpperCase()}`, "success");
      loadShopkeeperOrders(currentOrderFilter);
      loadShopStock();
      loadShopDashboardMetrics();
    } else {
      showToast(data.detail || "Failed to update status", "danger");
    }
  } catch (err) {
    showToast("Error updating order status.", "danger");
  }
}

function openRejectOrderModal(orderId) {
  document.getElementById("rejectTargetOrderId").value = orderId;
  document.getElementById("rejectReasonCustom").value = "";
  showModal("rejectOrderModal");
}

function handleRejectPresetChange(val) {
  const custom = document.getElementById("rejectReasonCustom");
  if (val !== "Other") {
    custom.value = val;
  } else {
    custom.value = "";
    custom.focus();
  }
}

function handleConfirmOrderRejection(e) {
  e.preventDefault();
  const orderId = document.getElementById("rejectTargetOrderId").value;
  const reason = document.getElementById("rejectReasonCustom").value.trim() || document.getElementById("rejectReasonPreset").value;

  hideModal("rejectOrderModal");
  updateOrderStatus(orderId, "rejected", reason);
}

// Sound notification using Web Audio API synthesis
function playOrderNotificationChime() {
  if (!audioNotificationsEnabled) return;

  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();

    // Play a friendly multi-tone chime (C5, E5, G5)
    const tones = [523.25, 659.25, 783.99];
    tones.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.12, ctx.currentTime + idx * 0.12);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + idx * 0.12 + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + idx * 0.12);
      osc.stop(ctx.currentTime + idx * 0.12 + 0.4);
    });
  } catch (err) {}
}

function toggleAudioNotifications() {
  audioNotificationsEnabled = !audioNotificationsEnabled;
  const btn = document.getElementById("btnAudioToggle");
  if (btn) {
    btn.textContent = audioNotificationsEnabled ? "🔔 Sound: ON" : "🔕 Sound: MUTED";
  }
  showToast(`Order sound notifications ${audioNotificationsEnabled ? 'enabled' : 'muted'}.`, "info");
}

// =========================================================================
// 4. INVENTORY MANAGEMENT & BUG 7 FIX
// =========================================================================

async function loadShopStock() {
  if (!currentShop) return;

  const cat = document.getElementById("stockCategoryFilter") ? document.getElementById("stockCategoryFilter").value : "";
  const status = document.getElementById("stockStatusFilter") ? document.getElementById("stockStatusFilter").value : "";

  let url = `${API_BASE}/stock/products?shop_id=${currentShop.shop_id}`;
  if (cat) url += `&category=${encodeURIComponent(cat)}`;
  if (status) url += `&status_filter=${encodeURIComponent(status)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (res.ok && data.success) {
      shopCatalog = data.products || [];
      renderStockTable(shopCatalog);
      populateOfferProductsDropdown(shopCatalog);
      renderPosQuickItems(shopCatalog);

      // Low stock KPI
      const lowCount = shopCatalog.filter(p => p.is_low_stock).length;
      const kpiLow = document.getElementById("kpiLowStock");
      if (kpiLow) kpiLow.textContent = lowCount;
    }
  } catch (err) {
    console.error("Error loading stock:", err);
  }
}

function renderStockTable(products) {
  const tbody = document.getElementById("stockTableBody");
  if (!tbody) return;

  if (!products || products.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No products registered. Click '+ Add New Product' to stock items.</td></tr>`;
    return;
  }

  tbody.innerHTML = products.map(p => {
    const isOut = p.total_quantity === 0;
    const isLow = p.is_low_stock;
    const badgeClass = isOut ? "badge-danger" : (isLow ? "badge-warning" : "badge-success");
    const stockStatus = isOut ? "OUT OF STOCK" : (isLow ? "LOW STOCK" : "IN STOCK");
    const isAvail = p.is_available !== false;

    return `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <img src="${p.image_url || 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=100'}" style="width: 36px; height: 36px; border-radius: var(--radius-xs); object-fit: cover;" onerror="this.src='https://images.unsplash.com/photo-1542838132-92c53300491e?w=100'">
            <div>
              <div style="font-weight: 700;">${escapeHtml(p.name)}</div>
              <span class="badge" style="background: var(--bg-subtle); color: var(--text-muted); font-size: 0.68rem;">${p.category} • ${p.unit || '1 pc'}</span>
            </div>
          </div>
        </td>
        <td><code>${p.barcode}</code></td>
        <td>
          <div style="font-weight: 700;">₹${Number(p.price).toFixed(2)}</div>
          ${p.mrp ? `<div style="font-size: 0.75rem; color: var(--text-light); text-decoration: line-through;">₹${Number(p.mrp).toFixed(2)}</div>` : ''}
        </td>
        <td>
          <span style="font-size: 1.15rem; font-weight: 800;">${p.total_quantity}</span>
          <span class="badge ${badgeClass}" style="margin-left: 0.35rem;">${stockStatus}</span>
        </td>
        <td>${p.low_stock_threshold || 5}</td>
        <td>
          <span style="font-size: 0.85rem;">${p.earliest_expiry}</span>
          <div style="font-size: 0.72rem; color: var(--text-muted);">${p.batches ? p.batches.length : 0} batch(es)</div>
        </td>
        <td style="text-align: right;">
          <div style="display: flex; gap: 0.35rem; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="openQuickStockModal(${p.id}, '${escapeHtml(p.name)}', ${p.total_quantity})" title="Adjust stock count">
              📦 Stock
            </button>
            <button class="btn btn-secondary btn-sm" onclick="openEditProductModal(${p.id})" title="Edit product details">
              ✏️
            </button>
            <button class="btn btn-sm ${isAvail ? 'btn-success' : 'btn-secondary'}" onclick="toggleProductAvailability(${p.id})" title="Toggle online availability">
              ${isAvail ? '● Live' : '○ Off'}
            </button>
            <button class="btn btn-outline-danger btn-sm" onclick="deleteProduct(${p.id}, '${escapeHtml(p.name)}')" title="Delete product">
              🗑️
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function filterStockTable(query) {
  const q = query.toLowerCase().trim();
  const filtered = shopCatalog.filter(p => 
    p.name.toLowerCase().includes(q) || 
    p.barcode.toLowerCase().includes(q) ||
    p.category.toLowerCase().includes(q)
  );
  renderStockTable(filtered);
}

function openAddProductModal() {
  document.getElementById("productForm").reset();
  document.getElementById("productEditId").value = "";
  document.getElementById("addProductModalTitle").textContent = "📦 Add Product to Store Inventory";
  document.getElementById("btnSaveProduct").textContent = "Save Product to Inventory";
  document.getElementById("initialBatchGroup").style.display = "grid";
  document.getElementById("prodImagePreview").style.display = "none";
  showModal("addProductModal");
}

function openEditProductModal(prodId) {
  const p = shopCatalog.find(item => item.id === prodId);
  if (!p) return;

  document.getElementById("productEditId").value = p.id;
  document.getElementById("prodNameInput").value = p.name;
  document.getElementById("prodBarcodeInput").value = p.barcode;
  document.getElementById("prodBrandInput").value = p.brand || "General";
  document.getElementById("prodCategoryInput").value = p.category;
  document.getElementById("prodPriceInput").value = p.price;
  document.getElementById("prodMrpInput").value = p.mrp || "";
  document.getElementById("prodUnitInput").value = p.unit || "1 pc";
  document.getElementById("prodThresholdInput").value = p.low_stock_threshold || 5;
  document.getElementById("prodImageInput").value = p.image_url || "";
  document.getElementById("prodDescInput").value = p.description || "";
  document.getElementById("prodAvailableInput").checked = p.is_available !== false;

  updateImagePreview(p.image_url);

  document.getElementById("addProductModalTitle").textContent = "✏️ Edit Product Details";
  document.getElementById("btnSaveProduct").textContent = "Update Product";
  document.getElementById("initialBatchGroup").style.display = "none";

  showModal("addProductModal");
}

function updateImagePreview(url) {
  const preview = document.getElementById("prodImagePreview");
  if (url && url.trim()) {
    preview.src = url;
    preview.style.display = "block";
  } else {
    preview.style.display = "none";
  }
}

async function handleSaveProduct(e) {
  e.preventDefault();
  if (!currentShop) return;

  const editId = document.getElementById("productEditId").value;
  const isEdit = Boolean(editId);

  const payload = {
    name: document.getElementById("prodNameInput").value.trim(),
    barcode: document.getElementById("prodBarcodeInput").value.trim() || null,
    brand: document.getElementById("prodBrandInput").value.trim(),
    category: document.getElementById("prodCategoryInput").value,
    price: parseFloat(document.getElementById("prodPriceInput").value),
    mrp: document.getElementById("prodMrpInput").value ? parseFloat(document.getElementById("prodMrpInput").value) : null,
    unit: document.getElementById("prodUnitInput").value.trim(),
    low_stock_threshold: parseInt(document.getElementById("prodThresholdInput").value) || 5,
    image_url: document.getElementById("prodImageInput").value.trim() || null,
    description: document.getElementById("prodDescInput").value.trim() || null,
    is_available: document.getElementById("prodAvailableInput").checked
  };

  if (!isEdit) {
    payload.initial_quantity = parseInt(document.getElementById("prodInitialQtyInput").value) || 0;
    payload.expiry_date = document.getElementById("prodExpiryInput").value || "2027-12-31";
  }

  const url = isEdit 
    ? `${API_BASE}/stock/product/${editId}?shop_id=${currentShop.shop_id}`
    : `${API_BASE}/stock/product?shop_id=${currentShop.shop_id}`;
  const method = isEdit ? "PUT" : "POST";

  try {
    const res = await fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(data.message || (isEdit ? "Product updated!" : "Product added to inventory!"), "success");
      hideModal("addProductModal");
      loadShopStock();
      loadShopDashboardMetrics();
    } else {
      showToast(data.detail || "Failed to save product", "danger");
    }
  } catch (err) {
    showToast("Network error saving product", "danger");
  }
}

function openQuickStockModal(prodId, prodName, currentQty) {
  document.getElementById("stockTargetProdId").value = prodId;
  document.getElementById("stockProdNameLabel").textContent = prodName;
  document.getElementById("currentStockCountDisplay").textContent = currentQty;
  document.getElementById("quickStockQtyInput").value = currentQty;
  showModal("quickStockModal");
}

async function handleQuickStockUpdate(e) {
  e.preventDefault();
  if (!currentShop) return;

  const prodId = document.getElementById("stockTargetProdId").value;
  const targetQty = parseInt(document.getElementById("quickStockQtyInput").value);
  const expiry = document.getElementById("quickStockExpiryInput").value;

  try {
    const res = await fetch(`${API_BASE}/stock/product/${prodId}/stock?shop_id=${currentShop.shop_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity: targetQty, expiry_date: expiry })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(data.message || "Stock level updated!", "success");
      hideModal("quickStockModal");
      loadShopStock();
      loadShopDashboardMetrics();
    } else {
      showToast(data.detail || "Failed to update stock", "danger");
    }
  } catch (err) {
    showToast("Error updating stock count", "danger");
  }
}

async function toggleProductAvailability(prodId) {
  if (!currentShop) return;
  try {
    const res = await fetch(`${API_BASE}/stock/product/${prodId}/toggle-availability?shop_id=${currentShop.shop_id}`, {
      method: "PUT"
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, "info");
      loadShopStock();
    }
  } catch (err) {}
}

async function deleteProduct(prodId, prodName) {
  if (!confirm(`Are you sure you want to delete "${prodName}" from inventory? This will also remove its stock batches.`)) return;
  if (!currentShop) return;

  try {
    const res = await fetch(`${API_BASE}/stock/product/${prodId}?shop_id=${currentShop.shop_id}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message || "Product deleted.", "success");
      loadShopStock();
      loadShopDashboardMetrics();
    } else {
      showToast(data.detail || "Failed to delete product", "danger");
    }
  } catch (err) {
    showToast("Network error deleting product", "danger");
  }
}

// =========================================================================
// 5. SEASONAL OFFERS MANAGEMENT & BUG 8 FIX
// =========================================================================

async function loadOffers() {
  if (!currentShop) return;
  try {
    const res = await fetch(`${API_BASE}/marketing/offers?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success) {
      activeOffers = data.offers || [];
      const container = document.getElementById("offersListContainer");
      if (activeOffers.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">🏷️</div>
            <div style="font-weight: 700;">No Seasonal Offers Active</div>
            <p style="font-size: 0.85rem;">Create festival discounts to attract nearby shoppers on the mobile portal.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = activeOffers.map(o => `
        <div class="card" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-left: 4px solid var(--accent); flex-wrap: wrap; gap: 0.75rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
              <strong style="font-size: 1.05rem;">${escapeHtml(o.title)}</strong>
              <span class="badge badge-success" style="font-weight: 800;">${o.discount_percent}% OFF</span>
            </div>
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.25rem;">
              Target: <strong>${escapeHtml(o.product_name)}</strong> • Valid: <strong>${o.valid_from}</strong> to <strong>${o.valid_to}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 0.4rem;">
            <button class="btn btn-secondary btn-sm" onclick="openEditOfferModal(${o.id})">✏️ Edit</button>
            <button class="btn btn-outline-danger btn-sm" onclick="deleteOffer(${o.id})">🗑️ Delete</button>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {}
}

function populateOfferProductsDropdown(products) {
  const sel = document.getElementById("offerProductSelect");
  if (!sel) return;
  const currentVal = sel.value;
  sel.innerHTML = `<option value="">All Products (Store-wide discount)</option>` +
    (products || []).map(p => `<option value="${p.id}">${escapeHtml(p.name)} (₹${Number(p.price).toFixed(2)})</option>`).join("");
  if (currentVal) sel.value = currentVal;
}

function openCreateOfferModal() {
  document.getElementById("createOfferForm").reset();
  document.getElementById("offerEditId").value = "";
  document.getElementById("offerModalTitle").textContent = "🏷️ Create Seasonal Offer";
  document.getElementById("offerSubmitBtn").textContent = "Publish Offer";

  const todayStr = new Date().toISOString().split("T")[0];
  const nextMonth = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
  document.getElementById("offerValidFromInput").value = todayStr;
  document.getElementById("offerValidToInput").value = nextMonth;

  populateOfferProductsDropdown(shopCatalog);
  showModal("createOfferModal");
}

function openEditOfferModal(offerId) {
  const offer = activeOffers.find(o => o.id === offerId);
  if (!offer) return;

  populateOfferProductsDropdown(shopCatalog);
  document.getElementById("offerEditId").value = offer.id;
  document.getElementById("offerTitleInput").value = offer.title;
  document.getElementById("offerDiscountInput").value = offer.discount_percent;
  document.getElementById("offerProductSelect").value = offer.product_id ? String(offer.product_id) : "";
  document.getElementById("offerValidFromInput").value = offer.valid_from;
  document.getElementById("offerValidToInput").value = offer.valid_to;

  document.getElementById("offerModalTitle").textContent = "✏️ Edit Seasonal Offer";
  document.getElementById("offerSubmitBtn").textContent = "Save Changes";

  showModal("createOfferModal");
}

async function handleCreateOffer(e) {
  e.preventDefault();
  if (!currentShop) return;

  const editId = document.getElementById("offerEditId").value;
  const isEdit = Boolean(editId);

  const payload = {
    title: document.getElementById("offerTitleInput").value.trim(),
    discount_percent: parseFloat(document.getElementById("offerDiscountInput").value),
    product_id: document.getElementById("offerProductSelect").value ? parseInt(document.getElementById("offerProductSelect").value) : null,
    valid_from: document.getElementById("offerValidFromInput").value,
    valid_to: document.getElementById("offerValidToInput").value
  };

  const url = isEdit
    ? `${API_BASE}/marketing/offers/${editId}?shop_id=${currentShop.shop_id}`
    : `${API_BASE}/marketing/offers?shop_id=${currentShop.shop_id}`;
  const method = isEdit ? "PUT" : "POST";

  try {
    const res = await fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(data.message || (isEdit ? "Offer updated!" : "Seasonal offer published!"), "success");
      hideModal("createOfferModal");
      loadOffers();
    } else {
      showToast(data.detail || "Failed to save offer", "danger");
    }
  } catch (err) {
    showToast("Error saving offer", "danger");
  }
}

async function deleteOffer(offerId) {
  if (!confirm("Are you sure you want to remove this seasonal offer?")) return;
  if (!currentShop) return;

  try {
    const res = await fetch(`${API_BASE}/marketing/offers/${offerId}?shop_id=${currentShop.shop_id}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message || "Offer removed", "success");
      loadOffers();
    } else {
      showToast(data.detail || "Failed to delete offer", "danger");
    }
  } catch (err) {
    showToast("Error deleting offer", "danger");
  }
}

// =========================================================================
// 6. DASHBOARD KPI METRICS & RECENT ORDERS
// =========================================================================

async function loadShopDashboardMetrics() {
  if (!currentShop) return;

  try {
    const res = await fetch(`${API_BASE}/orders/shopkeeper/list?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success && data.orders) {
      const orders = data.orders;
      const todayStr = new Date().toISOString().split("T")[0];
      const todayOrders = orders.filter(o => (o.time || o.created_at || "").startsWith(todayStr));
      const totalRev = orders.filter(o => o.status !== 'rejected').reduce((s, o) => s + (o.total_amount || 0), 0);

      document.getElementById("kpiTodayOrders").textContent = todayOrders.length || orders.length;
      document.getElementById("kpiRevenue").textContent = `₹${totalRev.toFixed(2)}`;

      // Render recent 3 orders
      const recentContainer = document.getElementById("dashboardRecentOrders");
      if (recentContainer) {
        if (orders.length === 0) {
          recentContainer.innerHTML = `<div class="empty-state">No orders yet.</div>`;
        } else {
          recentContainer.innerHTML = orders.slice(0, 3).map(o => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border-light);">
              <div>
                <strong>${o.order_number}</strong> • ${escapeHtml(o.shopper_name)}
                <div style="font-size: 0.75rem; color: var(--text-muted);">${o.time || o.created_at}</div>
              </div>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span class="badge ${o.status === 'pending' ? 'badge-pending' : (o.status === 'accepted' ? 'badge-accepted' : 'badge-delivered')}">
                  ${o.status}
                </span>
                <span style="font-weight: 800;">₹${Number(o.total_amount).toFixed(2)}</span>
              </div>
            </div>
          `).join("");
        }
      }
    }
  } catch (err) {}
}

async function loadDemandInsights() {
  if (!currentShop) return;
  const container = document.getElementById("demandInsightsContainer");
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/insights/demand?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success && data.insights && data.insights.length > 0) {
      container.innerHTML = data.insights.map(item => `
        <div class="card" style="border-left: 4px solid var(--primary); background: #f8fafc;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <strong style="font-size: 0.95rem;">"${escapeHtml(item.item)}"</strong>
            <span class="badge badge-accent">${item.unmet_searches} searches</span>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-body);">${escapeHtml(item.advice)}</p>
        </div>
      `).join("");
    } else {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;">No missed searches logged yet.</div>`;
    }
  } catch (err) {}
}

// =========================================================================
// 7. COUNTER SCAN & BILLING (POS DUAL SESSIONS)
// =========================================================================

function setupPosBilling() {
  renderPosBillTable();
  const inp = document.getElementById("posBarcodeInput");
  if (inp) inp.focus();
}

function switchBillingTab(tab) {
  activeBillingTab = tab;
  document.getElementById("posTab1Btn").className = tab === "tab_1" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm";
  document.getElementById("posTab2Btn").className = tab === "tab_2" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm";
  renderPosBillTable();
}

function renderPosBillTable() {
  const session = billingSessions[activeBillingTab];
  const tbody = document.getElementById("posBillTableBody");
  const totalDisplay = document.getElementById("posTotalDisplay");
  if (!tbody || !totalDisplay) return;

  if (session.items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No items added to current session. Scan a barcode above.</td></tr>`;
    totalDisplay.textContent = "₹0.00";
    return;
  }

  tbody.innerHTML = session.items.map(it => `
    <tr>
      <td><strong>${escapeHtml(it.name)}</strong></td>
      <td>${it.quantity}</td>
      <td>₹${it.price.toFixed(2)}</td>
      <td style="font-weight: 700;">₹${(it.price * it.quantity).toFixed(2)}</td>
      <td><button class="btn btn-outline-danger btn-sm" onclick="removePosItem(${it.product_id})" style="padding: 0.15rem 0.4rem;">✕</button></td>
    </tr>
  `).join("");

  const total = session.items.reduce((s, it) => s + (it.price * it.quantity), 0);
  session.total = total;
  totalDisplay.textContent = `₹${total.toFixed(2)}`;
}

function handleBarcodeScan(e) {
  e.preventDefault();
  const input = document.getElementById("posBarcodeInput");
  const barcode = input.value.trim();
  if (!barcode) return;

  const product = shopCatalog.find(p => p.barcode === barcode);
  if (product) {
    addPosItem(product);
    input.value = "";
    input.focus();
  } else {
    showToast(`No item found with barcode "${barcode}"`, "warning");
  }
}

function addPosItem(product) {
  const session = billingSessions[activeBillingTab];
  const existing = session.items.find(it => it.product_id === product.id);
  if (existing) {
    existing.quantity += 1;
  } else {
    session.items.push({
      product_id: product.id,
      name: product.name,
      price: product.price,
      quantity: 1
    });
  }
  renderPosBillTable();
}

function removePosItem(prodId) {
  const session = billingSessions[activeBillingTab];
  session.items = session.items.filter(it => it.product_id !== prodId);
  renderPosBillTable();
}

function clearCurrentBill() {
  billingSessions[activeBillingTab].items = [];
  billingSessions[activeBillingTab].total = 0;
  renderPosBillTable();
}

async function completePosCheckout(paymentMethod) {
  const session = billingSessions[activeBillingTab];
  if (session.items.length === 0) {
    showToast("Bill is empty. Scan items first.", "warning");
    return;
  }
  if (!currentShop) return;

  const payload = {
    session_tab: activeBillingTab,
    payment_method: paymentMethod,
    items: session.items.map(it => ({ product_id: it.product_id, quantity: it.quantity }))
  };

  try {
    const res = await fetch(`${API_BASE}/billing/checkout?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`Bill paid: ₹${session.total.toFixed(2)} via ${paymentMethod.toUpperCase()}`, "success");
      clearCurrentBill();
      loadShopStock();
      loadShopDashboardMetrics();
    } else {
      showToast(data.detail || "Checkout failed", "danger");
    }
  } catch (err) {
    showToast("Error processing bill", "danger");
  }
}

function renderPosQuickItems(products) {
  const container = document.getElementById("posQuickItemsGrid");
  if (!container) return;

  container.innerHTML = products.slice(0, 10).map(p => `
    <div class="card" style="padding: 0.65rem; cursor: pointer;" onclick="addPosItem({id: ${p.id}, name: '${escapeHtml(p.name)}', price: ${p.price}})">
      <div style="font-weight: 700; font-size: 0.85rem;">${escapeHtml(p.name)}</div>
      <div style="font-size: 0.8rem; color: var(--primary); font-weight: 800;">₹${Number(p.price).toFixed(2)}</div>
    </div>
  `).join("");
}

// =========================================================================
// 8. STORE PROFILE MODAL & 1 KM CLUSTER
// =========================================================================

async function openShopProfileModal() {
  if (!currentShop) return;

  try {
    const res = await fetch(`${API_BASE}/auth/shopkeeper/profile?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success && data.shop) {
      const s = data.shop;
      document.getElementById("shopProfName").value = s.name || "";
      document.getElementById("shopProfOwner").value = s.owner_name || "";
      document.getElementById("shopProfPhone").value = s.phone || "";
      document.getElementById("shopProfEmail").value = s.email || "";
      document.getElementById("shopProfAddress").value = s.address || "";
      document.getElementById("shopProfCategory").value = s.category || "";
      document.getElementById("shopProfHours").value = s.opening_hours || "";
      document.getElementById("shopProfPhoto").value = s.photo_url || "";
      document.getElementById("shopProfIsOpen").checked = s.is_open !== false;

      showModal("shopProfileModal");
    }
  } catch (err) {}
}

async function handleSaveShopProfile(e) {
  e.preventDefault();
  if (!currentShop) return;

  const payload = {
    shop_name: document.getElementById("shopProfName").value.trim(),
    owner_name: document.getElementById("shopProfOwner").value.trim(),
    phone: document.getElementById("shopProfPhone").value.trim(),
    email: document.getElementById("shopProfEmail").value.trim() || null,
    address: document.getElementById("shopProfAddress").value.trim(),
    category: document.getElementById("shopProfCategory").value.trim(),
    opening_hours: document.getElementById("shopProfHours").value.trim(),
    photo_url: document.getElementById("shopProfPhoto").value.trim() || null,
    is_open: document.getElementById("shopProfIsOpen").checked
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopkeeper/profile?shop_id=${currentShop.shop_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success && data.shop) {
      currentShop.name = data.shop.name;
      currentShop.owner_name = data.shop.owner_name;
      currentShop.phone = data.shop.phone;
      currentShop.email = data.shop.email;
      currentShop.address = data.shop.address;
      currentShop.is_open = data.shop.is_open;

      currentShopkeeper.shop_name = data.shop.name;
      currentShopkeeper.name = data.shop.owner_name;
      currentShopkeeper.is_open = data.shop.is_open;
      localStorage.setItem("agorazure_shopkeeper", JSON.stringify(currentShopkeeper));

      renderShopkeeperHeader();
      hideModal("shopProfileModal");
      showToast("Store profile updated successfully!", "success");
    } else {
      showToast(data.detail || "Failed to update profile", "danger");
    }
  } catch (err) {
    showToast("Error updating store profile", "danger");
  }
}

async function loadSharedDelivery() {
  if (!currentShop) return;
  const area = document.getElementById("clusterContentArea");
  if (!area) return;

  try {
    const res = await fetch(`${API_BASE}/delivery/cluster-info?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success) {
      const d = data.delivery_details;
      area.innerHTML = `
        <div class="card" style="border-left: 4px solid var(--accent); max-width: 650px;">
          <div style="font-size: 1.15rem; font-weight: 800; margin-bottom: 0.5rem;">
            Cluster: ${escapeHtml(d.cluster_name)}
          </div>
          <div style="font-size: 0.9rem; color: var(--text-body); line-height: 1.6;">
            Dedicated Partner: <strong>${escapeHtml(d.delivery_person_name || 'Rider Assigned')}</strong> ${d.delivery_person_phone ? `(${d.delivery_person_phone})` : ''}<br>
            Total Monthly Partner Salary: <strong>₹${Number(d.total_monthly_salary).toLocaleString()}</strong><br>
            Nearby Shops Sharing Rider: <strong>${d.total_shops_sharing} shops</strong><br>
            <div style="margin-top: 0.6rem; padding: 0.6rem; background: var(--bg-subtle); border-radius: var(--radius-sm); font-weight: 700; color: var(--primary);">
              Your Store's Monthly Share: ₹${Number(d.salary_split_per_shop).toFixed(2)} / month
            </div>
          </div>
        </div>
      `;
    }
  } catch (err) {}
}

// =========================================================================
// 9. MODALS & UTILITIES
// =========================================================================

function showModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add("active");
}

function hideModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("active");
}

function showToast(msg, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const icons = {
    success: "✓",
    danger: "✕",
    warning: "⚠️",
    info: "ℹ️"
  };

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${escapeHtml(msg)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    toast.style.transition = "all 0.2s ease";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
