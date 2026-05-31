/* ==============================================================
   SmartEats — Apple-Inspired UI Interactions
   ============================================================== */

document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  // ---- Navbar scroll effect ----
  const navbar = document.querySelector('.apple-navbar');
  if (navbar) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 20) {
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    });
  }

  // ---- Mobile drawer toggle ----
  const drawerToggle = document.getElementById('drawerToggle');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const drawer = document.getElementById('mobileDrawer');
  const drawerClose = document.getElementById('drawerClose');

  function openDrawer() {
    if (drawerOverlay && drawer) {
      drawerOverlay.classList.add('visible');
      drawer.classList.add('visible');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeDrawer() {
    if (drawerOverlay && drawer) {
      drawerOverlay.classList.remove('visible');
      drawer.classList.remove('visible');
      document.body.style.overflow = '';
    }
  }

  if (drawerToggle) drawerToggle.addEventListener('click', openDrawer);
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

  // Close drawer on Escape
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeDrawer();
  });

  // ---- Apple-style search with live suggestions ----
  const searchInputs = document.querySelectorAll('.apple-search-input');
  searchInputs.forEach(function(input) {
    const resultsContainer = input.closest('.apple-search')?.querySelector('.apple-search-results');
    
    input.addEventListener('input', function() {
      const query = this.value.trim();
      if (query.length < 2) {
        if (resultsContainer) resultsContainer.classList.remove('visible');
        return;
      }
      
      // Show loading state
      if (resultsContainer) {
        resultsContainer.innerHTML = '<div class="apple-search-result-item" style="justify-content:center;"><div class="apple-skeleton" style="width:100%;height:40px;"></div></div>';
        resultsContainer.classList.add('visible');
      }

      fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (!resultsContainer) return;
          resultsContainer.innerHTML = '';
          
          if (data.restaurants && data.restaurants.length > 0) {
            data.restaurants.forEach(function(r) {
              const item = document.createElement('a');
              item.href = r.url || '#';
              item.className = 'apple-search-result-item';
              item.innerHTML = '<i class="fas fa-store" style="color:var(--color-accent);"></i> <div><strong>' + r.name + '</strong><br><span class="text-caption">' + (r.district || '') + '</span></div>';
              resultsContainer.appendChild(item);
            });
          }
          
          if (data.meals && data.meals.length > 0) {
            data.meals.forEach(function(m) {
              const item = document.createElement('a');
              item.href = m.url || '#';
              item.className = 'apple-search-result-item';
              item.innerHTML = '<img src="' + (m.image || '/static/css/images/default.png') + '" alt="' + m.name + '"> <div><strong>' + m.name + '</strong><br><span class="text-caption">' + (m.price || '') + '</span></div>';
              resultsContainer.appendChild(item);
            });
          }
          
          if ((!data.restaurants || data.restaurants.length === 0) && (!data.meals || data.meals.length === 0)) {
            resultsContainer.innerHTML = '<div class="apple-search-result-item" style="justify-content:center;color:var(--color-text-secondary);">No results found</div>';
          }
          
          resultsContainer.classList.add('visible');
        })
        .catch(function() {
          if (resultsContainer) {
            resultsContainer.innerHTML = '<div class="apple-search-result-item" style="justify-content:center;color:var(--color-text-secondary);">Something went wrong</div>';
          }
        });
    });

    // Close on blur
    input.addEventListener('blur', function() {
      setTimeout(function() {
        if (resultsContainer) resultsContainer.classList.remove('visible');
      }, 200);
    });

    // Close on Escape
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && resultsContainer) {
        resultsContainer.classList.remove('visible');
        this.blur();
      }
    });
  });

  // ---- Smooth quantity controls ----
  document.querySelectorAll('.cart-qty-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const delta = this.dataset.action === 'increase' ? 1 : -1;
      const input = this.closest('.cart-item-actions')?.querySelector('.cart-qty-value');
      if (!input) return;
      
      let val = parseInt(input.textContent) || 1;
      val = Math.max(1, val + delta);
      input.textContent = val;

      // Trigger update via AJAX
      const itemId = this.dataset.itemId;
      if (itemId) {
        fetch('/update_cart_quantity', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: itemId, quantity: val })
        }).then(function(r) { return r.json(); }).then(function(data) {
          if (data.cart_total !== undefined) {
            const totalEl = document.getElementById('cart-total-amount');
            if (totalEl) totalEl.textContent = 'M' + data.cart_total.toFixed(2);
          }
          if (data.cart_count !== undefined) {
            const countEl = document.getElementById('cart-count');
            if (countEl) countEl.textContent = data.cart_count;
            // Update bottom nav count
            document.querySelectorAll('.nav-count').forEach(function(el) {
              el.textContent = data.cart_count;
            });
          }
        }).catch(function(err) { console.error('Cart update failed:', err); });
      }
    });
  });

  // ---- Add to cart with animation ----
  document.querySelectorAll('.meal-card-add, .add-to-cart-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const productId = this.dataset.productId;
      if (!productId) return;

      // Show loading state
      const originalText = this.innerHTML;
      this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
      this.disabled = true;

      fetch('/add_to_cart_ajax', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
      }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
          // Update cart count everywhere
          const countEl = document.getElementById('cart-count');
          if (countEl) countEl.textContent = data.cart_count || 0;
          document.querySelectorAll('.nav-count').forEach(function(el) {
            el.textContent = data.cart_count || 0;
          });

          // Flash feedback on button
          btn.innerHTML = '<i class="fas fa-check"></i> Added';
          btn.classList.add('added');
          setTimeout(function() {
            btn.innerHTML = '<i class="fas fa-plus"></i> Add';
            btn.classList.remove('added');
            btn.disabled = false;
          }, 1500);

          // Show toast notification
          showToast('Item added to cart', 'success');
        }
      }).catch(function() {
        btn.innerHTML = originalText;
        btn.disabled = false;
        showToast('Failed to add item', 'error');
      });
    });
  });

  // ---- Remove from cart ----
  document.querySelectorAll('.remove-from-cart').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const itemId = this.dataset.itemId;
      if (!itemId) return;

      fetch('/remove_from_cart_ajax/' + itemId, {
        method: 'POST'
      }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
          // Remove the cart item row with animation
          const row = btn.closest('.cart-item');
          if (row) {
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '0';
            row.style.transform = 'translateX(20px)';
            setTimeout(function() { row.remove(); }, 300);
          }

          // Update totals
          const totalEl = document.getElementById('cart-total-amount');
          if (totalEl) totalEl.textContent = 'M' + (data.cart_total || 0).toFixed(2);
          
          const countEl = document.getElementById('cart-count');
          if (countEl) countEl.textContent = data.cart_count || 0;
          document.querySelectorAll('.nav-count').forEach(function(el) {
            el.textContent = data.cart_count || 0;
          });

          // Show empty state if cart is empty
          if (data.cart_count === 0) {
            const cartContainer = document.getElementById('cart-items-container');
            if (cartContainer) {
              cartContainer.innerHTML = '<div class="apple-empty"><div class="apple-empty-icon"><i class="fas fa-shopping-bag"></i></div><div class="apple-empty-title">Your cart is empty</div><div class="apple-empty-text">Add some delicious meals to get started.</div><a href="/menu/1" class="apple-btn apple-btn-primary">Browse Menu</a></div>';
            }
          }

          showToast('Item removed from cart', 'info');
        }
      }).catch(function() {
        showToast('Failed to remove item', 'error');
      });
    });
  });

  // ---- Toast notification system ----
  function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'apple-toast ' + type;
    
    const icons = {
      success: 'fas fa-check-circle',
      error: 'fas fa-exclamation-circle',
      warning: 'fas fa-exclamation-triangle',
      info: 'fas fa-info-circle'
    };
    
    toast.innerHTML = '<i class="' + (icons[type] || icons.info) + '" style="font-size:1.25rem;"></i> ' + message;
    container.appendChild(toast);

    setTimeout(function() {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(function() { toast.remove(); }, 300);
    }, 3500);
  }

  // Expose for global use
  window.showToast = showToast;

  // ---- Image lazy loading ----
  const lazyImages = document.querySelectorAll('img[loading="lazy"]');
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src || img.src;
          img.classList.remove('lazy');
          imageObserver.unobserve(img);
        }
      });
    });

    lazyImages.forEach(function(img) { imageObserver.observe(img); });
  }

  // ---- Active nav link ----
  const currentPath = window.location.pathname;
  document.querySelectorAll('.apple-nav-link, .apple-bottom-nav-item, .apple-drawer-nav-item').forEach(function(link) {
    const href = link.getAttribute('href');
    if (href && href !== '#' && currentPath.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // ---- Keyboard navigation enhancements ----
  document.addEventListener('keydown', function(e) {
    // Ctrl+K or / to focus search
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName))) {
      e.preventDefault();
      const searchInput = document.querySelector('.apple-search-input');
      if (searchInput) searchInput.focus();
    }
  });

  // ---- Category chip selection ----
  document.querySelectorAll('.category-chip').forEach(function(chip) {
    chip.addEventListener('click', function() {
      const parent = this.closest('.category-chips');
      if (parent) {
        parent.querySelectorAll('.category-chip').forEach(function(c) { c.classList.remove('active'); });
      }
      this.classList.toggle('active');
      
      // Navigate to category filter
      const categoryId = this.dataset.categoryId;
      if (categoryId) {
        const baseUrl = window.location.pathname;
        window.location.href = baseUrl + '?category=' + categoryId;
      }
    });
  });

  // ---- Radio group selection ----
  document.querySelectorAll('.apple-radio').forEach(function(radio) {
    radio.addEventListener('click', function() {
      const parent = this.closest('.apple-radio-group');
      if (parent) {
        parent.querySelectorAll('.apple-radio').forEach(function(r) { r.classList.remove('selected'); });
      }
      this.classList.add('selected');
      
      const radioInput = this.querySelector('input[type="radio"]');
      if (radioInput) radioInput.checked = true;
    });
  });

  // ---- Payment method selection ----
  const paymentRadios = document.querySelectorAll('.payment-method-radio');
  paymentRadios.forEach(function(radio) {
    radio.addEventListener('change', function() {
      document.querySelectorAll('.payment-detail').forEach(function(d) { d.style.display = 'none'; });
      const detail = document.getElementById('payment-' + this.value);
      if (detail) detail.style.display = 'block';
    });
  });

  // ---- Order tracking: auto-refresh driver position ----
  const orderStatusEl = document.getElementById('orderStatus');
  if (orderStatusEl) {
    const orderId = orderStatusEl.dataset.orderId;
    if (orderId) {
      setInterval(function() {
        fetch('/api/order-status/' + orderId)
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.status) orderStatusEl.textContent = data.status;
            if (data.eta) {
              const etaEl = document.getElementById('driverEta');
              if (etaEl) etaEl.textContent = data.eta;
            }
            if (data.progress !== undefined) {
              const progressBar = document.getElementById('deliveryProgress');
              if (progressBar) progressBar.style.width = data.progress + '%';
            }
          }).catch(function() {});
      }, 10000);
    }
  }

  // ---- Star rating interaction ----
  document.querySelectorAll('.star-rating-input i').forEach(function(star) {
    star.addEventListener('click', function() {
      const value = this.dataset.value;
      const parent = this.closest('.star-rating-input');
      parent.querySelectorAll('i').forEach(function(s) {
        s.classList.remove('fas');
        s.classList.add('far');
        if (parseInt(s.dataset.value) <= parseInt(value)) {
          s.classList.remove('far');
          s.classList.add('fas');
        }
      });
      const input = parent.querySelector('input[type="hidden"]');
      if (input) input.value = value;
    });

    star.addEventListener('mouseenter', function() {
      const value = this.dataset.value;
      const parent = this.closest('.star-rating-input');
      parent.querySelectorAll('i').forEach(function(s) {
        if (parseInt(s.dataset.value) <= parseInt(value)) {
          s.classList.add('hover');
        }
      });
    });

    star.addEventListener('mouseleave', function() {
      const parent = this.closest('.star-rating-input');
      parent.querySelectorAll('i').forEach(function(s) {
        s.classList.remove('hover');
      });
    });
  });

  // ---- Coupon application ----
  const couponForm = document.getElementById('couponForm');
  if (couponForm) {
    couponForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const code = this.querySelector('input').value.trim();
      if (!code) return;

      fetch('/apply-coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
      }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
          showToast('Coupon applied! ' + (data.discount || ''), 'success');
          if (data.new_total !== undefined) {
            const totalEl = document.getElementById('cart-total-amount');
            if (totalEl) totalEl.textContent = 'M' + data.new_total.toFixed(2);
          }
        } else {
          showToast(data.message || 'Invalid coupon code', 'warning');
        }
      }).catch(function() {
        showToast('Error applying coupon', 'error');
      });
    });
  }

  // ---- Flash messages auto-dismiss ----
  const flashMessages = document.querySelectorAll('.apple-toast-container .apple-toast');
  flashMessages.forEach(function(msg) {
    setTimeout(function() {
      msg.style.opacity = '0';
      msg.style.transform = 'translateX(100%)';
      msg.style.transition = 'all 0.3s ease';
      setTimeout(function() { msg.remove(); }, 300);
    }, 4000);
  });

  // ---- Map initialization for delivery tracking ----
  const mapContainer = document.getElementById('trackingMap');
  if (mapContainer && typeof L !== 'undefined') {
    const map = L.map(mapContainer).setView([-29.3, 27.5], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap'
    }).addTo(map);

    // Add driver marker (movable)
    const driverIcon = L.divIcon({
      className: 'driver-marker',
      html: '<div style="background:var(--color-accent);width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
    const driverMarker = L.marker([-29.3, 27.5], { icon: driverIcon }).addTo(map);

    const orderId = mapContainer.dataset.orderId;
    if (orderId) {
      setInterval(function() {
        fetch('/api/driver-location/' + orderId)
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.lat && data.lng) {
              driverMarker.setLatLng([data.lat, data.lng]);
              map.setView([data.lat, data.lng], 13);
            }
          }).catch(function() {});
      }, 15000);
    }
  }

  console.log('🍎 SmartEats Apple UI initialized');
});