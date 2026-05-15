/* ═══════════════════════════════════════════
   LOUP GAROU — Utils
   DOM, WebSocket, Animations, Toast
   ═══════════════════════════════════════════ */

const LoupGarouUtils = (() => {

  /* ──────────────────────────────────────────
     DOM HELPERS
     ────────────────────────────────────────── */
  function qs(selector, parent = document) {
    return parent.querySelector(selector);
  }

  function qsAll(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
  }

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function createElement(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    for (const [key, val] of Object.entries(attrs)) {
      if (key === 'class') {
        el.className = val;
      } else if (key === 'style' && typeof val === 'object') {
        Object.assign(el.style, val);
      } else if (key.startsWith('on') && typeof val === 'function') {
        el.addEventListener(key.slice(2).toLowerCase(), val);
      } else if (key === 'dataset' && typeof val === 'object') {
        Object.assign(el.dataset, val);
      } else {
        el.setAttribute(key, val);
      }
    }
    for (const child of children) {
      if (child == null) continue;
      if (typeof child === 'string') {
        el.appendChild(document.createTextNode(child));
      } else {
        el.appendChild(child);
      }
    }
    return el;
  }

  function setHTML(el, html) {
    if (!el) return;
    el.innerHTML = html;
  }

  function setText(el, text) {
    if (!el) return;
    el.textContent = text;
  }

  function show(el) {
    if (!el) return;
    el.classList.remove('hidden');
  }

  function hide(el) {
    if (!el) return;
    el.classList.add('hidden');
  }

  function toggle(el, condition) {
    if (!el) return;
    el.classList.toggle('hidden', !condition);
  }

  function addClass(el, ...cls) {
    if (!el) return;
    el.classList.add(...cls);
  }

  function removeClass(el, ...cls) {
    if (!el) return;
    el.classList.remove(...cls);
  }

  function hasClass(el, cls) {
    return el ? el.classList.contains(cls) : false;
  }

  function empty(el) {
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  /* ──────────────────────────────────────────
     ANIMATION HELPERS
     ────────────────────────────────────────── */
  function animateOnce(el, animationClass, duration = 600) {
    return new Promise(resolve => {
      if (!el) return resolve();
      el.classList.add(animationClass);
      const cleanup = () => {
        el.classList.remove(animationClass);
        resolve();
      };
      setTimeout(cleanup, duration);
    });
  }

  function addRipple(btn, e) {
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const x = (e ? e.clientX - rect.left : rect.width / 2) - size / 2;
    const y = (e ? e.clientY - rect.top  : rect.height / 2) - size / 2;
    const ripple = createElement('span', {
      class: 'ripple',
      style: { width: `${size}px`, height: `${size}px`, left: `${x}px`, top: `${y}px` }
    });
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
  }

  // Attach ripple to all .btn elements dynamically
  document.addEventListener('click', e => {
    const btn = e.target.closest('.btn');
    if (btn) addRipple(btn, e);
  });

  function fadeIn(el, duration = 300) {
    if (!el) return;
    el.style.opacity = '0';
    el.style.transition = `opacity ${duration}ms ease`;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { el.style.opacity = '1'; });
    });
  }

  function staggerAnimate(parent, cls = 'stagger-children') {
    if (!parent) return;
    parent.classList.add(cls);
    setTimeout(() => parent.classList.remove(cls), 2000);
  }

  /* ──────────────────────────────────────────
     TOAST NOTIFICATIONS
     ────────────────────────────────────────── */
  let _toastContainer = null;

  function getToastContainer() {
    if (!_toastContainer) {
      _toastContainer = createElement('div', { class: 'toast-container', id: 'toast-container' });
      document.body.appendChild(_toastContainer);
    }
    return _toastContainer;
  }

  function showToast(message, opts = {}) {
    const { type = 'info', duration = 3500 } = opts;
    const container = getToastContainer();
    const toast = createElement('div', {
      class: `toast${type === 'error' ? ' toast-error' : ''}`
    });
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-out');
      setTimeout(() => toast.remove(), 500);
    }, duration);
  }

  /* ──────────────────────────────────────────
     WEBSOCKET WITH AUTO-RECONNECT
     ────────────────────────────────────────── */
  function createWebSocket(path, handlers = {}) {
    const WS_URL = (() => {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${location.host}${path}`;
    })();

    let ws = null;
    let reconnectTimer = null;
    let reconnectDelay = 1500;
    let reconnectAttempts = 0;
    const MAX_RECONNECT = 10;
    let intentionallyClosed = false;
    let _onMessage = handlers.onMessage || (() => {});
    let _onOpen    = handlers.onOpen    || (() => {});
    let _onClose   = handlers.onClose   || (() => {});
    let _onStatus  = handlers.onStatus  || (() => {});

    function connect() {
      intentionallyClosed = false;
      _onStatus('connecting');
      try {
        ws = new WebSocket(WS_URL);
      } catch(err) {
        debugLog('WS create error:', err);
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        reconnectDelay = 1500;
        reconnectAttempts = 0;
        _onStatus('connected');
        _onOpen();
        debugLog('WS connected');
      };

      ws.onclose = e => {
        _onStatus('disconnected');
        _onClose(e);
        debugLog('WS closed', e.code, e.reason);
        if (!intentionallyClosed) scheduleReconnect();
      };

      ws.onerror = err => {
        debugLog('WS error', err);
        _onStatus('error');
      };

      ws.onmessage = e => {
        try {
          const data = JSON.parse(e.data);
          _onMessage(data);
        } catch (err) {
          debugLog('WS parse error', err);
        }
      };
    }

    function scheduleReconnect() {
      if (reconnectAttempts >= MAX_RECONNECT) {
        debugLog('WS max reconnect attempts reached');
        _onStatus('error');
        return;
      }
      _onStatus('reconnecting');
      reconnectAttempts++;
      reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
      debugLog(`WS reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts})`);
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, reconnectDelay);
    }

    function send(data) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
        return true;
      }
      debugLog('WS not ready, cannot send', data);
      return false;
    }

    function close() {
      intentionallyClosed = true;
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    }

    function isConnected() {
      return ws && ws.readyState === WebSocket.OPEN;
    }

    connect();

    return { send, close, isConnected, reconnect: connect };
  }

  /* ──────────────────────────────────────────
     DEBUG LOGGING
     ────────────────────────────────────────── */
  let _debug = location.search.includes('debug=1') ||
              localStorage.getItem('lg_debug') === '1';

  function debugLog(...args) {
    if (_debug) console.log('[LG]', ...args);
  }

  function isDebugMode() {
    return _debug;
  }

  function setDebugMode(enabled) {
    _debug = !!enabled;
    if (enabled) {
      localStorage.setItem('lg_debug', '1');
    } else {
      localStorage.removeItem('lg_debug');
    }
  }

  /* ──────────────────────────────────────────
     MISC HELPERS
     ────────────────────────────────────────── */
  function debounce(fn, delay = 200) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
  }

  function throttle(fn, limit = 200) {
    let last = 0;
    return (...args) => {
      const now = Date.now();
      if (now - last >= limit) { last = now; fn(...args); }
    };
  }

  function getInitials(name) {
    if (!name) return '?';
    return name.trim().split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }

  // Generate a stable pastel color from a string
  function stringToColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 50%, 55%)`;
  }

  function formatRound(n) {
    return String(n).padStart(2, '0');
  }

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  /* ──────────────────────────────────────────
     STARS BACKGROUND
     ────────────────────────────────────────── */
  function createStars(container, count = 60) {
    for (let i = 0; i < count; i++) {
      const star = createElement('div', {
        class: 'star',
        style: {
          left: `${Math.random() * 100}%`,
          top:  `${Math.random() * 60}%`,
          '--twinkle-dur':   `${2 + Math.random() * 4}s`,
          '--twinkle-delay': `${Math.random() * 4}s`,
          opacity: Math.random() * 0.6 + 0.2
        }
      });
      container.appendChild(star);
    }
  }

  return {
    qs, qsAll, escapeHtml, createElement, setHTML, setText,
    show, hide, toggle, addClass, removeClass, hasClass, empty,
    animateOnce, addRipple, fadeIn, staggerAnimate,
    showToast,
    createWebSocket,
    debugLog, isDebugMode, setDebugMode,
    debounce, throttle,
    getInitials, stringToColor, formatRound, sleep,
    createStars
  };

})();

if (typeof module !== 'undefined') module.exports = LoupGarouUtils;
