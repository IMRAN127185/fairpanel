/**
 * FairPanel API Wrapper (api.js)
 * Unified wrapper for CSRF handling, Fetch calls, error formatting, and toast notifications.
 */

const FairPanel = (() => {
  // Extract CSRF token from cookie or DOM
  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;
    return '';
  }

  // Toast notifications
  function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');

    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
    toast.innerHTML = `<span style="font-weight:bold; color:${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};">${icon}</span> <span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.25s';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  // HTML escaping for safe text rendering
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  // Fetch wrapper
  async function request(url, options = {}) {
    const headers = {
      'Accept': 'application/json',
      ...options.headers,
    };

    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
      let csrf = getCsrfToken();
      if (!csrf) {
        const csrfResponse = await fetch('/api/v1/auth/csrf', {
          credentials: 'same-origin',
          headers: { 'Accept': 'application/json' }
        });
        if (!csrfResponse.ok) throw new Error('Unable to start a secure session. Please reload.');
        csrf = getCsrfToken() || (await csrfResponse.json()).data.csrf_token;
      }
      if (csrf) {
        headers['X-CSRFToken'] = csrf;
      }
      if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
      }
    }

    try {
      const res = await fetch(url, { ...options, headers });
      const contentType = res.headers.get('content-type') || '';
      
      let data = null;
      if (contentType.includes('application/json')) {
        data = await res.json();
      } else {
        data = await res.text();
      }

      if (!res.ok) {
        const errorInfo = (data && data.error) ? data.error : {
          code: `http_${res.status}`,
          message: res.statusText || 'An error occurred'
        };
        const err = new Error(errorInfo.message);
        err.code = errorInfo.code;
        err.fields = errorInfo.fields || {};
        err.status = res.status;
        throw err;
      }

      return data ? (data.data !== undefined ? data.data : data) : null;
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error(`[FairPanel API] ${method} ${url} failed:`, err);
      }
      throw err;
    }
  }

  return {
    get: (url, opts) => request(url, { ...opts, method: 'GET' }),
    post: (url, body, opts) => request(url, { ...opts, method: 'POST', body }),
    patch: (url, body, opts) => request(url, { ...opts, method: 'PATCH', body }),
    put: (url, body, opts) => request(url, { ...opts, method: 'PUT', body }),
    delete: (url, opts) => request(url, { ...opts, method: 'DELETE' }),
    showToast,
    escapeHtml,
    getCsrfToken
  };
})();
