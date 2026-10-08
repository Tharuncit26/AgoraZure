/**
 * AgoraZure Shopkeeper Portal Logic
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

// State
let currentShop = null;
let currentTab = "tab_1";
let bills = {
  tab_1: [],
  tab_2: []
};
let shopCatalog = [];

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initAuth();
  setupEventListeners();
});

// =========================================================================
// 1. AUTHENTICATION & DEMO ACCOUNTS
// =========================================================================

function initAuth() {
  const saved = localStorage.getItem("agorazure_shopkeeper");
  if (saved) {
    try {
      currentShop = JSON.parse(saved);
      renderShopHeader();
      loadAllShopData();
      return;
    } catch (e) {
      localStorage.removeItem("agorazure_shopkeeper");
    }
  }
  showModal("authModal");
}

function renderShopHeader() {
  if (!currentShop) return;
  const nameEl = document.getElementById("shopNameDisplay");
  if (nameEl) nameEl.textContent = currentShop.shop_name || "";
  const ownerEl = document.getElementById("shopOwnerDisplay");
  if (ownerEl) ownerEl.textContent = currentShop.name || "";
  const addrEl = document.getElementById("shopAddressDisplay");
  if (addrEl) addrEl.textContent = currentShop.address || "";
  const authBar = document.getElementById("shopAuthBar");
  if (authBar) authBar.style.display = "flex";
  hideModal("authModal");
}

async function quickLogin(phone, password) {
  let res, data;
  try {
    res = await fetch(`${API_BASE}/auth/shopkeeper/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, password })
    });
  } catch (netErr) {
    console.error("Shopkeeper login network error:", netErr);
    showToast("Network error: Unable to connect to server. Please check backend connection.", "danger");
    return;
  }

  try {
    data = await res.json();
  } catch (parseErr) {
    console.error("Failed to parse login response:", parseErr);
    showToast("Server error: Invalid response from server.", "danger");
    return;
  }

  if (res.ok && data.success) {
    try {
      currentShop = data.shopkeeper;
      localStorage.setItem("agorazure_shopkeeper", JSON.stringify(currentShop));
      renderShopHeader();
      loadAllShopData();
      showToast(`Logged in as ${currentShop.shop_name}`, "success");
    } catch (uiErr) {
      console.error("Error setting up shop UI after login:", uiErr);
    }
  } else {
    showToast(data.detail || "Invalid phone or password. Login failed.", "danger");
  }
}

async function handleRegisterShop(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    shop_name: form.shop_name.value.trim(),
    owner_name: form.owner_name.value.trim(),
    phone: form.phone.value.trim(),
    password: form.password.value.trim(),
    address: form.address.value.trim(),
    latitude: parseFloat(form.latitude.value),
    longitude: parseFloat(form.longitude.value)
  };

  let res, data;
  try {
    res = await fetch(`${API_BASE}/auth/shopkeeper/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (netErr) {
    console.error("Shop registration network error:", netErr);
    showToast("Network error: Unable to connect to server. Please try again.", "danger");
    return;
  }

  try {
    data = await res.json();
  } catch (parseErr) {
    showToast("Server error: Invalid response from server.", "danger");
    return;
  }

  if (res.ok && data.success) {
    showToast("Shop registered successfully! Logging in...", "success");
    await quickLogin(payload.phone, payload.password);
  } else {
    showToast(data.detail || "Registration failed", "danger");
  }
}

function logout() {
  localStorage.removeItem("agorazure_shopkeeper");
  currentShop = null;
  location.reload();
}

// =========================================================================
// 2. DATA LOADING
// =========================================================================

function loadAllShopData() {
  if (!currentShop || !currentShop.shop_id) return;
  loadStock();
  loadAlerts();
  loadDemandInsights();
  loadOrders();
  loadSharedDelivery();
  loadMarketing();
  focusScanner();
}

// Switch navigation tabs
function switchNavTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach(panel => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });

  if (tabName === "billing") {
    focusScanner();
  }
}

// =========================================================================
// 3. SCAN AND BILL (POS ENGINE)
// =========================================================================

function switchBillingSession(tab) {
  currentTab = tab;
  document.getElementById("btnBillTab1").classList.toggle("active", tab === "tab_1");
  document.getElementById("btnBillTab2").classList.toggle("active", tab === "tab_2");
  renderBillingTable();
  focusScanner();
}

function focusScanner() {
  const input = document.getElementById("barcodeScannerInput");
  if (input) {
    input.focus();
  }
}

async function handleBarcodeScan(barcode) {
  if (!barcode || !currentShop) return;
  const barcodeClean = barcode.trim();
  if (!barcodeClean) return;

  try {
    const res = await fetch(`${API_BASE}/billing/scan?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ barcode: barcodeClean, session_tab: currentTab })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      const prod = data.product;
      const currentItems = bills[currentTab];
      const existing = currentItems.find(it => it.product_id === prod.id);

      if (existing) {
        if (existing.quantity + 1 > prod.available_stock) {
          showToast(`Cannot add more. Only ${prod.available_stock} in stock!`, "warning");
          return;
        }
        existing.quantity += 1;
        showToast(`Increased quantity for ${prod.name} (${existing.quantity})`, "success");
      } else {
        if (prod.available_stock <= 0) {
          showToast(`${prod.name} is Out of Stock!`, "danger");
          return;
        }
        currentItems.push({
          product_id: prod.id,
          name: prod.name,
          barcode: prod.barcode,
          price: prod.price,
          quantity: 1,
          available_stock: prod.available_stock
        });
        showToast(`Added ${prod.name} to Bill`, "success");
      }
      renderBillingTable();
    } else {
      showToast(data.detail || "Barcode not found in catalog", "danger");
    }
  } catch (err) {
    showToast("Error scanning item", "danger");
  } finally {
    const input = document.getElementById("barcodeScannerInput");
    if (input) {
      input.value = "";
      input.focus();
    }
  }
}

function updateItemQuantity(prodId, delta) {
  const currentItems = bills[currentTab];
  const item = currentItems.find(it => it.product_id === prodId);
  if (!item) return;

  const newQty = item.quantity + delta;
  if (newQty <= 0) {
    removeItemFromBill(prodId);
    return;
  }
  if (newQty > item.available_stock) {
    showToast(`Only ${item.available_stock} units available in stock.`, "warning");
    return;
  }
  item.quantity = newQty;
  renderBillingTable();
}

function removeItemFromBill(prodId) {
  bills[currentTab] = bills[currentTab].filter(it => it.product_id !== prodId);
  renderBillingTable();
}

function clearCurrentBill() {
  bills[currentTab] = [];
  renderBillingTable();
  focusScanner();
}

function renderBillingTable() {
  const currentItems = bills[currentTab];
  const tbody = document.getElementById("billingItemsTbody");
  const countBadge = document.getElementById(`countBadge_${currentTab}`);
  
  if (countBadge) {
    countBadge.textContent = currentItems.reduce((acc, it) => acc + it.quantity, 0);
  }

  if (currentItems.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="empty-state" style="padding: 2rem;">
          <div class="empty-icon">🛒</div>
          <p>Scan barcode with scanner or enter manually above to start billing</p>
        </td>
      </tr>
    `;
    updateBillTotals(0);
    return;
  }

  let total = 0;
  tbody.innerHTML = currentItems.map((it, idx) => {
    const lineTotal = it.price * it.quantity;
    total += lineTotal;
    return `
      <tr>
        <td>
          <div style="font-weight: 600;">${it.name}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${it.barcode}</div>
        </td>
        <td>₹${it.price.toFixed(2)}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.4rem;">
            <button class="btn btn-secondary btn-sm" onclick="updateItemQuantity(${it.product_id}, -1)">-</button>
            <span style="font-weight: 700; min-width: 20px; text-align: center;">${it.quantity}</span>
            <button class="btn btn-secondary btn-sm" onclick="updateItemQuantity(${it.product_id}, 1)">+</button>
          </div>
        </td>
        <td style="font-weight: 700;">₹${lineTotal.toFixed(2)}</td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="removeItemFromBill(${it.product_id})" title="Remove item">×</button>
        </td>
      </tr>
    `;
  }).join("");

  updateBillTotals(total);
}

function updateBillTotals(total) {
  const subtotalEl = document.getElementById("billSubtotal");
  if (subtotalEl) subtotalEl.textContent = `₹${total.toFixed(2)}`;
  const grandTotalEl = document.getElementById("billGrandTotal");
  if (grandTotalEl) grandTotalEl.textContent = `₹${total.toFixed(2)}`;
  const payBtns = document.querySelectorAll(".btn-pay-action");
  payBtns.forEach(btn => btn.disabled = total <= 0);
}

// Payment: Cash
async function handlePayCash() {
  const currentItems = bills[currentTab];
  if (currentItems.length === 0) return;

  const payload = {
    session_tab: currentTab,
    payment_method: "cash",
    items: currentItems.map(it => ({ product_id: it.product_id, quantity: it.quantity }))
  };

  try {
    const res = await fetch(`${API_BASE}/billing/confirm?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast("Cash Bill finalized! Stock deducted (FEFO).", "success");
      clearCurrentBill();
      loadStock();
      loadAlerts();
      showReceiptModal(data.receipt);
    } else {
      showToast(data.detail || "Payment failed", "danger");
    }
  } catch (err) {
    showToast("Error completing bill", "danger");
  }
}

// Payment: UPI QR Modal
async function handleShowUpiQr() {
  const currentItems = bills[currentTab];
  if (currentItems.length === 0) return;
  const total = currentItems.reduce((acc, it) => acc + (it.price * it.quantity), 0);

  try {
    const res = await fetch(`${API_BASE}/billing/upi-qr?amount=${total}&shop_id=${currentShop.shop_id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("upiQrImage").src = data.qr_base64;
      document.getElementById("upiQrAmount").textContent = `₹${data.amount.toFixed(2)}`;
      document.getElementById("upiQrMerchant").textContent = data.merchant;
      document.getElementById("upiQrId").textContent = data.upi_id;
      showModal("upiQrModal");
    } else {
      showToast("Could not generate UPI QR", "danger");
    }
  } catch (err) {
    showToast("Network error generating UPI QR", "danger");
  }
}

// Shopkeeper confirms UPI Payment received
async function handleConfirmUpiReceived() {
  const currentItems = bills[currentTab];
  if (currentItems.length === 0) return;

  const payload = {
    session_tab: currentTab,
    payment_method: "upi",
    items: currentItems.map(it => ({ product_id: it.product_id, quantity: it.quantity }))
  };

  try {
    const res = await fetch(`${API_BASE}/billing/confirm?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok && data.success) {
      hideModal("upiQrModal");
      showToast("UPI Payment confirmed! Stock reduced via FEFO.", "success");
      clearCurrentBill();
      loadStock();
      loadAlerts();
      showReceiptModal(data.receipt);
    } else {
      showToast(data.detail || "Error confirming payment", "danger");
    }
  } catch (err) {
    showToast("Failed to finalize bill", "danger");
  }
}

function showReceiptModal(receipt) {
  document.getElementById("receiptShopName").textContent = receipt.shop.name;
  document.getElementById("receiptShopAddress").textContent = receipt.shop.address;
  document.getElementById("receiptShopPhone").textContent = `Ph: ${receipt.shop.phone}`;
  document.getElementById("receiptNumber").textContent = receipt.bill_number;
  document.getElementById("receiptDate").textContent = receipt.timestamp;
  document.getElementById("receiptPayMethod").textContent = receipt.payment_method;

  const tbody = document.getElementById("receiptItemsTbody");
  tbody.innerHTML = receipt.items.map(it => `
    <div class="receipt-row">
      <div>
        <strong>${it.product_name}</strong>
        <div style="font-size: 0.72rem; color: #475569;">
          ${it.quantity} x ₹${it.unit_price.toFixed(2)} ${it.batches_used ? `[${it.batches_used.join(', ')}]` : ''}
        </div>
      </div>
      <div>₹${it.subtotal.toFixed(2)}</div>
    </div>
  `).join("");

  document.getElementById("receiptTotal").textContent = `₹${receipt.total_amount.toFixed(2)}`;
  showModal("receiptModal");
}

function printReceipt() {
  window.print();
}

// =========================================================================
// 4. STOCK & BATCH MANAGEMENT
// =========================================================================

async function loadStock() {
  if (!currentShop) return;
  try {
    const res = await fetch(`${API_BASE}/stock/products?shop_id=${currentShop.shop_id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      shopCatalog = data.products;
      renderStockTable(shopCatalog);
      populateShrinkageProductDropdown(shopCatalog);
    }
  } catch (err) {
    console.error("Error loading stock:", err);
  }
}

function renderStockTable(products) {
  const tbody = document.getElementById("stockTableBody");
  if (!products || products.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No products registered yet. Click 'Add Product' to start.</td></tr>`;
    return;
  }

  tbody.innerHTML = products.map(p => {
    const isLow = p.is_low_stock;
    const badgeClass = p.total_quantity === 0 ? "badge-danger" : (isLow ? "badge-warning" : "badge-success");
    const stockStatus = p.total_quantity === 0 ? "OUT OF STOCK" : (isLow ? "LOW STOCK" : "IN STOCK");

    return `
      <tr>
        <td>
          <div style="font-weight: 700;">${p.name}</div>
          <span class="badge badge-neutral">${p.category}</span>
        </td>
        <td><code>${p.barcode}</code></td>
        <td style="font-weight: 700;">₹${p.price.toFixed(2)}</td>
        <td>
          <span style="font-size: 1.1rem; font-weight: 800;">${p.total_quantity}</span>
          <span class="badge ${badgeClass}" style="margin-left: 0.4rem;">${stockStatus}</span>
        </td>
        <td>${p.low_stock_threshold}</td>
        <td>
          <span style="font-size: 0.85rem; color: #475569;">${p.earliest_expiry}</span>
          <div style="font-size: 0.72rem; color: var(--text-muted);">${p.batches.length} active batch(es)</div>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openAddBatchModal('${p.barcode}', '${p.name.replace(/'/g, "\\'")}')">
            + Batch
          </button>
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

async function handleAddProduct(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    name: form.name.value.trim(),
    barcode: form.barcode.value.trim(),
    price: parseFloat(form.price.value),
    category: form.category.value.trim(),
    low_stock_threshold: parseInt(form.low_stock_threshold.value) || 5,
    initial_quantity: parseInt(form.initial_quantity.value) || 0,
    expiry_date: form.expiry_date.value || "2026-12-31"
  };

  try {
    const res = await fetch(`${API_BASE}/stock/product?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, "success");
      hideModal("addProductModal");
      form.reset();
      loadStock();
      loadAlerts();
    } else {
      showToast(data.detail || "Failed to add product", "danger");
    }
  } catch (err) {
    showToast("Error adding product", "danger");
  }
}

function openAddBatchModal(barcode = "", productName = "") {
  const form = document.getElementById("addBatchForm");
  form.barcode.value = barcode;
  const nameLabel = document.getElementById("batchModalProductName");
  if (nameLabel) {
    nameLabel.textContent = productName ? `for ${productName}` : "";
  }
  showModal("addBatchModal");
}

async function handleAddBatch(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    barcode: form.barcode.value.trim(),
    quantity: parseInt(form.quantity.value),
    expiry_date: form.expiry_date.value.trim(),
    batch_number: form.batch_number.value.trim() || undefined
  };

  try {
    const res = await fetch(`${API_BASE}/stock/batch?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, "success");
      hideModal("addBatchModal");
      form.reset();
      loadStock();
      loadAlerts();
    } else {
      showToast(data.detail || "Failed to add batch", "danger");
    }
  } catch (err) {
    showToast("Error adding batch", "danger");
  }
}

// =========================================================================
// 5. ALERTS (Low Stock, Shrinkage, Expiry)
// =========================================================================

async function loadAlerts() {
  if (!currentShop) return;
  loadLowStockAlerts();
  loadExpiryAlerts();
}

async function loadLowStockAlerts() {
  try {
    const res = await fetch(`${API_BASE}/alerts/low-stock?shop_id=${currentShop.shop_id}`);
    const data = await res.json();
    const container = document.getElementById("lowStockAlertsList");
    
    if (res.ok && data.success) {
      document.getElementById("lowStockCountBadge").textContent = data.count;
      if (data.count === 0) {
        container.innerHTML = `<div class="empty-state" style="padding: 1rem;">✅ All items are well-stocked above thresholds!</div>`;
        return;
      }
      container.innerHTML = data.alerts.map(a => `
        <div class="insight-card ${a.severity === 'CRITICAL' ? 'urgency-high' : 'urgency-medium'}">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>${a.name}</strong>
            <span class="badge ${a.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}">${a.severity}</span>
          </div>
          <p style="font-size: 0.85rem; margin-top: 0.3rem;">${a.message}</p>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading low stock alerts:", err);
  }
}

async function loadExpiryAlerts() {
  try {
    const res = await fetch(`${API_BASE}/alerts/expiry?shop_id=${currentShop.shop_id}&days_threshold=30`);
    const data = await res.json();
    const container = document.getElementById("expiryAlertsList");
    
    if (res.ok && data.success) {
      document.getElementById("expiryCountBadge").textContent = data.count;
      if (data.count === 0) {
        container.innerHTML = `<div class="empty-state" style="padding: 1rem;">✅ No batches expiring in the next 30 days.</div>`;
        return;
      }
      container.innerHTML = data.alerts.map(a => `
        <div class="insight-card ${a.severity === 'EXPIRED' ? 'urgency-high' : (a.severity === 'CRITICAL' ? 'urgency-high' : 'urgency-medium')}">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>${a.product_name} (Batch: ${a.batch_number})</strong>
            <span class="badge ${a.severity === 'EXPIRED' ? 'badge-danger' : 'badge-warning'}">
              ${a.is_expired ? 'EXPIRED' : `${a.days_left}d left`}
            </span>
          </div>
          <p style="font-size: 0.82rem; color: #475569; margin: 0.25rem 0;">Qty: ${a.quantity} units | Expiry: ${a.expiry_date}</p>
          <p style="font-size: 0.82rem; font-weight: 600; color: var(--primary);">${a.fefo_advice}</p>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading expiry alerts:", err);
  }
}

function populateShrinkageProductDropdown(products) {
  const sel = document.getElementById("shrinkageProductSelect");
  if (!sel) return;
  sel.innerHTML = `<option value="">-- Select Product to Count --</option>` +
    products.map(p => `<option value="${p.id}">${p.name} (Recorded Stock: ${p.total_quantity})</option>`).join("");
}

async function handleShrinkageCheck(e) {
  e.preventDefault();
  const form = e.target;
  const prodId = parseInt(form.product_id.value);
  const counted = parseInt(form.counted_quantity.value);
  if (!prodId) {
    showToast("Please select a product", "warning");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/alerts/shrinkage-check?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: prodId, counted_quantity: counted })
    });
    const data = await res.json();
    const resultBox = document.getElementById("shrinkageResultBox");

    if (res.ok && data.success) {
      resultBox.style.display = "block";
      const isShrink = data.status === "SHRINKAGE_DETECTED";
      const isSurplus = data.status === "SURPLUS_DETECTED";

      resultBox.className = `insight-card ${isShrink ? 'urgency-high' : (isSurplus ? 'urgency-medium' : 'urgency-low')}`;
      resultBox.innerHTML = `
        <div style="font-weight: 700; margin-bottom: 0.4rem;">
          ${isShrink ? '⚠️ Shrinkage Discrepancy Found' : (isSurplus ? 'ℹ️ Surplus Detected' : '✅ Exact Match')}
        </div>
        <p style="font-size: 0.9rem;">${data.message}</p>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.4rem;">
          Expected: <strong>${data.expected_quantity}</strong> | Physically Counted: <strong>${data.counted_quantity}</strong>
        </div>
      `;
    } else {
      showToast(data.detail || "Shrinkage check failed", "danger");
    }
  } catch (err) {
    showToast("Error checking shrinkage", "danger");
  }
}

// =========================================================================
// 6. UNMET-DEMAND INSIGHTS (Azure AI Stocking Advice)
// =========================================================================

async function loadDemandInsights() {
  if (!currentShop) return;
  const container = document.getElementById("demandInsightsList");
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">🧠 Analyzing customer demand & missed searches...</div>`;

  try {
    const res = await fetch(`${API_BASE}/insights/stocking-advice?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success) {
      document.getElementById("missedSearchCountTotal").textContent = data.total_missed_searches;
      document.getElementById("unmetDemandItemsCount").textContent = data.unmet_demand_items_count;

      if (!data.stocking_advice || data.stocking_advice.length === 0) {
        container.innerHTML = `<div class="empty-state">No unmet demand recorded yet. As shoppers search for unstocked items, AI stocking recommendations will appear here.</div>`;
        return;
      }

      container.innerHTML = data.stocking_advice.map(adv => `
        <div class="insight-card urgency-${adv.urgency ? adv.urgency.toLowerCase() : 'medium'}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
            <div>
              <strong style="font-size: 1.05rem;">${adv.term}</strong>
              <span style="font-size: 0.78rem; color: var(--text-muted); margin-left: 0.5rem;">(${adv.count} shoppers searched)</span>
            </div>
            <span class="badge ${adv.urgency === 'High' ? 'badge-danger' : 'badge-warning'}">${adv.urgency} Urgency</span>
          </div>
          <p style="font-size: 0.92rem; color: #1e293b; line-height: 1.45;">${adv.advice}</p>
        </div>
      `).join("");
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading demand insights.</div>`;
  }
}

// =========================================================================
// 7. ONLINE ORDERS MANAGEMENT
// =========================================================================

async function loadOrders(filterStatus = "") {
  if (!currentShop) return;
  const container = document.getElementById("ordersListContainer");
  const url = filterStatus 
    ? `${API_BASE}/orders/shopkeeper/list?shop_id=${currentShop.shop_id}&status_filter=${filterStatus}`
    : `${API_BASE}/orders/shopkeeper/list?shop_id=${currentShop.shop_id}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (res.ok && data.success) {
      document.getElementById("ordersCountBadge").textContent = data.count;
      if (data.orders.length === 0) {
        container.innerHTML = `<div class="empty-state">No orders matching this filter.</div>`;
        return;
      }

      container.innerHTML = data.orders.map(o => {
        const statusColors = {
          pending: "badge-warning",
          accepted: "badge-primary",
          ready: "badge-primary",
          out_for_delivery: "badge-warning",
          picked_up: "badge-success",
          completed: "badge-success"
        };
        const badgeColor = statusColors[o.status] || "badge-neutral";

        return `
          <div class="card" style="margin-bottom: 1rem;">
            <div class="card-header" style="margin-bottom: 0.6rem; padding-bottom: 0.5rem;">
              <div>
                <strong>${o.order_number}</strong>
                <span class="badge ${badgeColor}" style="margin-left: 0.4rem;">${o.status.replace(/_/g, ' ')}</span>
              </div>
              <div style="font-weight: 800; font-size: 1.1rem; color: var(--primary);">₹${o.total_amount.toFixed(2)}</div>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.6rem;">
              <div>Customer: <strong>${o.shopper.name}</strong> (${o.shopper.phone})</div>
              <div>Collect: <strong>${o.collect_option === 'home_delivery' ? '🛵 Home Delivery' : '🏬 Pickup'}</strong></div>
            </div>

            <div style="background: #f8fafc; padding: 0.6rem; border-radius: var(--radius-sm); font-size: 0.85rem; margin-bottom: 0.8rem;">
              ${o.items.map(it => `<div>• ${it.product_name} x ${it.quantity} (₹${it.subtotal.toFixed(2)})</div>`).join("")}
            </div>

            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
              ${o.status === 'pending' ? `
                <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${o.id}, 'accepted')">Accept Order</button>
              ` : ''}
              ${o.status === 'accepted' ? `
                <button class="btn btn-accent btn-sm" onclick="updateOrderStatus(${o.id}, 'ready')">Mark Ready</button>
              ` : ''}
              ${o.status === 'ready' && o.collect_option === 'home_delivery' ? `
                <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${o.id}, 'out_for_delivery')">Out for Delivery</button>
              ` : ''}
              ${o.status === 'ready' && o.collect_option === 'pickup' ? `
                <button class="btn btn-accent btn-sm" onclick="updateOrderStatus(${o.id}, 'completed')">Customer Picked Up</button>
              ` : ''}
              ${o.status === 'out_for_delivery' ? `
                <button class="btn btn-accent btn-sm" onclick="updateOrderStatus(${o.id}, 'completed')">Delivered</button>
              ` : ''}
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Error loading orders:", err);
  }
}

async function updateOrderStatus(orderId, newStatus) {
  try {
    const res = await fetch(`${API_BASE}/orders/status/${orderId}?shop_id=${currentShop.shop_id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, "success");
      loadOrders();
      loadStock();
    } else {
      showToast(data.detail || "Failed to update status", "danger");
    }
  } catch (err) {
    showToast("Error updating order", "danger");
  }
}

// =========================================================================
// 8. SHARED DELIVERY SERVICE (1 KM CLUSTER & SPLIT SALARY)
// =========================================================================

async function loadSharedDelivery() {
  if (!currentShop) return;
  try {
    const res = await fetch(`${API_BASE}/delivery/cluster-info?shop_id=${currentShop.shop_id}`);
    const data = await res.json();

    if (res.ok && data.success) {
      const d = data.delivery_details;
      if (!d.has_cluster) {
        const clusterArea = document.getElementById("clusterContentArea");
        if (clusterArea) {
          clusterArea.innerHTML = `
            <div class="empty-state">
              <p>${d.message}</p>
              <button class="btn btn-primary btn-sm" onclick="recomputeClusters()" style="margin-top: 1rem;">Compute 1 km Clusters</button>
            </div>
          `;
        }
        return;
      }

      const clusterNameEl = document.getElementById("clusterNameDisplay");
      if (clusterNameEl) clusterNameEl.textContent = d.cluster_name;
      const riderNameEl = document.getElementById("sharedRiderName");
      if (riderNameEl) riderNameEl.textContent = d.delivery_person_name;
      const riderPhoneEl = document.getElementById("sharedRiderPhone");
      if (riderPhoneEl) riderPhoneEl.textContent = d.delivery_person_phone || "";
      const totalSalaryEl = document.getElementById("totalRiderSalary");
      if (totalSalaryEl) totalSalaryEl.textContent = `₹${d.total_monthly_salary.toLocaleString()}`;
      const sharingCountEl = document.getElementById("shopsSharingCount");
      if (sharingCountEl) sharingCountEl.textContent = d.total_shops_sharing;
      const salaryShareEl = document.getElementById("thisShopSalaryShare");
      if (salaryShareEl) salaryShareEl.textContent = `₹${d.this_shop_share.toLocaleString()}`;

      const listContainer = document.getElementById("clusterShopsList");
      if (listContainer && d.shops) {
        listContainer.innerHTML = d.shops.map(s => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--surface-border);">
            <div>
              <strong>${s.name}</strong> ${s.is_current_shop ? '<span class="badge badge-primary">THIS SHOP</span>' : ''}
              <div style="font-size: 0.8rem; color: var(--text-muted);">${s.address}</div>
            </div>
            <span style="font-size: 0.85rem; font-weight: 700;">Share: ₹${d.this_shop_share}</span>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Error loading delivery cluster:", err);
  }
}

async function recomputeClusters() {
  try {
    const res = await fetch(`${API_BASE}/delivery/recompute-clusters`, { method: "POST" });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast("Clusters recomputed successfully!", "success");
      loadSharedDelivery();
    }
  } catch (err) {
    showToast("Error recomputing clusters", "danger");
  }
}

// =========================================================================
// 9. MARKETING (Loyalty Points & Seasonal Offers)
// =========================================================================

async function loadMarketing() {
  if (!currentShop) return;
  loadLoyaltySummary();
  loadOffers();
}

async function loadLoyaltySummary() {
  try {
    const res = await fetch(`${API_BASE}/marketing/loyalty-summary?shop_id=${currentShop.shop_id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("loyaltyTotalIssued").textContent = data.total_rewards_issued;
      document.getElementById("loyaltyCustomerCount").textContent = data.total_customers_enrolled;

      const tbody = document.getElementById("loyaltyCustomersTbody");
      if (data.customers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No customer rewards issued yet. Customers earn 1 pt per ₹50 spent.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.customers.map(c => `
        <tr>
          <td><strong>${c.name}</strong></td>
          <td>${c.phone}</td>
          <td><strong style="color: var(--primary);">${c.total_points_earned} pts</strong></td>
          <td>${c.last_active}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading loyalty summary:", err);
  }
}

async function loadOffers() {
  try {
    const res = await fetch(`${API_BASE}/marketing/offers?shop_id=${currentShop.shop_id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      const container = document.getElementById("offersListContainer");
      if (data.offers.length === 0) {
        container.innerHTML = `<div class="empty-state">No seasonal offers active. Click 'Create Offer' to add one.</div>`;
        return;
      }
      container.innerHTML = data.offers.map(o => `
        <div class="insight-card urgency-low" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>${o.title}</strong>
            <span class="badge badge-success" style="margin-left: 0.4rem;">${o.discount_percent}% OFF</span>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
              Product: ${o.product_name} | Valid: ${o.valid_from} to ${o.valid_to}
            </div>
          </div>
          <button class="btn btn-danger btn-sm" onclick="deleteOffer(${o.id})">Delete</button>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading offers:", err);
  }
}

async function handleCreateOffer(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value.trim(),
    discount_percent: parseFloat(form.discount_percent.value),
    product_id: form.product_id.value ? parseInt(form.product_id.value) : null,
    valid_from: form.valid_from.value,
    valid_to: form.valid_to.value
  };

  try {
    const res = await fetch(`${API_BASE}/marketing/offers?shop_id=${currentShop.shop_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, "success");
      hideModal("createOfferModal");
      form.reset();
      loadOffers();
    } else {
      showToast(data.detail || "Failed to create offer", "danger");
    }
  } catch (err) {
    showToast("Error creating offer", "danger");
  }
}

async function deleteOffer(offerId) {
  try {
    const res = await fetch(`${API_BASE}/marketing/offers/${offerId}?shop_id=${currentShop.shop_id}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast("Offer removed", "success");
      loadOffers();
    }
  } catch (err) {
    showToast("Error deleting offer", "danger");
  }
}

// =========================================================================
// 10. MODAL & EVENT LISTENERS
// =========================================================================

function setupEventListeners() {
  // Navigation tab clicks
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchNavTab(btn.dataset.tab));
  });

  // Barcode scanner input (USB / Bluetooth keyboard emulation presses Enter)
  const scannerInput = document.getElementById("barcodeScannerInput");
  if (scannerInput) {
    scannerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleBarcodeScan(scannerInput.value);
      }
    });
  }

  // Stock search input
  const stockSearch = document.getElementById("stockSearchInput");
  if (stockSearch) {
    stockSearch.addEventListener("input", (e) => filterStockTable(e.target.value));
  }

  // Form submit listeners
  const regForm = document.getElementById("registerShopForm");
  if (regForm) regForm.addEventListener("submit", handleRegisterShop);

  const addProdForm = document.getElementById("addProductForm");
  if (addProdForm) addProdForm.addEventListener("submit", handleAddProduct);

  const addBatchForm = document.getElementById("addBatchForm");
  if (addBatchForm) addBatchForm.addEventListener("submit", handleAddBatch);

  const shrinkForm = document.getElementById("shrinkageCheckForm");
  if (shrinkForm) shrinkForm.addEventListener("submit", handleShrinkageCheck);

  const offerForm = document.getElementById("createOfferForm");
  if (offerForm) offerForm.addEventListener("submit", handleCreateOffer);
}

function showModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add("active");
}

function hideModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove("active");
  focusScanner();
}

function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3200);
}
