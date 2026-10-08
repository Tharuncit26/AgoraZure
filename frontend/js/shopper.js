/**
 * AgoraZure Shopper Portal Logic
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

// Shopper State
let currentShopper = null;
let shopperLocation = {
  lat: 12.9720,
  lon: 77.6418,
  address: "Indiranagar, Bengaluru"
};
let cart = []; // [{ product_id, name, price, shop_id, shop_name, quantity, has_shared_delivery }]
let currentOrderReceipt = null;

document.addEventListener("DOMContentLoaded", () => {
  initShopperAuth();
  setupShopperEvents();
  loadUseSoonDeals();
  performSearch(""); // Initial catalog load
});

// =========================================================================
// 1. AUTH & LOCATION
// =========================================================================

function initShopperAuth() {
  const saved = localStorage.getItem("agorazure_shopper");
  if (saved) {
    try {
      currentShopper = JSON.parse(saved);
      shopperLocation.lat = currentShopper.latitude || 12.9720;
      shopperLocation.lon = currentShopper.longitude || 77.6418;
      shopperLocation.address = currentShopper.address || "Indiranagar, Bengaluru";
      renderShopperHeader();
      loadNotifications();
      loadLoyaltyPoints();
      loadOrderHistory();
      return;
    } catch (e) {
      localStorage.removeItem("agorazure_shopper");
    }
  }
  showModal("shopperAuthModal");
}

function renderShopperHeader() {
  if (!currentShopper) return;
  const nameEl = document.getElementById("shopperNameDisplay");
  if (nameEl) nameEl.textContent = currentShopper.name || "";
  const locEl = document.getElementById("shopperLocationDisplay");
  if (locEl) locEl.textContent = shopperLocation.address || "";
  const authBar = document.getElementById("shopperAuthBar");
  if (authBar) authBar.style.display = "flex";
  hideModal("shopperAuthModal");
}

async function quickShopperLogin(phone, password) {
  let res, data;
  try {
    res = await fetch(`${API_BASE}/auth/shopper/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, password })
    });
  } catch (netErr) {
    console.error("Shopper login network error:", netErr);
    showToast("Network error: Unable to connect to server. Please check backend connection.", "danger");
    return;
  }

  try {
    data = await res.json();
  } catch (parseErr) {
    console.error("Failed to parse shopper login response:", parseErr);
    showToast("Server error: Invalid response from server.", "danger");
    return;
  }

  if (res.ok && data.success) {
    try {
      currentShopper = data.shopper;
      localStorage.setItem("agorazure_shopper", JSON.stringify(currentShopper));
      shopperLocation.lat = currentShopper.latitude || 12.9720;
      shopperLocation.lon = currentShopper.longitude || 77.6418;
      shopperLocation.address = currentShopper.address || "Indiranagar, Bengaluru";
      renderShopperHeader();
      loadNotifications();
      loadLoyaltyPoints();
      loadOrderHistory();
      performSearch("");
      loadUseSoonDeals();
      showToast(`Welcome back, ${currentShopper.name}!`, "success");
    } catch (uiErr) {
      console.error("Error setting up shopper UI after login:", uiErr);
    }
  } else {
    showToast(data.detail || "Invalid phone or password. Login failed.", "danger");
  }
}

async function handleRegisterShopper(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    name: form.name.value.trim(),
    phone: form.phone.value.trim(),
    password: form.password.value.trim(),
    address: form.address.value.trim(),
    latitude: parseFloat(form.latitude.value),
    longitude: parseFloat(form.longitude.value)
  };

  let res, data;
  try {
    res = await fetch(`${API_BASE}/auth/shopper/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (netErr) {
    console.error("Shopper register network error:", netErr);
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
    showToast("Shopper registered successfully! Logging in...", "success");
    await quickShopperLogin(payload.phone, payload.password);
  } else {
    showToast(data.detail || "Registration failed", "danger");
  }
}

function shopperLogout() {
  localStorage.removeItem("agorazure_shopper");
  currentShopper = null;
  location.reload();
}

// =========================================================================
// 2. PRODUCT SEARCH WITH LIVE STOCK & DISTANCE (Haversine)
// =========================================================================

async function performSearch(query = "") {
  const container = document.getElementById("searchResultsContainer");
  const substitutesContainer = document.getElementById("substitutesContainer");
  substitutesContainer.style.display = "none";

  const sId = (currentShopper && currentShopper.id) ? currentShopper.id : "";
  const queryParam = sId ? `&shopper_id=${sId}` : "";
  const url = `${API_BASE}/shopper-portal/search?q=${encodeURIComponent(query)}&shopper_lat=${shopperLocation.lat}&shopper_lon=${shopperLocation.lon}${queryParam}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (res.ok && data.success) {
      // 1. Handle Unmet Demand / Missed Search & Smart AI Substitutes
      if (data.is_missed_search) {
        showToast("🔍 Item not in stock. Request logged in Unmet-Demand Loop!", "warning");
        if (data.smart_substitutes && data.smart_substitutes.length > 0) {
          renderSmartSubstitutes(data.query, data.smart_substitutes);
        }
      }

      // 2. Render Search Results
      if (data.products.length === 0) {
        container.innerHTML = `
          <div class="empty-state" style="grid-column: 1 / -1;">
            <div class="empty-icon">🔎</div>
            <h3>No matching products in nearby shops</h3>
            <p>Your search for "<strong>${data.query}</strong>" has been logged. When any nearby shopkeeper stocks this item, you will be notified!</p>
          </div>
        `;
        return;
      }

      container.innerHTML = data.products.map(p => {
        const inStock = p.live_stock > 0;
        return `
          <div class="product-card">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
                <span class="badge badge-neutral">${p.category}</span>
                <span style="font-size: 0.78rem; font-weight: 700; color: var(--primary);">
                  📍 ${p.distance_km} km away
                </span>
              </div>
              <h3 style="font-size: 1.05rem; margin-bottom: 0.25rem;">${p.name}</h3>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                Sold by <strong>${p.shop_name}</strong>
              </div>
            </div>

            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--surface-border);">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5rem;">
                <div class="product-price">₹${p.price.toFixed(2)}</div>
                <div style="font-size: 0.8rem; font-weight: 600; color: ${inStock ? 'var(--accent)' : 'var(--danger)'};">
                  ${inStock ? `● ${p.live_stock} in stock` : '● Out of stock'}
                </div>
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                <span>${p.has_shared_delivery ? '🛵 Shared Delivery Available' : '🏬 Pickup Only'}</span>
              </div>

              <button 
                class="btn ${inStock ? 'btn-primary' : 'btn-secondary'} btn-sm btn-block" 
                onclick="addToCart(${p.id}, '${p.name.replace(/'/g, "\\'")}', ${p.price}, ${p.shop_id}, '${p.shop_name.replace(/'/g, "\\'")}', ${p.has_shared_delivery})"
                ${!inStock ? 'disabled' : ''}
              >
                ${inStock ? '+ Add to Cart' : 'Unavailable'}
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Search error:", err);
  }
}

// Render AI Smart Substitutes
function renderSmartSubstitutes(missingItem, subs) {
  const container = document.getElementById("substitutesContainer");
  const list = document.getElementById("substitutesList");
  container.style.display = "block";
  document.getElementById("missingItemTitle").textContent = missingItem;

  list.innerHTML = subs.map(s => `
    <div style="background: #ffffff; border: 1px solid #bae6fd; border-radius: var(--radius-sm); padding: 0.85rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
      <div style="flex: 1; min-width: 220px;">
        <div style="font-weight: 700; font-size: 0.95rem; color: var(--secondary);">✨ ${s.product_name}</div>
        <div style="font-size: 0.8rem; color: var(--primary-dark); margin: 0.2rem 0;">
          ${s.shop_name} (📍 ${s.distance_km} km) • <strong>₹${s.price.toFixed(2)}</strong>
        </div>
        <div style="font-size: 0.78rem; color: #475569; font-style: italic;">"${s.reason}"</div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="addToCartFromSubstitute(${s.product_id}, '${s.product_name.replace(/'/g, "\\'")}', ${s.price}, '${s.shop_name.replace(/'/g, "\\'")}')">
        Add Substitute
      </button>
    </div>
  `).join("");
}

// =========================================================================
// 3. "USE SOON" DEALS (Near-Expiry Clearance Deals)
// =========================================================================

async function loadUseSoonDeals() {
  try {
    const res = await fetch(`${API_BASE}/shopper-portal/use-soon-deals?shopper_lat=${shopperLocation.lat}&shopper_lon=${shopperLocation.lon}&days_window=14`);
    const data = await res.json();
    const container = document.getElementById("useSoonDealsContainer");

    if (res.ok && data.success) {
      if (data.deals.length === 0) {
        container.innerHTML = `<div class="empty-state" style="padding: 1rem;">No near-expiry deals available right now.</div>`;
        return;
      }

      container.innerHTML = data.deals.map(d => `
        <div class="product-card" style="border: 2px solid #fed7aa; background: #fffaf5;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
            <span class="badge badge-warning" style="background: #ffedd5; color: #c2410c;">🏷️ USE SOON DEAL</span>
            <span class="badge badge-danger" style="font-size: 0.72rem;">Expires in ${d.days_left}d</span>
          </div>

          <h4 style="margin-bottom: 0.2rem;">${d.product_name}</h4>
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.5rem;">
            ${d.shop_name} (📍 ${d.distance_km} km)
          </div>

          <div style="display: flex; align-items: baseline; gap: 0.4rem; margin-bottom: 0.6rem;">
            <span class="deal-strike">₹${d.original_price.toFixed(2)}</span>
            <span style="font-size: 1.25rem; font-weight: 800; color: #ea580c;">₹${d.deal_price.toFixed(2)}</span>
            <span style="font-size: 0.75rem; font-weight: 700; color: #16a34a;">(${d.discount_percent}% OFF)</span>
          </div>

          <button 
            class="btn btn-sm btn-block" 
            style="background: #ea580c; color: white;" 
            onclick="addToCart(${d.product_id}, '${d.product_name.replace(/'/g, "\\'")}', ${d.deal_price}, ${d.shop_id}, '${d.shop_name.replace(/'/g, "\\'")}', true)"
          >
            Grab Use Soon Deal
          </button>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading use soon deals:", err);
  }
}

// =========================================================================
// 4. CART & CHECKOUT (PRE-BOOK / BUY FROM HOME & COLLECT OPTIONS)
// =========================================================================

function addToCart(productId, name, price, shopId, shopName, hasSharedDelivery = true) {
  // If cart already has items from another shop, prompt user
  if (cart.length > 0 && cart[0].shop_id !== shopId) {
    if (!confirm(`Your cart already contains items from ${cart[0].shop_name}. Clear cart to add items from ${shopName}?`)) {
      return;
    }
    cart = [];
  }

  const existing = cart.find(it => it.product_id === productId);
  if (existing) {
    existing.quantity += 1;
  } else {
    cart.push({
      product_id: productId,
      name: name,
      price: price,
      shop_id: shopId,
      shop_name: shopName,
      quantity: 1,
      has_shared_delivery: hasSharedDelivery
    });
  }

  updateCartBadge();
  showToast(`Added ${name} to Cart`, "success");
}

function addToCartFromSubstitute(productId, name, price, shopName) {
  // Find product's shop info from catalog or assume 1
  addToCart(productId, name, price, 1, shopName, true);
}

function updateCartBadge() {
  const totalCount = cart.reduce((acc, it) => acc + it.quantity, 0);
  document.getElementById("cartCountBadge").textContent = totalCount;
}

function openCartModal() {
  const container = document.getElementById("cartItemsContainer");
  const shopNameHeader = document.getElementById("cartShopName");

  if (cart.length === 0) {
    container.innerHTML = `<div class="empty-state">Your cart is empty. Search products above to add items.</div>`;
    shopNameHeader.textContent = "";
    document.getElementById("cartTotalAmount").textContent = "₹0.00";
    document.getElementById("btnPlaceOrder").disabled = true;
    showModal("cartModal");
    return;
  }

  shopNameHeader.textContent = `Ordering from: ${cart[0].shop_name}`;
  let total = 0;

  container.innerHTML = cart.map(it => {
    const line = it.price * it.quantity;
    total += line;
    return `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--surface-border);">
        <div>
          <div style="font-weight: 600;">${it.name}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">₹${it.price.toFixed(2)} each</div>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm" onclick="modifyCartQty(${it.product_id}, -1)">-</button>
          <span style="font-weight: 700;">${it.quantity}</span>
          <button class="btn btn-secondary btn-sm" onclick="modifyCartQty(${it.product_id}, 1)">+</button>
          <span style="min-width: 60px; text-align: right; font-weight: 700;">₹${line.toFixed(2)}</span>
        </div>
      </div>
    `;
  }).join("");

  document.getElementById("cartTotalAmount").textContent = `₹${total.toFixed(2)}`;
  document.getElementById("btnPlaceOrder").disabled = false;

  // Check if home delivery is allowed (shop must be part of delivery cluster)
  const deliveryOptionInput = document.getElementById("optHomeDelivery");
  const deliveryWarning = document.getElementById("deliveryClusterWarning");
  if (!cart[0].has_shared_delivery) {
    deliveryOptionInput.disabled = true;
    deliveryWarning.style.display = "block";
    document.getElementById("optPickup").checked = true;
  } else {
    deliveryOptionInput.disabled = false;
    deliveryWarning.style.display = "none";
  }

  showModal("cartModal");
}

function modifyCartQty(prodId, delta) {
  const item = cart.find(it => it.product_id === prodId);
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    cart = cart.filter(it => it.product_id !== prodId);
  }
  updateCartBadge();
  openCartModal(); // Refresh view
}

async function handlePlaceOrder() {
  if (cart.length === 0 || !currentShopper) return;

  const orderType = document.querySelector('input[name="order_type"]:checked').value;
  const collectOption = document.querySelector('input[name="collect_option"]:checked').value;

  const payload = {
    shop_id: cart[0].shop_id,
    order_type: orderType,
    collect_option: collectOption,
    items: cart.map(it => ({ product_id: it.product_id, quantity: it.quantity }))
  };

  try {
    const res = await fetch(`${API_BASE}/orders/create?shopper_id=${currentShopper.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      hideModal("cartModal");
      cart = [];
      updateCartBadge();
      showToast(data.message, "success");
      loadOrderHistory();
      loadLoyaltyPoints();
      showShopperReceipt(data.order.order_number);
    } else {
      showToast(data.detail || "Failed to place order", "danger");
    }
  } catch (err) {
    showToast("Error processing order", "danger");
  }
}

// Digital Receipt for Order
async function showShopperReceipt(orderNumber) {
  try {
    const res = await fetch(`${API_BASE}/orders/receipt/${orderNumber}`);
    const data = await res.json();
    if (res.ok && data.success) {
      const r = data.receipt;
      document.getElementById("ordReceiptShop").textContent = r.shop.name;
      document.getElementById("ordReceiptNumber").textContent = r.order_number;
      document.getElementById("ordReceiptDate").textContent = r.timestamp;
      document.getElementById("ordReceiptType").textContent = `${r.order_type.toUpperCase()} (${r.collect_option.replace(/_/g, ' ').toUpperCase()})`;
      document.getElementById("ordReceiptStatus").textContent = r.status.toUpperCase();

      const itemsContainer = document.getElementById("ordReceiptItems");
      itemsContainer.innerHTML = r.items.map(it => `
        <div class="receipt-row">
          <span>${it.product_name} x ${it.quantity}</span>
          <span>₹${it.subtotal.toFixed(2)}</span>
        </div>
      `).join("");

      document.getElementById("ordReceiptTotal").textContent = `₹${r.total_amount.toFixed(2)}`;
      showModal("orderReceiptModal");
    }
  } catch (err) {
    console.error("Receipt error:", err);
  }
}

// =========================================================================
// 5. NOTIFICATIONS (NOTIFY-BACK FROM UNMET-DEMAND LOOP)
// =========================================================================

async function loadNotifications() {
  if (!currentShopper) return;
  try {
    const res = await fetch(`${API_BASE}/shopper-portal/notifications?shopper_id=${currentShopper.id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      const unread = data.notifications.filter(n => !n.is_read).length;
      document.getElementById("notifBadge").textContent = unread;

      const container = document.getElementById("notificationsList");
      if (data.notifications.length === 0) {
        container.innerHTML = `<div class="empty-state">No notifications yet. When out-of-stock items you searched for arrive in stock, you will be notified here!</div>`;
        return;
      }

      container.innerHTML = data.notifications.map(n => `
        <div class="insight-card ${n.is_read ? 'urgency-low' : 'urgency-high'}" style="position: relative;">
          <div style="font-weight: 700; font-size: 0.95rem;">${n.title}</div>
          <p style="font-size: 0.88rem; margin: 0.3rem 0;">${n.message}</p>
          <div style="font-size: 0.72rem; color: var(--text-muted);">${n.created_at}</div>
          ${!n.is_read ? `<button class="btn btn-secondary btn-sm" onclick="markNotifRead(${n.id})" style="margin-top: 0.4rem;">Mark Read</button>` : ''}
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading notifications:", err);
  }
}

async function markNotifRead(notifId) {
  if (!currentShopper) return;
  try {
    await fetch(`${API_BASE}/shopper-portal/notifications/${notifId}/read?shopper_id=${currentShopper.id}`, { method: "PUT" });
    loadNotifications();
  } catch (err) {
    console.error(err);
  }
}

// =========================================================================
// 6. LOYALTY POINTS & ORDER HISTORY
// =========================================================================

async function loadLoyaltyPoints() {
  if (!currentShopper) return;
  try {
    const res = await fetch(`${API_BASE}/shopper-portal/loyalty-points?shopper_id=${currentShopper.id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("shopperPointsBalance").textContent = data.points_balance;
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadOrderHistory() {
  if (!currentShopper) return;
  try {
    const res = await fetch(`${API_BASE}/orders/shopper/history?shopper_id=${currentShopper.id}`);
    const data = await res.json();
    const container = document.getElementById("shopperOrderHistoryContainer");

    if (res.ok && data.success) {
      if (data.orders.length === 0) {
        container.innerHTML = `<div class="empty-state">No past orders. Place your first order to start earning Agora loyalty points!</div>`;
        return;
      }

      container.innerHTML = data.orders.map(o => `
        <div class="card" style="margin-bottom: 0.75rem;">
          <div class="card-header" style="margin-bottom: 0.4rem; padding-bottom: 0.4rem;">
            <div>
              <strong>${o.order_number}</strong>
              <span class="badge badge-primary" style="margin-left: 0.4rem;">${o.status.replace(/_/g, ' ')}</span>
            </div>
            <div style="font-weight: 800; color: var(--primary);">₹${o.total_amount.toFixed(2)}</div>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
            From: <strong>${o.shop_name}</strong> • ${o.collect_option === 'home_delivery' ? '🛵 Home Delivery' : '🏬 Pickup'} • ${o.created_at}
          </div>
          <div style="font-size: 0.85rem;">
            ${o.items.map(it => `• ${it.product_name} x ${it.quantity} (₹${it.subtotal.toFixed(2)})`).join("<br>")}
          </div>
          <button class="btn btn-secondary btn-sm" onclick="showShopperReceipt('${o.order_number}')" style="margin-top: 0.6rem;">
            🧾 View Digital Receipt
          </button>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error(err);
  }
}

// =========================================================================
// 7. EVENT LISTENERS
// =========================================================================

function setupShopperEvents() {
  const searchInput = document.getElementById("shopperSearchInput");
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        performSearch(e.target.value.trim());
      }, 350);
    });
  }

  const regForm = document.getElementById("registerShopperForm");
  if (regForm) regForm.addEventListener("submit", handleRegisterShopper);
}

function showModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add("active");
}

function hideModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove("active");
}

function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}
