/**
 * auth.js – Authentication guard and utilities
 * Used by every protected page (dashboard, students, courses, etc.)
 */

const AUTH_TOKEN_KEY = 'token';

/**
 * Returns the stored JWT token, or null.
 */
function getToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
}

/**
 * Redirect to login if no token is present.
 * Call this at the top of every protected page.
 */
function requireAuth() {
    if (!getToken()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

/**
 * Clear the token and go back to login.
 */
function logout() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    window.location.href = 'login.html';
}

/**
 * Build the standard Authorization header object.
 */
function authHeaders(extra = {}) {
    return {
        'Authorization': `Bearer ${getToken()}`,
        ...extra
    };
}

/**
 * Attach the logout handler to the #logoutBtn if it exists.
 */
function attachLogoutBtn(Call) {
    const btn = document.getElementById('logoutBtn');
    if (btn) {
        btn.addEventListener('click', logout);
    }
}

// Auto-initialise when dom is ready
document.addEventListener('DOMContentLoaded', () => {
    attachLogoutBtn();
});
