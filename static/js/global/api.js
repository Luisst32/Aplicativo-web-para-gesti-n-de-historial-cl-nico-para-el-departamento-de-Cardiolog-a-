/**
 * API.JS
 * Wrapper global para peticiones HTTP (fetch) con token CSRF de Django y manejo unificado de errores.
 */

const api = {
  /**
   * Petición genérica usando fetch con cabeceras de Django
   */
  async request(url, options = {}) {
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    };

    // Agregar token CSRF en métodos que modifican estado
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const csrfToken = getCookie('csrftoken');
      if (csrfToken) {
        defaultHeaders['X-CSRFToken'] = csrfToken;
      }
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (e) {
          errorData = { detail: response.statusText };
        }
        const error = new Error(errorData.message || errorData.detail || `Error HTTP ${response.status}`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      // Si no hay contenido (204 No Content), retornar null
      if (response.status === 204) return null;

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.text();
    } catch (err) {
      console.error(`[API Error] ${method} ${url}:`, err);
      throw err;
    }
  },

  get(url, options = {}) {
    return this.request(url, { ...options, method: 'GET' });
  },

  post(url, data = {}, options = {}) {
    return this.request(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  put(url, data = {}, options = {}) {
    return this.request(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data)
    });
  },

  patch(url, data = {}, options = {}) {
    return this.request(url, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  },

  delete(url, options = {}) {
    return this.request(url, { ...options, method: 'DELETE' });
  }
};
