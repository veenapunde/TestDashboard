/**
 * api.js – Centralised API helper and toast notification system
 */

const API_BASE = '';   // Same-origin; Flask serves on port 5000

// ─── Toast Notifications ──────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }, duration);
}

// ─── Core Fetch Wrapper ───────────────────────────────────────────────────────
/**
 * Make an API request with automatic auth header injection and error
 * handling.
 *
 * @param {string} endpoint  - e.g. '/api/students'
 * @param {object} options   - standard fetch options (method, body, etc.)
 * @returns {Promise<{ok, status, data}>}
 */
async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(options.headers || {})
    };

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        // Handle 401 – force logout
        if (response.status === 401) {
            showToast('Session expired. Please log in again.', 'error');
            setTimeout(logout, 1500);
            return { ok: false, status: 401, data: null };
        }

        const data = await response.json();
        return { ok: response.ok, status: response.status, data };

    } catch (err) {
        console.error(`API error [${endpoint}]:`, err);
        showToast('Connection error. Is the server running?', 'error');
        return { ok: false, status: 0, data: null };
    }
}

// ─── Shorthand helpers ────────────────────────────────────────────────────────
const api = {
    get:    (url)           => apiRequest(url, { method: 'GET' }),
    post:   (url, body)     => apiRequest(url, { method: 'POST',   body: JSON.stringify(body) }),
    put:    (url, body)     => apiRequest(url, { method: 'PUT',    body: JSON.stringify(body) }),
    delete: (url)           => apiRequest(url, { method: 'DELETE' })
};
