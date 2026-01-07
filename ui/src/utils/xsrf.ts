/**
 * XSRF Token Utilities
 *
 * You typically don't need to use these functions directly unless you need
 * manual control over XSRF token handling.
 */

const XSRF_COOKIE_NAME = '_xsrf';
const XSRF_HEADER_NAME = 'X-XSRFToken';

/**
 * Get XSRF token from cookie
 */
export function getXsrfTokenFromCookie(): string | null {
    const match = document.cookie.match(new RegExp(`(^|;\\s*)${XSRF_COOKIE_NAME}=([^;]*)`));
    return match ? decodeURIComponent(match[2]) : null;
}

/**
 * Fetch XSRF token from server (sets cookie automatically)
 */
export async function fetchXsrfToken(): Promise<string> {
    // Use relative URL to avoid CORS issues
    const response = await fetch('/api/xsrf-token', {
        credentials: 'include', // include cookies
    });

    if (!response.ok) {
        throw new Error('Failed to fetch XSRF token');
    }

    const data = await response.json();
    return data.token;
}

/**
 * Ensure XSRF token is available, fetch if needed
 */
export async function ensureXsrfToken(): Promise<string> {
    let token = getXsrfTokenFromCookie();

    if (!token) {
        token = await fetchXsrfToken();
    }

    return token;
}

/**
 * Enhanced fetch with automatic XSRF token handling
 *
 * This function is kept for backwards compatibility but may be removed in the future.
 */
export async function fetchWithXsrf(url: string, options: RequestInit = {}): Promise<Response> {
    const method = options.method?.toUpperCase() || 'GET';

    // only need XSRF for state-changing methods
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        const token = await ensureXsrfToken();

        options.headers = {
            ...options.headers,
            [XSRF_HEADER_NAME]: token,
        };
    }

    // always include credentials for cookies
    options.credentials = 'include';

    return fetch(url, options);
}

/* USAGE EXAMPLES
 *
 * NOTE: With the global fetch interceptor, you typically just use fetch() directly:
 *
 * Example: Creating a session (standard fetch, XSRF handled automatically)
 *
 * async function createSession(context: string) {
 *     const response = await fetch('http://localhost:8888/api/sessions/create-with-context', {
 *         method: 'POST',
 *         headers: {
 *             'Content-Type': 'application/json',
 *         },
 *         body: JSON.stringify({
 *             context,
 *             context_info: {},
 *             language: 'python3',
 *         }),
 *     });
 *
 *     if (!response.ok) {
 *         throw new Error('Failed to create session');
 *     }
 *
 *     return response.json();
 * }
 *
 */
