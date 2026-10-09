/**
 * AgoraZure - Shopper Portal Interactive Engine
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
let currentShopper = null;
let shopperLocation = {
  lat: 12.9716,
  lon: 77.5946,
  address: "Indiranagar, Bengaluru"
};
let cart = []; // [{ product_id, name, price, original_price, shop_id, shop_name, quantity, has_shared_delivery, image_url, unit }]
let activeCategory = "All";
let searchDebounceTimer = null;
let trackingPollInterval = null;
let bannerInterval = null;
let currentBannerIdx = 0;
let bannerCount = 0;
let trackingOrderId = null;

// =========================================================================
// 1. INITIALIZATION & AUTHENTICATION
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
  initShopperAuth();
  loadShopsFilterDropdown();
  setupEventListeners();
  loadActiveBanners();
  loadUseSoonDeals();
  performSearch(""); // Initial catalog load
});

function initShopperAuth() {
  const saved = localStorage.getItem("agorazure_shopper");
  if (saved) {
    try {
      currentShopper = JSON.parse(saved);
      shopperLocation.lat = currentShopper.latitude || 12.9716;
      shopperLocation.lon = currentShopper.longitude || 77.5946;
      shopperLocation.address = currentShopper.address || "Indiranagar, Bengaluru";
      renderShopperHeader();
      loadNotifications();
      loadLoyaltyPoints();
      loadOrderHistory(true);
      return;
    } catch (e) {
      localStorage.removeItem("agorazure_shopper");
    }
  }
  renderShopperHeader();
}

function renderShopperHeader() {
  const nameEl = document.getElementById("shopperNameDisplay");
  const locEl = document.getElementById("shopperLocationDisplay");
  const btnLogout = document.getElementById("btnLogout");

  if (currentShopper) {
    if (nameEl) nameEl.textContent = currentShopper.name || "Shopper";
    if (locEl) locEl.textContent = shopperLocation.address || "Indiranagar, Bengaluru";
    if (btnLogout) btnLogout.style.display = "inline-flex";
  } else {
    if (nameEl) nameEl.textContent = "Sign In";
    if (locEl) locEl.textContent = "Set Delivery Location";
    if (btnLogout) btnLogout.style.display = "none";
  }
}

function switchAuthTab(tab) {
  const loginContainer = document.getElementById("authLoginFormContainer");
  const regContainer = document.getElementById("authRegisterFormContainer");
  const tabLogin = document.getElementById("tabAuthLogin");
  const tabReg = document.getElementById("tabAuthRegister");

  if (tab === "register") {
    loginContainer.style.display = "none";
    regContainer.style.display = "block";
    tabReg.style.color = "var(--primary)";
    tabReg.style.borderBottomColor = "var(--primary)";
    tabLogin.style.color = "var(--text-muted)";
    tabLogin.style.borderBottomColor = "transparent";
  } else {
    loginContainer.style.display = "block";
    regContainer.style.display = "none";
    tabLogin.style.color = "var(--primary)";
    tabLogin.style.borderBottomColor = "var(--primary)";
    tabReg.style.color = "var(--text-muted)";
    tabReg.style.borderBottomColor = "transparent";
  }
}

async function handleShopperLogin(e) {
  e.preventDefault();
  const form = e.target;
  const identifier = form.identifier.value.trim();
  const password = form.password.value.trim();

  if (!identifier || !password) {
    showToast("Please enter your phone or email and password", "warning");
    return;
  }

  const payload = {
    phone: identifier.includes("@") ? null : identifier,
    email: identifier.includes("@") ? identifier : null,
    password: password
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopper/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      currentShopper = data.shopper;
      localStorage.setItem("agorazure_shopper", JSON.stringify(currentShopper));
      shopperLocation.lat = currentShopper.latitude || 12.9716;
      shopperLocation.lon = currentShopper.longitude || 77.5946;
      shopperLocation.address = currentShopper.address || "Indiranagar, Bengaluru";
      renderShopperHeader();
      hideModal("shopperAuthModal");
      showToast(`Welcome back, ${currentShopper.name}!`, "success");
      loadNotifications();
      loadLoyaltyPoints();
      loadOrderHistory(true);
      performSearch(getSearchQuery());
    } else {
      showToast(data.detail || "Invalid login credentials. Please try again.", "danger");
    }
  } catch (err) {
    showToast("Network error: Unable to connect to server.", "danger");
  }
}

async function quickShopperLogin(phone, password) {
  const res = await fetch(`${API_BASE}/auth/shopper/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, password })
  });
  const data = await res.json();
  if (res.ok && data.success) {
    currentShopper = data.shopper;
    localStorage.setItem("agorazure_shopper", JSON.stringify(currentShopper));
    shopperLocation.lat = currentShopper.latitude || 12.9716;
    shopperLocation.lon = currentShopper.longitude || 77.5946;
    shopperLocation.address = currentShopper.address || "Indiranagar, Bengaluru";
    renderShopperHeader();
    hideModal("shopperAuthModal");
    showToast(`Logged in as ${currentShopper.name}`, "success");
    loadNotifications();
    loadLoyaltyPoints();
    loadOrderHistory(true);
    performSearch(getSearchQuery());
  } else {
    showToast(data.detail || "Quick login failed.", "danger");
  }
}

async function handleRegisterShopper(e) {
  e.preventDefault();
  const form = e.target;
  const name = form.name.value.trim();
  const phone = form.phone.value.trim();
  const email = form.email.value.trim();
  const address = form.address.value.trim();
  const password = form.password.value;
  const confirm = form.confirm_password.value;

  if (password !== confirm) {
    showToast("Passwords do not match. Please re-enter.", "warning");
    return;
  }
  if (phone.length < 10) {
    showToast("Please enter a valid 10-digit mobile number.", "warning");
    return;
  }

  const payload = {
    name,
    phone,
    email: email || null,
    address,
    password,
    latitude: 12.9716,
    longitude: 77.5946
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopper/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast("Account created successfully! Logging you in...", "success");
      await quickShopperLogin(phone, password);
    } else {
      showToast(data.detail || "Registration failed. Phone may already be registered.", "danger");
    }
  } catch (err) {
    showToast("Network error: Could not complete registration.", "danger");
  }
}

function shopperLogout() {
  localStorage.removeItem("agorazure_shopper");
  currentShopper = null;
  renderShopperHeader();
  showToast("You have been signed out.", "info");
  location.reload();
}

function openProfileModal(isLocationEdit = false) {
  if (!currentShopper) {
    showModal("shopperAuthModal");
    return;
  }

  document.getElementById("profNameInput").value = currentShopper.name || "";
  document.getElementById("profPhoneInput").value = currentShopper.phone || "";
  document.getElementById("profEmailInput").value = currentShopper.email || "";
  document.getElementById("profAddressInput").value = currentShopper.address || shopperLocation.address || "";
  document.getElementById("profLatInput").value = currentShopper.latitude || shopperLocation.lat || 12.9716;
  document.getElementById("profLonInput").value = currentShopper.longitude || shopperLocation.lon || 77.5946;

  if (isLocationEdit) {
    document.getElementById("profileModalTitle").textContent = "📍 Update Delivery Location";
  } else {
    document.getElementById("profileModalTitle").textContent = "👤 My Profile Details";
  }

  showModal("shopperProfileModal");
}

async function handleSaveShopperProfile(e) {
  e.preventDefault();
  if (!currentShopper) return;

  const form = e.target;
  const payload = {
    name: form.name.value.trim(),
    phone: form.phone.value.trim(),
    email: form.email.value.trim() || null,
    address: form.address.value.trim(),
    latitude: parseFloat(form.latitude.value),
    longitude: parseFloat(form.longitude.value)
  };

  try {
    const res = await fetch(`${API_BASE}/auth/shopper/profile?shopper_id=${currentShopper.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      currentShopper = data.shopper;
      localStorage.setItem("agorazure_shopper", JSON.stringify(currentShopper));
      shopperLocation.lat = currentShopper.latitude;
      shopperLocation.lon = currentShopper.longitude;
      shopperLocation.address = currentShopper.address;
      renderShopperHeader();
      hideModal("shopperProfileModal");
      showToast("Profile details updated successfully!", "success");
      performSearch(getSearchQuery());
    } else {
      showToast(data.detail || "Failed to update profile", "danger");
    }
  } catch (err) {
    showToast("Network error updating profile.", "danger");
  }
}

// =========================================================================
// 2. SEARCH & AUTOCOMPLETE SUGGESTIONS
// =========================================================================

function getSearchQuery() {
  const inp = document.getElementById("shopperSearchInput");
  return inp ? inp.value.trim() : "";
}

function clearSearch() {
  const inp = document.getElementById("shopperSearchInput");
  if (inp) inp.value = "";
  const clearBtn = document.getElementById("searchClearBtn");
  if (clearBtn) clearBtn.style.display = "none";
  hideSearchDropdown();
  performSearch("");
}

function triggerSearchNow() {
  hideSearchDropdown();
  performSearch(getSearchQuery());
}

function hideSearchDropdown() {
  const dd = document.getElementById("searchDropdown");
  if (dd) dd.classList.remove("active");
}

async function fetchSearchSuggestions(prefix) {
  const dd = document.getElementById("searchDropdown");
  const container = document.getElementById("dropdownSuggestionsContainer");
  if (!dd || !container) return;

  const shopFilterEl = document.getElementById("shopperShopFilter");
  const shopParam = (shopFilterEl && shopFilterEl.value) ? `&shop_id=${shopFilterEl.value}` : "";

  try {
    const res = await fetch(`${API_BASE}/shopper-portal/suggestions?q=${encodeURIComponent(prefix)}${shopParam}`);
    const data = await res.json();

    if (res.ok && data.success && data.suggestions && data.suggestions.length > 0) {
      container.innerHTML = `
        <div class="dropdown-section-title">SUGGESTIONS & PRODUCTS</div>
        ${data.suggestions.map(s => {
          const isProd = s.type === "product";
          const imgHtml = s.image_url ? `<img src="${s.image_url}" class="dropdown-thumb" alt="${s.text}">` : `<span style="font-size: 1.3rem;">📦</span>`;
          const priceHtml = s.price ? `<div class="dropdown-item-price">₹${Number(s.price).toFixed(2)}</div>` : '';

          return `
            <div class="dropdown-item" onclick="selectSuggestion('${s.text.replace(/'/g, "\\'")}')">
              <div class="dropdown-item-left">
                ${imgHtml}
                <div>
                  <div class="dropdown-item-title">${s.text}</div>
                  <div class="dropdown-item-sub">${s.category || (s.type === 'brand' ? 'Brand' : 'Category')}</div>
                </div>
              </div>
              ${priceHtml}
            </div>
          `;
        }).join("")}
      `;
      dd.classList.add("active");
    } else {
      hideSearchDropdown();
    }
  } catch (err) {
    hideSearchDropdown();
  }
}

function selectSuggestion(text) {
  const inp = document.getElementById("shopperSearchInput");
  if (inp) inp.value = text;
  hideSearchDropdown();
  performSearch(text);
}

function selectCategory(cat, btnEl) {
  activeCategory = cat;
  document.querySelectorAll(".category-pill").forEach(el => el.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");

  const titleEl = document.getElementById("catalogSectionTitle");
  if (titleEl) {
    titleEl.textContent = cat === "All" ? "Nearby Products & Essentials" : `${cat} Essentials`;
  }
  performSearch(getSearchQuery());
}

async function loadShopsFilterDropdown() {
  const sel = document.getElementById("shopperShopFilter");
  if (!sel) return;

  try {
    const res = await fetch(`${API_BASE}/auth/shops`);
    const data = await res.json();
    if (res.ok && data.success && data.shops) {
      const options = data.shops.map(s => `
        <option value="${s.id}">${s.name} (${s.address.split(',')[0]} • ${s.is_open ? 'Open' : 'Closed'})</option>
      `).join("");
      sel.innerHTML = `<option value="">All Nearby Neighborhood Shops</option>` + options;
    }
  } catch (err) {}
}

function handleShopFilterChange() {
  performSearch(getSearchQuery());
}

async function performSearch(query = "") {
  const container = document.getElementById("searchResultsContainer");
  const substitutesContainer = document.getElementById("substitutesContainer");
  if (substitutesContainer) substitutesContainer.style.display = "none";

  const clearBtn = document.getElementById("searchClearBtn");
  if (clearBtn) clearBtn.style.display = query ? "flex" : "none";

  const sId = (currentShopper && currentShopper.id) ? currentShopper.id : "";
  const queryParam = sId ? `&shopper_id=${sId}` : "";
  const shopFilterEl = document.getElementById("shopperShopFilter");
  const shopFilterParam = (shopFilterEl && shopFilterEl.value) ? `&shop_id=${shopFilterEl.value}` : "";
  const catParam = (activeCategory && activeCategory !== "All") ? `&category=${encodeURIComponent(activeCategory)}` : "";

  const url = `${API_BASE}/shopper-portal/search?q=${encodeURIComponent(query)}&shopper_lat=${shopperLocation.lat}&shopper_lon=${shopperLocation.lon}${queryParam}${shopFilterParam}${catParam}`;

  // Skeleton Loading
  container.innerHTML = Array(8).fill(0).map(() => `
    <div class="card skeleton" style="height: 280px;"></div>
  `).join("");

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (res.ok && data.success) {
      const resultsCountEl = document.getElementById("catalogResultsCount");
      if (resultsCountEl) {
        resultsCountEl.textContent = `${data.results_count || data.products.length} items found`;
      }

      // Handle Unmet Demand / Missed Search & Smart AI Substitutes
      if (data.is_missed_search) {
        showToast("🔍 Item not in stock. Logged in Unmet-Demand loop!", "warning");
        if (data.smart_substitutes && data.smart_substitutes.length > 0) {
          renderSmartSubstitutes(data.query, data.smart_substitutes);
        }
      }

      // Empty State with Suggestions
      if (!data.products || data.products.length === 0) {
        const popularChips = ["Milk", "Bread", "Eggs", "Atta", "Rice", "Tea", "Butter", "Biscuits"];
        container.innerHTML = `
          <div class="empty-state" style="grid-column: 1 / -1; padding: 3rem 1.5rem;">
            <div class="empty-icon">🔎</div>
            <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem; color: var(--text-main);">No items found</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.25rem;">
              ${query ? `No items matching "<strong>${escapeHtml(query)}</strong>" were found in nearby stores.` : 'No products available for this filter.'}
            </p>
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.6rem; font-weight: 600;">Popular Searches:</div>
            <div style="display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;">
              ${popularChips.map(ch => `
                <button class="btn btn-secondary btn-sm" onclick="selectSuggestion('${ch}')">${ch}</button>
              `).join("")}
            </div>
          </div>
        `;
        return;
      }

      // Render Rich Product Cards
      container.innerHTML = data.products.map(p => renderProductCardHtml(p)).join("");
    } else {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;">Failed to load catalog. Please try again.</div>`;
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;">Network error loading catalog.</div>`;
  }
}

function renderProductCardHtml(p) {
  const inStock = p.in_stock && (p.is_available !== false);
  const cartItem = cart.find(it => it.product_id === p.id);
  const qtyInCart = cartItem ? cartItem.quantity : 0;
  const fallbackImg = "https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&auto=format&fit=crop&q=80";
  const imgSrc = p.image_url || fallbackImg;

  const discountBadge = p.has_offer 
    ? `<span class="discount-badge">${Math.round(p.discount_percent)}% OFF</span>`
    : (p.mrp && p.mrp > p.price 
        ? `<span class="discount-badge">${Math.round(((p.mrp - p.price) / p.mrp) * 100)}% OFF</span>` 
        : '');

  let actionHtml = '';
  if (!inStock) {
    actionHtml = `<span class="badge" style="background: #f1f5f9; color: #94a3b8; font-size: 0.75rem;">OUT OF STOCK</span>`;
  } else if (qtyInCart > 0) {
    actionHtml = `
      <div class="stepper-container">
        <button class="stepper-btn" onclick="modifyCartQty(${p.id}, -1)">-</button>
        <span class="stepper-val">${qtyInCart}</span>
        <button class="stepper-btn" onclick="modifyCartQty(${p.id}, 1)">+</button>
      </div>
    `;
  } else {
    actionHtml = `
      <button class="btn btn-primary btn-sm btn-add-stepper" onclick="addToCart(${p.id}, '${escapeHtml(p.name)}', ${p.price}, ${p.mrp || p.price}, ${p.shop_id}, '${escapeHtml(p.shop_name)}', ${p.has_shared_delivery}, '${p.image_url || ''}', '${p.unit || '1 pc'}')">
        + ADD
      </button>
    `;
  }

  return `
    <div class="product-card" id="prodCard-${p.id}">
      <div class="product-image-wrap">
        <img src="${imgSrc}" class="product-img" alt="${escapeHtml(p.name)}" loading="lazy" onerror="this.src='${fallbackImg}'">
        ${discountBadge}
      </div>

      <div class="product-unit">${p.unit || '1 pc'} • ${p.brand || 'General'}</div>
      <div class="product-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>

      <div class="product-shop-tag">
        <span>🏪</span> <strong>${escapeHtml(p.shop_name)}</strong> • ${Number(p.distance_km).toFixed(1)} km
      </div>

      <div class="product-footer">
        <div class="price-box">
          <div class="price-current">₹${Number(p.price).toFixed(2)}</div>
          ${(p.mrp && p.mrp > p.price) ? `<div class="price-mrp">₹${Number(p.mrp).toFixed(2)}</div>` : ''}
        </div>
        <div>
          ${actionHtml}
        </div>
      </div>
    </div>
  `;
}

function renderSmartSubstitutes(missingItem, subs) {
  const container = document.getElementById("substitutesContainer");
  const list = document.getElementById("substitutesList");
  const title = document.getElementById("missingItemTitle");
  if (!container || !list) return;

  title.textContent = missingItem;
  list.innerHTML = subs.map(s => `
    <div class="card" style="border: 1px solid #38bdf8; background: #ffffff;">
      <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 0.2rem;">${escapeHtml(s.name)}</div>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.4rem;">
        Available at <strong>${escapeHtml(s.shop_name)}</strong> (Shop ID: ${s.shop_id})
      </div>
      <div style="font-size: 0.78rem; color: #0284c7; background: #f0f9ff; padding: 0.4rem; border-radius: var(--radius-sm); margin-bottom: 0.6rem;">
        💡 ${escapeHtml(s.reason)}
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 800; color: var(--primary);">₹${Number(s.price).toFixed(2)}</span>
        <button class="btn btn-primary btn-sm" onclick="addToCart(${s.product_id}, '${escapeHtml(s.name)}', ${s.price}, ${s.price}, ${s.shop_id}, '${escapeHtml(s.shop_name)}', true, '', '1 pc')">
          + Add Alternate
        </button>
      </div>
    </div>
  `).join("");
  container.style.display = "block";
}

async function loadUseSoonDeals() {
  const container = document.getElementById("useSoonDealsContainer");
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/shopper-portal/use-soon-deals?shopper_lat=${shopperLocation.lat}&shopper_lon=${shopperLocation.lon}`);
    const data = await res.json();

    if (res.ok && data.success && data.deals && data.deals.length > 0) {
      container.innerHTML = data.deals.slice(0, 4).map(d => {
        const discPrice = d.discounted_price || (d.price * (1 - d.discount_percent/100));
        return `
          <div class="product-card" style="border-top: 3px solid #f59e0b;">
            <div class="product-image-wrap">
              <img src="${d.image_url || 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=400'}" class="product-img" alt="${escapeHtml(d.name)}">
              <span class="use-soon-badge">${Math.round(d.discount_percent)}% OFF</span>
            </div>
            <div class="product-unit">${d.unit || '1 pc'} • Expiry: <strong>${d.expiry_date}</strong></div>
            <div class="product-name">${escapeHtml(d.name)}</div>
            <div class="product-shop-tag">🏪 <strong>${escapeHtml(d.shop_name)}</strong></div>
            <div class="product-footer">
              <div class="price-box">
                <div class="price-current" style="color: #b45309;">₹${Number(discPrice).toFixed(2)}</div>
                <div class="price-mrp">₹${Number(d.price).toFixed(2)}</div>
              </div>
              <button class="btn btn-primary btn-sm btn-add-stepper" onclick="addToCart(${d.id}, '${escapeHtml(d.name)}', ${discPrice}, ${d.price}, ${d.shop_id}, '${escapeHtml(d.shop_name)}', true, '${d.image_url || ''}', '${d.unit || '1 pc'}')">
                + ADD
              </button>
            </div>
          </div>
        `;
      }).join("");
    } else {
      const section = document.getElementById("useSoonSection");
      if (section) section.style.display = "none";
    }
  } catch (err) {}
}

async function loadActiveBanners() {
  const track = document.getElementById("bannerTrack");
  const dotsContainer = document.getElementById("carouselDots");
  const section = document.getElementById("bannerCarouselSection");
  if (!track || !section) return;

  try {
    const res = await fetch(`${API_BASE}/marketing/active-banners`);
    const data = await res.json();

    if (res.ok && data.success && data.banners && data.banners.length > 0) {
      bannerCount = data.banners.length;
      track.innerHTML = data.banners.map((b, idx) => `
        <div class="banner-slide ${idx % 2 === 1 ? 'slide-alt' : ''}">
          <div>
            <span class="banner-badge">${b.badge || `${Math.round(b.discount_percent)}% OFF`}</span>
            <div class="banner-title">${escapeHtml(b.title)}</div>
            <div class="banner-desc">${escapeHtml(b.banner_text)} • Valid till ${b.valid_to}</div>
          </div>
          <div style="font-size: 3rem; opacity: 0.85;">🏷️</div>
        </div>
      `).join("");

      dotsContainer.innerHTML = data.banners.map((_, i) => `
        <div class="carousel-dot ${i === 0 ? 'active' : ''}" onclick="goToBannerSlide(${i})"></div>
      `).join("");

      section.style.display = "block";

      if (bannerInterval) clearInterval(bannerInterval);
      bannerInterval = setInterval(() => {
        currentBannerIdx = (currentBannerIdx + 1) % bannerCount;
        updateBannerSlide();
      }, 5000);
    }
  } catch (err) {}
}

function goToBannerSlide(idx) {
  currentBannerIdx = idx;
  updateBannerSlide();
}

function updateBannerSlide() {
  const track = document.getElementById("bannerTrack");
  if (track) track.style.transform = `translateX(-${currentBannerIdx * 100}%)`;
  document.querySelectorAll(".carousel-dot").forEach((dot, i) => {
    dot.classList.toggle("active", i === currentBannerIdx);
  });
}

// =========================================================================
// 3. CART & CHECKOUT DRAWER
// =========================================================================

function addToCart(prodId, name, price, mrp, shopId, shopName, hasSharedDelivery, imageUrl, unit) {
  // Check if items are from another shop
  if (cart.length > 0 && cart[0].shop_id !== shopId) {
    if (!confirm(`Your cart already contains items from "${cart[0].shop_name}". Clear your current cart and start ordering from "${shopName}"?`)) {
      return;
    }
    cart = [];
  }

  const existing = cart.find(it => it.product_id === prodId);
  if (existing) {
    existing.quantity += 1;
  } else {
    cart.push({
      product_id: prodId,
      name,
      price: parseFloat(price),
      mrp: parseFloat(mrp) || parseFloat(price),
      shop_id: shopId,
      shop_name: shopName,
      has_shared_delivery: Boolean(hasSharedDelivery),
      image_url: imageUrl,
      unit: unit || "1 pc",
      quantity: 1
    });
  }

  updateCartState();
  showToast(`Added "${name}" to cart`, "info");
}

function modifyCartQty(prodId, delta) {
  const item = cart.find(it => it.product_id === prodId);
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    cart = cart.filter(it => it.product_id !== prodId);
  }

  updateCartState();
}

function updateCartState() {
  updateCartBadges();
  renderCartDrawerContent();
  // Re-render product cards in search results so the steppers reflect active counts
  performSearch(getSearchQuery());
}

function updateCartBadges() {
  const totalQty = cart.reduce((acc, it) => acc + it.quantity, 0);
  const totalAmount = cart.reduce((acc, it) => acc + (it.price * it.quantity), 0);

  const cartBadge = document.getElementById("cartCountBadge");
  if (cartBadge) cartBadge.textContent = totalQty;
  const mobileBadge = document.getElementById("mobileCartCount");
  if (mobileBadge) mobileBadge.textContent = totalQty;
  const headerTotal = document.getElementById("cartHeaderTotal");
  if (headerTotal) headerTotal.textContent = `₹${totalAmount.toFixed(2)}`;
}

function openCartDrawer() {
  renderCartDrawerContent();
  document.getElementById("cartDrawerOverlay").classList.add("active");
  document.getElementById("cartDrawer").classList.add("active");
}

function closeCartDrawer() {
  document.getElementById("cartDrawerOverlay").classList.remove("active");
  document.getElementById("cartDrawer").classList.remove("active");
}

function renderCartDrawerContent() {
  const container = document.getElementById("cartItemsContainer");
  const shopBanner = document.getElementById("cartShopBanner");
  const fulfillmentSection = document.getElementById("cartFulfillmentSection");
  const btnCheckout = document.getElementById("btnCheckout");

  if (!container) return;

  if (cart.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 2.5rem 1rem;">
        <div class="empty-icon">🛒</div>
        <div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.35rem;">Your Cart is Empty</div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">Explore essentials from neighborhood stores and add items.</div>
      </div>
    `;
    if (shopBanner) shopBanner.style.display = "none";
    if (fulfillmentSection) fulfillmentSection.style.display = "none";
    if (btnCheckout) btnCheckout.disabled = true;
    return;
  }

  // Populate Shop Info
  if (shopBanner) {
    shopBanner.style.display = "flex";
    document.getElementById("cartDrawerShopName").textContent = cart[0].shop_name;
  }
  if (fulfillmentSection) fulfillmentSection.style.display = "block";
  if (btnCheckout) btnCheckout.disabled = false;

  // Render items
  container.innerHTML = cart.map(it => `
    <div class="cart-item-row">
      <div style="flex: 1; padding-right: 0.5rem;">
        <div style="font-weight: 700; font-size: 0.9rem;">${escapeHtml(it.name)}</div>
        <div style="font-size: 0.78rem; color: var(--text-muted);">₹${it.price.toFixed(2)} each</div>
      </div>
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <div class="stepper-container" style="height: 30px; min-width: 78px;">
          <button class="stepper-btn" onclick="modifyCartQty(${it.product_id}, -1)">-</button>
          <span class="stepper-val">${it.quantity}</span>
          <button class="stepper-btn" onclick="modifyCartQty(${it.product_id}, 1)">+</button>
        </div>
        <div style="font-weight: 800; min-width: 60px; text-align: right;">
          ₹${(it.price * it.quantity).toFixed(2)}
        </div>
      </div>
    </div>
  `).join("");

  // Populate Saved Address
  const addrInput = document.getElementById("cartDeliveryAddress");
  if (addrInput && !addrInput.value) {
    addrInput.value = (currentShopper && currentShopper.address) ? currentShopper.address : shopperLocation.address;
  }

  // Verify Home Delivery capability
  const optHome = document.getElementById("optHomeDelivery");
  const optPickup = document.getElementById("optPickup");
  const clusterWarn = document.getElementById("deliveryClusterWarning");
  if (!cart[0].has_shared_delivery) {
    if (optHome) optHome.disabled = true;
    if (optPickup) optPickup.checked = true;
    if (clusterWarn) clusterWarn.style.display = "block";
  } else {
    if (optHome) optHome.disabled = false;
    if (clusterWarn) clusterWarn.style.display = "none";
  }

  updateCartBillSummary();
}

function updateCartBillSummary() {
  if (cart.length === 0) return;

  const itemTotal = cart.reduce((acc, it) => acc + (it.price * it.quantity), 0);
  const mrpTotal = cart.reduce((acc, it) => acc + ((it.mrp || it.price) * it.quantity), 0);
  const savings = Math.max(0, mrpTotal - itemTotal);

  const isPickup = document.getElementById("optPickup") && document.getElementById("optPickup").checked;
  const deliveryFee = isPickup ? 0.0 : 25.0;
  const tax = itemTotal * 0.05;
  const grandTotal = itemTotal + deliveryFee + tax;

  document.getElementById("billItemTotal").textContent = `₹${itemTotal.toFixed(2)}`;
  document.getElementById("billDeliveryFee").textContent = deliveryFee === 0 ? "FREE" : `₹${deliveryFee.toFixed(2)}`;
  document.getElementById("billTax").textContent = `₹${tax.toFixed(2)}`;
  document.getElementById("billGrandTotal").textContent = `₹${grandTotal.toFixed(2)}`;

  const savingsRow = document.getElementById("billSavingsRow");
  if (savings > 0) {
    savingsRow.style.display = "flex";
    document.getElementById("billSavings").textContent = `-₹${savings.toFixed(2)}`;
  } else {
    savingsRow.style.display = "none";
  }

  const btnCheckout = document.getElementById("btnCheckout");
  if (btnCheckout) {
    btnCheckout.textContent = `Place Order • ₹${grandTotal.toFixed(2)}`;
  }
}

async function handlePlaceOrder() {
  if (!currentShopper) {
    showModal("shopperAuthModal");
    return;
  }

  if (cart.length === 0) {
    showToast("Your cart is empty.", "warning");
    return;
  }

  const btnCheckout = document.getElementById("btnCheckout");
  const errorBox = document.getElementById("cartErrorBox");
  if (errorBox) errorBox.style.display = "none";

  const isPickup = document.getElementById("optPickup") && document.getElementById("optPickup").checked;
  const collectOption = isPickup ? "pickup" : "home_delivery";
  const deliveryAddr = document.getElementById("cartDeliveryAddress").value.trim() || currentShopper.address;
  const paymentMethod = document.getElementById("cartPaymentMethod").value;

  const payload = {
    shop_id: cart[0].shop_id,
    order_type: "buy_from_home",
    collect_option: collectOption,
    delivery_address: deliveryAddr,
    payment_method: paymentMethod,
    items: cart.map(it => ({
      product_id: it.product_id,
      quantity: it.quantity
    }))
  };

  btnCheckout.disabled = true;
  btnCheckout.textContent = "Saving Order to Database...";

  try {
    const res = await fetch(`${API_BASE}/orders/create?shopper_id=${currentShopper.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success && data.order) {
      closeCartDrawer();
      cart = [];
      updateCartState();
      showToast("Order placed successfully!", "success");
      loadOrderHistory(true);
      loadLoyaltyPoints();

      // Open Live Order Tracking immediately
      openOrderTrackingModal(data.order.id || data.order.orderId);
    } else {
      btnCheckout.disabled = false;
      btnCheckout.textContent = "Retry Placing Order";
      if (errorBox) {
        errorBox.style.display = "block";
        document.getElementById("cartErrorText").textContent = data.detail || "Order could not be saved.";
      }
      showToast(data.detail || "Failed to place order. Please retry.", "danger");
    }
  } catch (err) {
    btnCheckout.disabled = false;
    btnCheckout.textContent = "Retry Placing Order";
    if (errorBox) {
      errorBox.style.display = "block";
      document.getElementById("cartErrorText").textContent = "Network error while saving order.";
    }
    showToast("Network error. Please check connection and retry.", "danger");
  }
}

// =========================================================================
// 4. LIVE ORDER TRACKING (SWIGGY / ZOMATO TIMELINE)
// =========================================================================

async function openOrderTrackingModal(orderId) {
  trackingOrderId = orderId;
  showModal("orderTrackingModal");
  await fetchAndRenderTracking(orderId);

  if (trackingPollInterval) clearInterval(trackingPollInterval);
  trackingPollInterval = setInterval(() => {
    if (trackingOrderId) fetchAndRenderTracking(trackingOrderId, true);
  }, 3000); // 3-second live polling
}

function closeOrderTrackingModal() {
  if (trackingPollInterval) clearInterval(trackingPollInterval);
  trackingOrderId = null;
  hideModal("orderTrackingModal");
}

async function fetchAndRenderTracking(orderId, isSilent = false) {
  const body = document.getElementById("trackingModalBody");
  const headerNum = document.getElementById("trackOrderNumHeader");
  if (!body) return;

  try {
    const res = await fetch(`${API_BASE}/orders/track/${orderId}`);
    const data = await res.json();

    if (res.ok && data.success && data.order) {
      const o = data.order;
      if (headerNum) headerNum.textContent = `Order #${o.order_number} • ${o.shop.name}`;

      const isRejected = o.is_rejected;

      const timelineHtml = `
        <div class="order-tracking-card" style="padding: 1.25rem;">
          <div class="tracking-header">
            <div>
              <div style="font-size: 1.15rem; font-weight: 800; color: var(--text-main);">
                ${isRejected ? 'Order Rejected' : o.status_display}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                Placed on ${o.created_at} • ${o.collect_option === 'home_delivery' ? '🛵 Home Delivery' : '🏬 Store Pickup'}
              </div>
            </div>
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--primary);">
              ₹${Number(o.total_amount).toFixed(2)}
            </div>
          </div>

          ${isRejected ? `
            <div class="order-rejected-banner">
              <span style="font-size: 1.5rem;">✕</span>
              <div>
                <div style="font-weight: 800;">Order was Rejected by Store</div>
                <div style="font-size: 0.85rem; margin-top: 0.2rem;">
                  Reason: <strong>"${escapeHtml(o.reject_reason || 'Store could not fulfill items')}"</strong>
                </div>
              </div>
            </div>
          ` : `
            <!-- Live Progress Stepper -->
            <div class="timeline-stepper">
              ${(o.timeline || []).map(step => `
                <div class="timeline-step ${step.completed ? 'completed' : ''} ${step.current ? 'current' : ''}">
                  <div class="step-marker-col">
                    <div class="step-marker">
                      ${step.completed ? '✓' : (step.step === 1 ? '📝' : (step.step === 2 ? '👍' : (step.step === 3 ? '🍳' : (step.step === 4 ? '🛵' : '🎉'))))}
                    </div>
                    <div class="step-line"></div>
                  </div>
                  <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <div class="step-desc">${step.desc}</div>
                  </div>
                </div>
              `).join("")}
            </div>
          `}

          <!-- Order Summary Card -->
          <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: 0.85rem; font-size: 0.85rem; margin-top: 1.25rem;">
            <div style="font-weight: 700; margin-bottom: 0.4rem;">Order Items:</div>
            ${(o.items || []).map(it => `
              <div style="display: flex; justify-content: space-between; padding: 0.2rem 0;">
                <span>${escapeHtml(it.product_name)} × <strong>${it.quantity}</strong></span>
                <span>₹${Number(it.subtotal).toFixed(2)}</span>
              </div>
            `).join("")}
            <div style="border-top: 1px dashed var(--border-dark); margin-top: 0.5rem; padding-top: 0.5rem; display: flex; justify-content: space-between; font-weight: 800;">
              <span>Total Paid:</span>
              <span>₹${Number(o.total_amount).toFixed(2)}</span>
            </div>
          </div>
        </div>
      `;

      body.innerHTML = timelineHtml;
    }
  } catch (err) {
    if (!isSilent) console.error(err);
  }
}

// =========================================================================
// 5. ORDER HISTORY & REWARDS
// =========================================================================

async function loadOrderHistory(isSilent = false) {
  if (!currentShopper) return;
  const container = document.getElementById("shopperOrderHistoryContainer");
  const badge = document.getElementById("activeOrdersBadge");
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/orders/shopper/history?shopper_id=${currentShopper.id}`);
    const data = await res.json();

    if (res.ok && data.success && data.orders) {
      const activeCount = data.orders.filter(o => !['delivered', 'rejected', 'cancelled'].includes(o.status.toLowerCase())).length;
      if (badge) {
        if (activeCount > 0) {
          badge.textContent = `${activeCount} Active`;
          badge.style.display = "inline-flex";
        } else {
          badge.style.display = "none";
        }
      }

      if (data.orders.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">📜</div>
            <div style="font-weight: 700; margin-bottom: 0.3rem;">No Orders Yet</div>
            <p style="font-size: 0.85rem;">Place your first order to start earning Agora Loyalty Points!</p>
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

      container.innerHTML = data.orders.map(o => {
        const orderId = o.id || o.orderId;
        const status = (o.status || "pending").toLowerCase();
        const badgeClass = statusBadgeStyles[status] || "badge-secondary";
        const items = o.items || [];
        const quantity = items.reduce((s, it) => s + it.quantity, 0);

        return `
          <div class="card" style="margin-bottom: 0.9rem; border-left: 4px solid var(--primary);">
            <div class="card-header" style="flex-wrap: wrap; gap: 0.4rem; padding-bottom: 0.4rem;">
              <div>
                <strong style="font-size: 1rem;">${o.order_number}</strong>
                <span class="badge ${badgeClass}" style="margin-left: 0.4rem;">${status.replace(/_/g, ' ')}</span>
              </div>
              <div style="font-weight: 800; font-size: 1.1rem; color: var(--primary);">₹${Number(o.total_amount || o.total).toFixed(2)}</div>
            </div>

            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.5rem;">
              Store: <strong>${escapeHtml(o.shop_name)}</strong> • ${o.collect_option === 'home_delivery' ? '🛵 Home Delivery' : '🏬 Pickup'} • ${o.created_at || o.time}
            </div>

            <div style="background: var(--bg-subtle); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); font-size: 0.84rem; margin-bottom: 0.6rem;">
              <div style="font-weight: 600; margin-bottom: 0.2rem;">Items (${quantity}):</div>
              ${items.map(it => `• ${escapeHtml(it.product_name)} × <strong>${it.quantity}</strong> (₹${Number(it.subtotal).toFixed(2)})`).join("<br>")}
            </div>

            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;">
              <button class="btn btn-primary btn-sm" onclick="hideModal('orderHistoryModal'); openOrderTrackingModal(${orderId})">
                📍 Track Live Timeline
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    if (!isSilent) console.error(err);
  }
}

async function loadLoyaltyPoints() {
  if (!currentShopper) return;
  try {
    const res = await fetch(`${API_BASE}/shopper-portal/loyalty-summary?shopper_id=${currentShopper.id}`);
    const data = await res.json();
    if (res.ok && data.success) {
      const balance = data.points_balance || 0;
      const bEl = document.getElementById("shopperPointsBalance");
      if (bEl) bEl.textContent = balance;
      const lEl = document.getElementById("loyaltyBalanceLarge");
      if (lEl) lEl.textContent = balance;
    }
  } catch (err) {}
}

async function loadNotifications() {
  if (!currentShopper) return;
  try {
    const res = await fetch(`${API_BASE}/shopper-portal/notifications?shopper_id=${currentShopper.id}`);
    const data = await res.json();
    if (res.ok && data.success && data.notifications) {
      const notifList = document.getElementById("notificationsList");
      const badge = document.getElementById("notifBadge");
      const unreadCount = data.notifications.filter(n => !n.is_read).length;

      if (badge) {
        if (unreadCount > 0) {
          badge.textContent = unreadCount;
          badge.style.display = "inline-flex";
        } else {
          badge.style.display = "none";
        }
      }

      if (notifList) {
        if (data.notifications.length === 0) {
          notifList.innerHTML = `<div class="empty-state">No new notifications.</div>`;
        } else {
          notifList.innerHTML = data.notifications.map(n => `
            <div class="card" style="margin-bottom: 0.5rem; padding: 0.75rem; border-left: 3px solid #3b82f6;">
              <div style="font-weight: 700; font-size: 0.9rem;">${escapeHtml(n.title)}</div>
              <div style="font-size: 0.82rem; color: var(--text-body); margin-top: 0.2rem;">${escapeHtml(n.message)}</div>
            </div>
          `).join("");
        }
      }
    }
  } catch (err) {}
}

// =========================================================================
// 6. EVENT LISTENERS & MODAL UTILITIES
// =========================================================================

function setupEventListeners() {
  const searchInput = document.getElementById("shopperSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const val = e.target.value.trim();
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        if (val.length >= 1) {
          fetchSearchSuggestions(val);
        } else {
          hideSearchDropdown();
        }
        performSearch(val);
      }, 300); // Strict 300ms debounce
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        hideSearchDropdown();
        performSearch(e.target.value.trim());
      }
    });

    document.addEventListener("click", (e) => {
      const wrapper = document.querySelector(".search-hero");
      if (wrapper && !wrapper.contains(e.target)) {
        hideSearchDropdown();
      }
    });
  }
}

function showModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.add("active");
    if (id === "orderHistoryModal") loadOrderHistory();
    if (id === "loyaltyModal") loadLoyaltyPoints();
    if (id === "notificationsModal") loadNotifications();
  }
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
