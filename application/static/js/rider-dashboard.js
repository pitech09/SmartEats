/* ==============================================================
   SmartEats — Rider Dashboard UI Interactions
   ============================================================== */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // ── Toast helper ──
    function showToast(msg) {
      var t = document.getElementById('rd-toast');
      if (!t) return;
      t.textContent = msg;
      t.classList.add('show');
      clearTimeout(t._timer);
      t._timer = setTimeout(function () { t.classList.remove('show'); }, 2200);
    }

    // ── Online / Offline toggle ──
    var toggle = document.getElementById('rd-online-toggle');
    var toggleLabel = document.getElementById('rd-toggle-label');
    var statusDot = document.getElementById('rd-status-dot');
    var statusText = document.getElementById('rd-status-text');

    if (toggle) {
      toggle.addEventListener('click', function () {
        var isOnline = toggle.classList.toggle('active');
        if (toggleLabel) {
          toggleLabel.textContent = isOnline ? 'Online' : 'Offline';
          toggleLabel.classList.toggle('active-label', isOnline);
        }
        if (statusDot) statusDot.classList.toggle('offline', !isOnline);
        if (statusText) statusText.textContent = isOnline ? 'Available for deliveries' : 'You are offline';
        showToast(isOnline ? 'You are now online' : 'You are now offline');
        // Persist preference
        try { localStorage.setItem('rd_online', isOnline ? '1' : '0'); } catch (e) {}
      });
      // Restore
      try {
        if (localStorage.getItem('rd_online') === '0') {
          toggle.click(); // toggle off
        }
      } catch (e) {}
    }

    // ── Sound toggle ──
    var soundBtn = document.getElementById('rd-sound-toggle');
    if (soundBtn) {
      soundBtn.addEventListener('click', function () {
        var muted = soundBtn.classList.toggle('muted');
        soundBtn.querySelector('span').textContent = muted ? 'Notifications Off' : 'Notifications On';
        soundBtn.querySelector('i').className = muted ? 'fas fa-bell-slash' : 'fas fa-bell';
        try { localStorage.setItem('smarteats_delivery_sound', muted ? 'off' : 'on'); } catch (e) {}
        showToast(muted ? 'Notifications muted' : 'Notifications enabled');
      });
      // Restore
      try {
        if (localStorage.getItem('smarteats_delivery_sound') === 'off') {
          soundBtn.classList.add('muted');
          soundBtn.querySelector('span').textContent = 'Notifications Off';
          soundBtn.querySelector('i').className = 'fas fa-bell-slash';
        }
      } catch (e) {}
    }

    // ── Elapsed time counter ──
    function updateElapsed() {
      document.querySelectorAll('.rd-time-elapsed').forEach(function (el) {
        var iso = el.dataset.created;
        if (!iso) return;
        var created = new Date(iso);
        var diffMs = Date.now() - created.getTime();
        var diffMin = Math.floor(diffMs / 60000);
        var text;
        if (diffMin < 1) text = 'Just now';
        else if (diffMin < 60) text = diffMin + 'm ago';
        else if (diffMin < 1440) text = Math.floor(diffMin / 60) + 'h ' + (diffMin % 60) + 'm ago';
        else text = Math.floor(diffMin / 1440) + 'd ago';
        var span = el.querySelector('.rd-time-text');
        if (span) span.textContent = text;
      });
    }
    updateElapsed();
    setInterval(updateElapsed, 30000);

    // ── Take Order button feedback ──
    document.querySelectorAll('.rd-take-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Accepting...</span>';
        btn.style.pointerEvents = 'none';
      });
    });

    // ── Auto-refresh visual indicator ──
    var refreshBar = document.getElementById('rd-refresh-bar');
    if (refreshBar) {
      setInterval(function () {
        refreshBar.classList.add('visible');
        setTimeout(function () { refreshBar.classList.remove('visible'); }, 1500);
      }, 60000);
    }

  });
})();