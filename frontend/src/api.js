const defaultApiBaseUrl = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '/api';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const shouldSendJson = options.body && !(options.body instanceof FormData);

  if (shouldSendJson && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    const detail = data?.detail || data?.message || 'Something went wrong';
    throw new Error(detail);
  }

  return data;
}

export function signup(payload) {
  return request('/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function login(payload) {
  return request('/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchDocuments(userId) {
  return request(`/documents/${userId}`);
}

export function uploadDocument(userId, file) {
  const formData = new FormData();
  formData.append('user_id', String(userId));
  formData.append('file', file);

  return request('/parse-document', {
    method: 'POST',
    body: formData,
  });
}