/* ==============================================================
   SmartEats — Store POS System
   ============================================================== */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {

    // --- Elements ---
    const cartEl = document.getElementById('pos-cart');
    const totalEl = document.getElementById('pos-total');
    const cartCountEl = document.getElementById('pos-cart-count');
    const cartCountHeaderEl = document.getElementById('pos-cart-count-header');
    const emptyCartEl = document.getElementById('pos-empty-cart');
    const payBtn = document.getElementById('pos-pay-btn');
    const paymentSelect = document.getElementById('pos-payment');
    const searchInput = document.getElementById('pos-search');
    const categoryFilter = document.getElementById('pos-category');
    const productsContainer = document.getElementById('pos-products');
    const receiptModalEl = document.getElementById('posReceiptModal');
    const receiptBody = document.getElementById('receiptBody');
    const receiptTotal = document.getElementById('receiptTotal');
    const receiptPayment = document.getElementById('receiptPayment');
    const receiptDate = document.getElementById('receiptDate');
    const receiptId = document.getElementById('receiptId');
    const receiptStoreName = document.getElementById('receiptStoreName');
    const receiptAmountPaid = document.getElementById('receiptAmountPaid');
    const receiptChange = document.getElementById('receiptChange');
    const amountPaidInput = document.getElementById('pos-amount-paid');
    const changeDueEl = document.getElementById('pos-change-due');
    const changeDueSection = document.getElementById('change-due-section');

    let cart = [];

    // --- Helper: get cart total ---
    function getCartTotal() {
      var total = 0;
      cart.forEach(function(item) {
        total += item.price * item.quantity;
      });
      return total;
    }

    // --- Helper: update change display ---
    function updateChangeDisplay() {
      if (!amountPaidInput || !changeDueEl || !changeDueSection) return;
      var total = getCartTotal();
      var paid = parseFloat(amountPaidInput.value) || 0;
      if (paid > 0) {
        changeDueSection.classList.remove('d-none');
        var change = paid - total;
        changeDueEl.textContent = change >= 0 ? change.toFixed(2) : '0.00';
      } else {
        changeDueSection.classList.add('d-none');
        changeDueEl.textContent = '0.00';
      }
    }

    // Listen for amount paid input
    if (amountPaidInput) {
      amountPaidInput.addEventListener('input', updateChangeDisplay);
    }

    // --- Add Item via event delegation ---
    if (productsContainer) {
      productsContainer.addEventListener('click', function(e) {
        var btn = e.target.closest('.pos-add-btn');
        if (!btn) return;
        var card = btn.closest('.pos-product-card');
        if (!card) return;
        var id = parseInt(card.dataset.id);
        var name = card.dataset.name;
        var price = parseFloat(card.dataset.price);
        if (!id || !name || isNaN(price)) return;

        var item = cart.find(function(i) { return i.product_id === id; });
        if (item) {
          item.quantity++;
        } else {
          cart.push({ product_id: id, name: name, price: price, quantity: 1 });
        }
        renderCart();

        // Flash feedback
        btn.innerHTML = '<i class="fas fa-check"></i>';
        btn.classList.add('btn-success');
        setTimeout(function() {
          btn.innerHTML = '<i class="fas fa-plus"></i>';
          btn.classList.remove('btn-success');
        }, 600);
      });
    }

    // --- Update Qty via event delegation ---
    if (cartEl) {
      cartEl.addEventListener('click', function(e) {
        var btn = e.target.closest('button');
        if (!btn) return;
        var delta = 0;
        if (btn.classList.contains('qty-inc')) delta = 1;
        else if (btn.classList.contains('qty-dec')) delta = -1;
        if (delta === 0) return;

        var li = btn.closest('li');
        if (!li) return;
        var id = parseInt(li.dataset.id);
        if (!id) return;

        var item = cart.find(function(i) { return i.product_id === id; });
        if (!item) return;
        item.quantity += delta;
        if (item.quantity <= 0) {
          cart = cart.filter(function(i) { return i.product_id !== id; });
        }
        renderCart();
      });
    }

    // --- Filter & Search ---
    function filterProducts() {
      if (!productsContainer) return;
      var query = searchInput ? searchInput.value.toLowerCase().trim() : '';
      var catId = categoryFilter ? categoryFilter.value : '';

      var cards = productsContainer.querySelectorAll('.pos-product-card');
      cards.forEach(function(card) {
        var name = (card.dataset.name || '').toLowerCase();
        var cat = card.dataset.category || '';
        var matchesSearch = !query || name.indexOf(query) !== -1;
        var matchesCat = !catId || cat === catId;
        card.style.display = (matchesSearch && matchesCat) ? '' : 'none';
      });
    }

    if (categoryFilter) {
      categoryFilter.addEventListener('change', filterProducts);
    }
    if (searchInput) {
      searchInput.addEventListener('input', filterProducts);
    }

    // --- Render Cart ---
    function renderCart() {
      if (!cartEl) return;
      var total = 0;
      var count = 0;
      cartEl.innerHTML = '';

      if (cart.length === 0) {
        if (emptyCartEl) emptyCartEl.style.display = 'block';
        if (totalEl) totalEl.textContent = '0.00';
        if (cartCountEl) cartCountEl.textContent = '0';
        if (cartCountHeaderEl) cartCountHeaderEl.textContent = '0 items';
        if (payBtn) payBtn.disabled = true;
        changeDueSection.classList.add('d-none');
        return;
      }

      if (emptyCartEl) emptyCartEl.style.display = 'none';
      if (payBtn) payBtn.disabled = false;

      cart.forEach(function(item) {
        total += item.price * item.quantity;
        count += item.quantity;

        var li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.dataset.id = item.product_id;
        li.innerHTML =
          '<div>' +
            '<strong>' + item.name + '</strong><br>' +
            '<small class="text-muted">M' + item.price.toFixed(2) + ' each</small>' +
          '</div>' +
          '<div class="d-flex align-items-center">' +
            '<button class="btn btn-sm btn-outline-secondary me-1 qty-dec" type="button">' +
              '<i class="fas fa-minus"></i>' +
            '</button>' +
            '<span class="fw-bold mx-2">' + item.quantity + '</span>' +
            '<button class="btn btn-sm btn-outline-secondary me-2 qty-inc" type="button">' +
              '<i class="fas fa-plus"></i>' +
            '</button>' +
            '<span class="fw-bold text-primary">M' + (item.price * item.quantity).toFixed(2) + '</span>' +
          '</div>';
        cartEl.appendChild(li);
      });

      if (totalEl) totalEl.textContent = total.toFixed(2);
      if (cartCountEl) cartCountEl.textContent = count;
      if (cartCountHeaderEl) cartCountHeaderEl.textContent = count + ' items';

      // Recalculate change display after cart changes
      updateChangeDisplay();
    }

    // --- Submit Order ---
    function submitOrder() {
      if (cart.length === 0) return;

      // Validate amount paid
      var total = getCartTotal();
      var amountPaid = parseFloat(amountPaidInput ? amountPaidInput.value : 0) || 0;
      var paymentMethod = paymentSelect ? paymentSelect.value : 'Cash';

      // For cash payments, validate amount paid is sufficient
      if (paymentMethod === 'Cash' && amountPaid < total) {
        alert('Amount paid (M' + amountPaid.toFixed(2) + ') is less than the total (M' + total.toFixed(2) + '). Please enter a valid amount.');
        if (amountPaidInput) amountPaidInput.focus();
        return;
      }

      // For non-cash, auto-set amount paid to total
      if (paymentMethod !== 'Cash') {
        amountPaid = total;
      }

      var change = amountPaid - total;

      // Show spinner on button
      if (payBtn) {
        payBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Processing...';
        payBtn.disabled = true;
      }

      var url = window.POS_SUBMIT_URL;

      var headers = { 'Content-Type': 'application/json' };
      // Add CSRF token if available
      if (window.POS_CSRF_TOKEN) {
        headers['X-CSRFToken'] = window.POS_CSRF_TOKEN;
      }

      fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          items: cart,
          payment: paymentMethod,
          amount_paid: amountPaid,
          change: change
        })
      })
      .then(function(r) {
        // First check response type before trying to parse
        var contentType = r.headers.get('content-type') || '';
        if (contentType.indexOf('application/json') === -1) {
          // Not JSON - show raw text for debugging
          return r.text().then(function(text) {
            throw new Error('Server returned non-JSON response (status ' + r.status + '): ' + text.substring(0, 500));
          });
        }
        return r.json();
      })
      .then(function(res) {
        if (res.success) {
          showReceipt(res, amountPaid, change);
          cart = [];
          renderCart();
          // Reset amount paid
          if (amountPaidInput) amountPaidInput.value = '';
        } else {
          alert('Error: ' + (res.error || 'Could not complete order'));
        }
      })
      .catch(function(err) {
        alert('POS Error: ' + err.message);
        console.error('POS Error:', err);
      })
      .finally(function() {
        if (payBtn) {
          payBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i> Complete Sale';
          payBtn.disabled = false;
        }
      });
    }

    // Wire up Pay button
    if (payBtn) {
      payBtn.addEventListener('click', submitOrder);
    }

    // --- Show Receipt Modal ---
    function showReceipt(data, amountPaid, change) {
      if (!receiptModalEl) return;

      var modal = new bootstrap.Modal(receiptModalEl);
      var now = new Date();
      var dateStr = now.toLocaleDateString() + ' ' + now.toLocaleTimeString();
      var orderId = data.order_id || 'POS-' + Math.random().toString(36).substr(2, 8).toUpperCase();

      if (receiptStoreName) receiptStoreName.textContent = data.store_name || 'Store';
      if (receiptId) receiptId.textContent = orderId;
      if (receiptDate) receiptDate.textContent = dateStr;
      if (receiptPayment) receiptPayment.textContent = paymentSelect ? paymentSelect.value : 'Cash';
      if (receiptTotal) receiptTotal.textContent = data.total ? data.total.toFixed(2) : '0.00';
      if (receiptAmountPaid) receiptAmountPaid.textContent = (amountPaid || 0).toFixed(2);
      if (receiptChange) receiptChange.textContent = (change >= 0 ? change : 0).toFixed(2);

      if (receiptBody && data.items) {
        receiptBody.innerHTML = '';
        data.items.forEach(function(item) {
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td>' + item.name + '</td>' +
            '<td>' + item.quantity + '</td>' +
            '<td>M' + item.price.toFixed(2) + '</td>' +
            '<td class="text-end">M' + (item.price * item.quantity).toFixed(2) + '</td>';
          receiptBody.appendChild(tr);
        });
      }

      modal.show();
    }

    // --- Init rendering ---
    renderCart();
  });

})();