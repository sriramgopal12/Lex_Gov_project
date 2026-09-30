const defaultApiBaseUrl = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '/api';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const session = window.localStorage.getItem('lexgov-session');
  const accessToken = session ? JSON.parse(session)?.accessToken : null;
  const shouldSendJson = options.body && !(options.body instanceof FormData);

  if (shouldSendJson && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
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

export function fetchDocuments() {
  return request('/documents');
}

export function fetchDocumentStatus(documentId) {
  return request(`/documents/${documentId}/status`);
}

export function fetchChatHistory(documentId) {
  return request(`/documents/${documentId}/chat-history`);
}

export function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, { method: 'DELETE' });
}

export function deleteChat(documentId, chatId) {
  return request(`/documents/${documentId}/chat-history/${chatId}`, { method: 'DELETE' });
}

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  return request('/parse-document', {
    method: 'POST',
    body: formData,
  });
}

export function askDocumentQuestion(documentId, question) {
  return request(`/documents/${documentId}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

export function fetchSuggestedQuestions(documentId) {
  return request(`/documents/${documentId}/suggested-questions`);
}

export function simplifyDocumentAnswer(documentId, answerId) {
  return request(`/documents/${documentId}/simpler`, {
    method: 'POST',
    body: JSON.stringify({ answer_id: answerId }),
  });
}

export async function fetchDocumentPdf(documentId) {
  const session = window.localStorage.getItem('lexgov-session');
  const accessToken = session ? JSON.parse(session)?.accessToken : null;
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/pdf`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });

  if (!response.ok) {
    let detail = 'Unable to load the original PDF';
    try {
      const data = await response.json();
      detail = data?.detail || detail;
    } catch {
    }
    throw new Error(detail);
  }

  return response.blob();
}