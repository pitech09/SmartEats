// static/js/cart.js
(function () {
  // Socket.IO connection with reconnection logic
  const socket = io({
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000
  });

  // Audio unlock overlay
  function createAudioOverlay() {
    if (document.getElementById('enable-audio-overlay')) return;
    const ov = document.createElement('div');
    ov.id = 'enable-audio-overlay';
    ov.style = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;';
    ov.innerHTML = '<button id="enable-audio-btn" class="btn btn-success btn-lg">Enable Sound Notifications</button>';
    document.body.appendChild(ov);

    document.getElementById('enable-audio-btn').addEventListener('click', function() {
      const ids = ['new_order','order_update','order_ready'];
      ids.forEach(id => {
        const a = document.getElementById(id);
        if (a) {
          a.play().then(()=>a.pause()).catch(()=>{ /* ignore */ });
        }
      });
      ov.style.display = 'none';
      window.__audioUnlocked = true;
    }, { once: true });
  }

  // If audio elements exist, show overlay
  if (document.getElementById('new_order')) {
    createAudioOverlay();
  } else {
    window.__audioUnlocked = true; // nothing to unlock
  }

  // Re-join user's room on connect
  socket.on('connect', () => {
    // Attempt to get the user id rendered to page by template
    const el = document.querySelector('[data-current-user-id]');
    if (el) {
      const uid = el.getAttribute('data-current-user-id');
      if (uid) socket.emit('join_room', uid);
    } else {
      // optional: template can put <meta name="current-user-id" content="{{ current_user.id }}">
      const meta = document.querySelector('meta[name="current-user-id"]');
      if (meta && meta.content) socket.emit('join_room', meta.content);
    }
  });

  // Handle cart_updated socket events
  socket.on('cart_updated', function (data) {
    try {
      if (data.cart_count !== undefined) {
        const el = document.getElementById('cart-count');
        if (el) el.textContent = data.cart_count;
      }
      if (data.cart_total !== undefined) {
        const totalEl = document.getElementById('total-price');
        if (totalEl) {
          totalEl.dataset.base = parseFloat(data.cart_total).toFixed(2);
          // reflect delivery option
          const deliveryOption = document.querySelector("input[name='deliverymethod']:checked");
          const newTotal = calculateDisplayedTotal(parseFloat(totalEl.dataset.base), deliveryOption && deliveryOption.value === 'delivery');
          totalEl.innerText = 'M' + newTotal.toFixed(2);
        }
      }

      // Play a sound if available and audio unlocked
      if (window.__audioUnlocked) {
        const audio = document.getElementById('new_order') || document.getElementById('order_update');
        if (audio) {
          audio.currentTime = 0;
          audio.play().catch(()=>{});
        }
      }
    } catch (e) {
      console.debug('cart_updated handler error', e);
    }
  });

  // Utility: calculate visible total with delivery flag
  function calculateDisplayedTotal(base, deliverySelected) {
    const deliveryFee = 6.00; // change if you use store-specific fees
    return deliverySelected ? (base + deliveryFee) : base;
  }

  // Delivery option change -> update total display
  function bindDeliveryOptions() {
    document.querySelectorAll('.delivery-option').forEach(opt => {
      opt.addEventListener('change', function () {
        const totalEl = document.getElementById('total-price');
        if (!totalEl) return;
        const base = parseFloat(totalEl.dataset.base) || 0;
        const isDelivery = document.querySelector("input[name='deliverymethod']:checked") && document.querySelector("input[name='deliverymethod']:checked").value === 'delivery';
        totalEl.innerText = 'M' + calculateDisplayedTotal(base, isDelivery).toFixed(2);
      });
    });
  }
  bindDeliveryOptions();

  // Remove item via AJAX
  function bindRemoveButtons() {
    document.querySelectorAll('.remove-item').forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const itemId = this.dataset.id;
        fetch(`/remove_from_cart_ajax/${itemId}`, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
          }
        })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            // remove row from DOM
            const row = this.closest('tr');
            if (row) row.remove();

            // update base total and cart count (server also emits but update immediately)
            const totalEl = document.getElementById('total-price');
            if (totalEl && data.cart_total !== undefined) {
              totalEl.dataset.base = parseFloat(data.cart_total).toFixed(2);
              const isDelivery = document.querySelector("input[name='deliverymethod']:checked") && document.querySelector("input[name='deliverymethod']:checked").value === 'delivery';
              totalEl.innerText = 'M' + calculateDisplayedTotal(parseFloat(totalEl.dataset.base), isDelivery).toFixed(2);
            }
            const cartCnt = document.getElementById('cart-count');
            if (cartCnt && data.cart_count !== undefined) cartCnt.textContent = data.cart_count;
          }
        })
        .catch(err => console.debug('remove ajax error', err));
      });
    });
  }
  bindRemoveButtons();

  // Attach to add-to-cart buttons (if any on page)
  function bindAddToCartButtons() {
    document.querySelectorAll('.add-to-cart-btn').forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const productId = this.dataset.id;
        fetch('/add_to_cart_ajax', {
          method: 'POST',
          headers: {
            'Content-Type':'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ product_id: productId })
        })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            // update cart count quickly — server will also emit
            const cartCnt = document.getElementById('cart-count');
            if (cartCnt && data.cart_count !== undefined) cartCnt.textContent = data.cart_count;

            // optionally play sound
            if (window.__audioUnlocked) {
              const audio = document.getElementById('new_order') || document.getElementById('order_update');
              if (audio) { audio.currentTime = 0; audio.play().catch(()=>{}); }
            }
          }
        })
        .catch(err => console.debug('add to cart error', err));
      });
    });
  }
  bindAddToCartButtons();

  // Rebind after AJAX DOM changes (if you remove nodes)
  // If you use frameworks you'll likely re-run bindRemoveButtons() after DOM updates
  window.rebindCartHandlers = function () {
    bindRemoveButtons();
    bindDeliveryOptions();
    bindAddToCartButtons();
  };

})();
