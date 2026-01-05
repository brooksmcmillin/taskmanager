/**
 * Client-side API utilities for consistent fetch handling
 */

/**
 * Make an API request with auth handling and JSON parsing
 * @param {string} url - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<{ok: boolean, data?: any, error?: string, status: number}>}
 */
export async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (response.status === 401) {
      window.location.href = '/login';
      return { ok: false, error: 'Authentication required', status: 401 };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        ok: false,
        error: errorData.error || errorData.message || 'Request failed',
        status: response.status,
      };
    }

    const data = await response.json();
    return { ok: true, data, status: response.status };
  } catch (error) {
    return { ok: false, error: error.message || 'Network error', status: 0 };
  }
}

/**
 * GET request helper
 * @param {string} url - API endpoint
 * @returns {Promise<{ok: boolean, data?: any, error?: string, status: number}>}
 */
export function apiGet(url) {
  return apiFetch(url, { method: 'GET' });
}

/**
 * POST request helper
 * @param {string} url - API endpoint
 * @param {any} data - Request body
 * @returns {Promise<{ok: boolean, data?: any, error?: string, status: number}>}
 */
export function apiPost(url, data) {
  return apiFetch(url, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * PUT request helper
 * @param {string} url - API endpoint
 * @param {any} data - Request body
 * @returns {Promise<{ok: boolean, data?: any, error?: string, status: number}>}
 */
export function apiPut(url, data) {
  return apiFetch(url, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * DELETE request helper
 * @param {string} url - API endpoint
 * @returns {Promise<{ok: boolean, data?: any, error?: string, status: number}>}
 */
export function apiDelete(url) {
  return apiFetch(url, { method: 'DELETE' });
}

/**
 * Create a modal manager for consistent modal handling
 * @param {string} modalId - Modal element ID
 * @param {string} formId - Form element ID
 * @param {Function} resetFormFn - Function to reset form to add mode
 * @returns {Object} Modal manager with open, close, and setup methods
 */
export function createModalManager(modalId, formId, resetFormFn) {
  const modal = document.getElementById(modalId);
  const form = document.getElementById(formId);

  function open() {
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    modal.classList.remove('show');
    document.body.style.overflow = '';
    if (form) form.reset();
    if (resetFormFn) resetFormFn();
  }

  function setup() {
    // Close on backdrop click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });

    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('show')) {
        close();
      }
    });

    // Close button
    const closeBtn = modal.querySelector('.close');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
    }
  }

  return { open, close, setup, modal, form };
}

/**
 * Create a form manager for CRUD operations
 * @param {Object} config - Form configuration
 * @returns {Object} Form manager with methods for form operations
 */
export function createFormManager(config) {
  const {
    formId,
    entityName,
    apiEndpoint,
    getFormData,
    fields,
    onSuccess,
    deleteConfirmMessage,
  } = config;

  let editingId = null;
  const form = document.getElementById(formId);

  function populateForEdit(entity) {
    editingId = entity.id;
    fields.forEach(({ name, element, getValue }) => {
      const el = element || document.getElementById(name);
      if (el && getValue) {
        el.value = getValue(entity);
      } else if (el) {
        el.value = entity[name] || '';
      }
    });

    // Update UI for edit mode
    const submitBtn = document.getElementById('submit-btn');
    const modalHeader = document.querySelector('.modal-header h2');
    const deleteBtn = document.getElementById('delete-btn');

    if (submitBtn) submitBtn.textContent = `Update ${entityName}`;
    if (modalHeader) modalHeader.textContent = `Edit ${entityName}`;
    if (deleteBtn) deleteBtn.classList.remove('hidden');
  }

  function resetToAddMode() {
    editingId = null;
    const submitBtn = document.getElementById('submit-btn');
    const modalHeader = document.querySelector('.modal-header h2');
    const deleteBtn = document.getElementById('delete-btn');

    if (submitBtn) submitBtn.textContent = `Add ${entityName}`;
    if (modalHeader) modalHeader.textContent = `Add New ${entityName}`;
    if (deleteBtn) deleteBtn.classList.add('hidden');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = getFormData
      ? getFormData(formData)
      : Object.fromEntries(formData);

    const isEditing = editingId !== null;
    const url = isEditing ? `${apiEndpoint}/${editingId}` : apiEndpoint;
    const method = isEditing ? 'PUT' : 'POST';

    const result = await apiFetch(url, {
      method,
      body: JSON.stringify(data),
    });

    if (result.ok) {
      e.target.reset();
      resetToAddMode();
      if (onSuccess) onSuccess();
    } else {
      alert(
        `Error ${isEditing ? 'updating' : 'creating'} ${entityName.toLowerCase()}: ${result.error}`
      );
    }
  }

  async function handleDelete() {
    if (editingId === null) return;

    const message =
      deleteConfirmMessage ||
      `Are you sure you want to delete this ${entityName.toLowerCase()}?`;
    if (!confirm(message)) return;

    const result = await apiDelete(`${apiEndpoint}/${editingId}`);

    if (result.ok) {
      form.reset();
      resetToAddMode();
      if (onSuccess) onSuccess();
    } else {
      alert(`Error deleting ${entityName.toLowerCase()}: ${result.error}`);
    }
  }

  function setup() {
    form.addEventListener('submit', handleSubmit);
    const deleteBtn = document.getElementById('delete-btn');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', handleDelete);
    }
  }

  return {
    populateForEdit,
    resetToAddMode,
    handleSubmit,
    handleDelete,
    setup,
    getEditingId: () => editingId,
    setEditingId: (id) => {
      editingId = id;
    },
  };
}
