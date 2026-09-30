import { useEffect, useMemo, useRef, useState } from 'react';
import {
  askDocumentQuestion,
  deleteChat,
  deleteDocument,
  fetchChatHistory,
  fetchDocumentPdf,
  fetchDocuments,
  fetchSuggestedQuestions,
  login,
  simplifyDocumentAnswer,
  signup,
  uploadDocument,
} from './api';

const initialAuth = {
  name: '',
  email: '',
  password: '',
};

const ROUTES = {
  landing: '/',
  signup: '/signup',
  login: '/login',
  dashboard: '/dashboard',
  documentReview: '/document-review',
};

function App() {
  const [session, setSession] = useState(() => {
    const stored = window.localStorage.getItem('lexgov-session');
    return stored ? JSON.parse(stored) : null;
  });
  const [theme, setTheme] = useState(() => {
    const storedTheme = window.localStorage.getItem('lexgov-theme');
    if (storedTheme === 'light' || storedTheme === 'dark') {
      return storedTheme;
    }

    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  const [view, setView] = useState(() => getViewFromLocation());
  const [currentDocument, setCurrentDocument] = useState(null);

  useEffect(() => {
    if (session) {
      window.localStorage.setItem('lexgov-session', JSON.stringify(session));
    } else {
      window.localStorage.removeItem('lexgov-session');
    }
  }, [session]);

  useEffect(() => {
    window.localStorage.setItem('lexgov-theme', theme);
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    function handleHashChange() {
      setView(getViewFromLocation());
    }

    window.addEventListener('hashchange', handleHashChange);
    window.addEventListener('popstate', handleHashChange);
    handleHashChange();

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
      window.removeEventListener('popstate', handleHashChange);
    };
  }, []);

  useEffect(() => {
    if (session && (view === 'login' || view === 'signup')) {
      setHashRoute('dashboard');
    }
  }, [session, view]);

  useEffect(() => {
    if (!session || view !== 'document-review' || currentDocument) {
      return;
    }

    const documentId = getDocumentIdFromLocation();
    if (!documentId) {
      return;
    }

    fetchDocuments()
      .then((response) => {
        const document = response.documents?.find((item) => item.id === documentId);
        if (document) {
          setCurrentDocument(document);
        } else {
          setHashRoute('dashboard');
        }
      })
      .catch(() => setHashRoute('dashboard'));
  }, [currentDocument, session, view]);

  const resolvedView = session || view !== 'dashboard' ? view : 'dashboard';

  function handleNavigate(nextView) {
    if (nextView === 'document-review') {
      setHashRoute('documentReview');
      return;
    }

    setHashRoute(nextView);
  }

  function toggleTheme() {
    setTheme((currentTheme) => (currentTheme === 'dark' ? 'light' : 'dark'));
  }

  return (
    <div className="app-shell">
      <button className="theme-toggle" type="button" onClick={toggleTheme}>
        {theme === 'dark' ? 'Light theme' : 'Dark theme'}
      </button>
      {resolvedView === 'dashboard' && session ? (
        <DashboardPage
          session={session}
          onLogout={() => {
            setSession(null);
            setCurrentDocument(null);
            handleNavigate('landing');
          }}
          onNavigate={handleNavigate}
          onOpenDocument={(document) => {
            setCurrentDocument(document);
            window.history.pushState({}, '', `/documents/${document.id}/chat`);
            setView('document-review');
          }}
        />
      ) : resolvedView === 'document-review' && currentDocument ? (
        <DocumentReviewPage
          session={session}
          selectedDocument={currentDocument}
          onBack={() => {
            setCurrentDocument(null);
            handleNavigate('dashboard');
          }}
          onLogout={() => {
            setSession(null);
            setCurrentDocument(null);
            handleNavigate('landing');
          }}
        />
      ) : resolvedView === 'signup' ? (
        <AuthPage
          mode="signup"
          onSuccess={setSession}
          session={session}
          onNavigate={handleNavigate}
        />
      ) : resolvedView === 'login' ? (
        <AuthPage
          mode="login"
          onSuccess={setSession}
          session={session}
          onNavigate={handleNavigate}
        />
      ) : (
        <LandingPage
          session={session}
          onLogout={() => {
            setSession(null);
            handleNavigate('landing');
          }}
          onNavigate={handleNavigate}
        />
      )}
    </div>
  );
}

function getViewFromHash(hash) {
  const normalized = hash.replace(/^#/, '') || '/';

  if (normalized === '/signup') {
    return 'signup';
  }

  if (normalized === '/login') {
    return 'login';
  }

  if (normalized === '/dashboard') {
    return 'dashboard';
  }

  if (normalized === '/document-review' || /^\/documents\/\d+\/chat$/.test(normalized)) {
    return 'document-review';
  }

  return 'landing';
}

function getViewFromLocation() {
  if (/^\/documents\/\d+\/chat$/.test(window.location.pathname)) {
    return 'document-review';
  }

  return getViewFromHash(window.location.hash);
}

function getDocumentIdFromLocation() {
  const match = window.location.pathname.match(/^\/documents\/(\d+)\/chat$/);
  return match ? Number(match[1]) : null;
}

function formatHistoryTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const dateKey = date.toDateString();
  const label = dateKey === today.toDateString()
    ? 'Today'
    : dateKey === yesterday.toDateString()
      ? 'Yesterday'
      : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  return `${label} · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
}

function setHashRoute(nextView) {
  const nextPath = ROUTES[nextView] || ROUTES.landing;
  if (window.location.pathname !== '/') {
    window.history.pushState({}, '', '/');
  }
  window.location.hash = `#${nextPath}`;
}

function LandingPage({ session, onLogout, onNavigate }) {
  return (
    <main className="page landing-page">
      <header className="topbar">
        <button className="brand-mark brand-button" type="button" onClick={() => onNavigate('landing')}>
          LexGov
        </button>
        <nav className="topbar-actions">
          {session ? (
            <>
              <button type="button" className="ghost-link" onClick={() => onNavigate('dashboard')}>
                Dashboard
              </button>
              <button className="secondary-button" type="button" onClick={onLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <button type="button" className="ghost-link" onClick={() => onNavigate('login')}>
                Login
              </button>
              <button type="button" className="primary-button compact-button" onClick={() => onNavigate('signup')}>
                Create account
              </button>
            </>
          )}
        </nav>
      </header>

      <section className="hero-grid">
        <div className="hero-copy card-glass">
          <p className="eyebrow">Modern legal document workflow</p>
          <h1>
            LexGov keeps legal PDFs organized in a clean, official workspace.
          </h1>
          <p className="hero-description">
            Create an account, sign in securely, and see only the documents tied to your
            profile in one focused dashboard.
          </p>
          <div className="hero-actions">
            <button type="button" className="primary-button" onClick={() => onNavigate('signup')}>
              Sign up
            </button>
            <button type="button" className="secondary-button" onClick={() => onNavigate('login')}>
              Log in
            </button>
          </div>
          <div className="hero-stats">
            <div>
              <strong>Secure</strong>
              <span>Account-based access</span>
            </div>
            <div>
              <strong>Focused</strong>
              <span>Only your files visible</span>
            </div>
            <div>
              <strong>Official</strong>
              <span>Polished government-style UI</span>
            </div>
          </div>
        </div>

        <div className="hero-panel card-surface">
          <div className="panel-header">
            <span className="panel-badge">LexGov</span>
            <span className="panel-chip">Trusted legal portal</span>
          </div>
          <div className="panel-list">
            <button className="panel-item panel-action" type="button" onClick={() => onNavigate('signup')}>
              <span>01</span>
              <div>
                <strong>Sign up</strong>
                <p>Register a profile in seconds.</p>
              </div>
            </button>
            <button className="panel-item panel-action" type="button" onClick={() => onNavigate('login')}>
              <span>02</span>
              <div>
                <strong>Log in</strong>
                <p>Access your personal document area.</p>
              </div>
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function AuthPage({ mode, onSuccess, session, onNavigate }) {
  const [form, setForm] = useState(initialAuth);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const isSignup = mode === 'signup';

  useEffect(() => {
    setError('');
  }, [mode]);

  const title = useMemo(() => (isSignup ? 'Create your LexGov account' : 'Welcome back to LexGov'), [isSignup]);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const payload = isSignup
        ? {
            name: form.name.trim(),
            email: form.email.trim(),
            password: form.password,
          }
        : {
            email: form.email.trim(),
            password: form.password,
          };

      const result = isSignup ? await signup(payload) : await login(payload);

      if (isSignup) {
        onNavigate('login');
        return;
      }

      const nextSession = {
        userId: Number(result.user_id),
        accessToken: result.access_token,
        name: result.name || form.name.trim(),
        email: result.email,
      };

      onSuccess(nextSession);
      onNavigate('dashboard');
    } catch (error) {
      setError(error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  if (session) {
    return null;
  }

  return (
    <main className="page auth-page">
      <div className="auth-nav">
        <button className="auth-back-button" type="button" onClick={() => onNavigate('dashboard')}>
          <span className="auth-back-icon" aria-hidden="true">←</span>
          <span>Back to dashboard</span>
        </button>
        <span className="auth-nav-label">LexGov secure access</span>
      </div>

      <div className="auth-shell">
        <section className="auth-brand card-surface">
          <button className="brand-mark brand-mark-large brand-button" type="button" onClick={() => onNavigate('landing')}>
            LexGov
          </button>
          <h1>{title}</h1>
          <p>
            A refined legal workspace for secure account access and personalized PDF tracking.
          </p>
          <div className="auth-note">
            <span>{isSignup ? 'New user onboarding' : 'Returning user sign in'}</span>
          </div>
        </section>

        <section className="auth-card card-glass">
          <div className="auth-tabs">
            <button type="button" className={`tab-link ${!isSignup ? 'active' : ''}`} onClick={() => onNavigate('login')}>
              Login
            </button>
            <button type="button" className={`tab-link ${isSignup ? 'active' : ''}`} onClick={() => onNavigate('signup')}>
              Sign up
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {isSignup && (
              <label>
                Full name
                <input
                  type="text"
                  placeholder="Enter your name"
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  required
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                placeholder="name@example.com"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                placeholder="Enter your password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                required
              />
            </label>

            {error && <div className="form-alert">{error}</div>}

            <button className="primary-button submit-button" type="submit" disabled={loading}>
              {loading ? 'Please wait...' : isSignup ? 'Create account' : 'Log in'}
            </button>
          </form>

          <p className="form-footnote">
            {isSignup ? 'Already have an account?' : 'Need an account?'}{' '}
            <button type="button" className="inline-text-button" onClick={() => onNavigate(isSignup ? 'login' : 'signup')}>
              {isSignup ? 'Log in' : 'Sign up'}
            </button>
          </p>
        </section>
      </div>
    </main>
  );
}

function DocumentReviewPage({ session, selectedDocument, onBack, onLogout }) {
  const [chatInput, setChatInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [copiedCitation, setCopiedCitation] = useState('');
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [pdfUrl, setPdfUrl] = useState('');
  const [pdfLoading, setPdfLoading] = useState(false);
  const [simplifyingId, setSimplifyingId] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [deletingChatId, setDeletingChatId] = useState(null);
  const [activeHistoryId, setActiveHistoryId] = useState(null);
  const [chatMessages, setChatMessages] = useState([
    {
      id: `welcome-${selectedDocument.unique_identifier_name}`,
      sender: 'assistant',
      text: `You are now reviewing ${selectedDocument.pdf_name}. Ask a question about the document, clauses, duties, deadlines, or legal meaning.`,
    },
  ]);

  useEffect(() => {
    let active = true;
    setHistoryLoading(true);
    fetchChatHistory(selectedDocument.id)
      .then((response) => {
        if (active) {
          setChatHistory(response.messages || []);
        }
      })
      .catch(() => {
        if (active) {
          setChatHistory([]);
        }
      })
      .finally(() => {
        if (active) {
          setHistoryLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedDocument.id]);

  useEffect(() => {
    let active = true;
    setSuggestionsLoading(true);
    fetchSuggestedQuestions(selectedDocument.id)
      .then((response) => {
        if (active) {
          setSuggestedQuestions(response.questions || []);
        }
      })
      .catch(() => {
        if (active) {
          setSuggestedQuestions([]);
        }
      })
      .finally(() => {
        if (active) {
          setSuggestionsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedDocument.id]);

  useEffect(() => () => {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
    }
  }, [pdfUrl]);

  function startNewChat() {
    setError('');
    setNotice('');
    setActiveHistoryId(null);
    setChatMessages([{
      id: `welcome-${selectedDocument.unique_identifier_name}-${Date.now()}`,
      sender: 'assistant',
      text: `You are now reviewing ${selectedDocument.pdf_name}. Ask a question about the document, clauses, duties, deadlines, or legal meaning.`,
    }]);
  }

  function openHistoryItem(item) {
    setError('');
    setNotice('');
    setActiveHistoryId(item.id);
    setChatMessages([
      { id: `history-${item.id}-question`, sender: 'user', text: item.question },
      {
        id: `history-${item.id}-answer`,
        sender: 'assistant',
        text: item.simplified_answer || item.answer,
        sources: item.sources || [],
        answerId: item.answer_id || '',
        question: item.question,
        simplified: Boolean(item.simplified_answer),
      },
    ]);
  }

  async function handleDeleteChat(item) {
    if (deletingChatId === item.id || !window.confirm('Delete this chat? Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      setDeletingChatId(item.id);
      setError('');
      await deleteChat(selectedDocument.id, item.id);
      setChatHistory((current) => current.filter((historyItem) => historyItem.id !== item.id));
      if (activeHistoryId === item.id) {
        setActiveHistoryId(null);
        setChatMessages([]);
      }
      setNotice('Chat deleted successfully.');
    } catch {
      setError('Unable to delete this chat. Please try again.');
    } finally {
      setDeletingChatId(null);
    }
  }

  async function togglePdf() {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
      setPdfUrl('');
      return;
    }

    try {
      setPdfLoading(true);
      setError('');
      const blob = await fetchDocumentPdf(selectedDocument.id);
      setPdfUrl(URL.createObjectURL(blob));
    } catch (requestError) {
      setError(requestError.message || 'Unable to load the original PDF.');
    } finally {
      setPdfLoading(false);
    }
  }

  async function submitQuestion(question) {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || loading) {
      return;
    }

    const userMessage = {
      id: `${selectedDocument.unique_identifier_name}-${Date.now()}-user`,
      sender: 'user',
      text: trimmedQuestion,
    };

    setChatMessages((current) => [...current, userMessage]);
    setChatInput('');
    setError('');
    setLoading(true);

    try {
      const response = await askDocumentQuestion(selectedDocument.id, trimmedQuestion);
      setActiveHistoryId(response.history_id || null);
      fetchChatHistory(selectedDocument.id)
        .then((historyResponse) => setChatHistory(historyResponse.messages || []))
        .catch(() => {});
      setChatMessages((current) => [
        ...current,
        {
          id: `${selectedDocument.unique_identifier_name}-${Date.now()}-assistant`,
          sender: 'assistant',
          text: response.answer,
          sources: response.sources || [],
          answerId: response.answer_id || '',
          question: trimmedQuestion,
        },
      ]);
    } catch (requestError) {
      setError(requestError.message || 'Unable to answer this question.');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmitQuestion(event) {
    event.preventDefault();
    submitQuestion(chatInput);
  }

  async function handleSimplerAnswer(message) {
    if (!message.answerId || simplifyingId) {
      return;
    }

    try {
      setSimplifyingId(message.id);
      setError('');
      const response = await simplifyDocumentAnswer(selectedDocument.id, message.answerId);
      setChatMessages((current) => current.map((item) => (
        item.id === message.id
          ? { ...item, text: response.answer, simplified: true }
          : item
      )));
    } catch (requestError) {
      setError(requestError.message || 'Unable to simplify this answer.');
    } finally {
      setSimplifyingId('');
    }
  }

  async function handleCopyCitation(source, citationId) {
    const citation = [
      `Section ${source.section_number || 'Unavailable'}`,
      source.title,
      source.page ? `Page ${source.page}` : '',
    ]
      .filter(Boolean)
      .join(': ')
      .replace(': Page', ' - Page');

    try {
      await navigator.clipboard.writeText(citation);
      setCopiedCitation(citationId);
      window.setTimeout(() => setCopiedCitation(''), 1600);
    } catch {
      setError('Unable to copy the citation.');
    }
  }

  return (
    <main className="page document-review-page">
      <header className="topbar document-review-topbar">
        <div>
          <button className="brand-mark brand-button" type="button" onClick={() => onBack()}>
            LexGov
          </button>
          <p className="topbar-subtitle">Document review workspace</p>
        </div>
        <div className="topbar-actions">
          <div className="user-pill">
            <strong>{session.name}</strong>
            <span>{session.email}</span>
          </div>
          <button className="secondary-button compact-button" type="button" onClick={onBack}>
            Back to files
          </button>
          <button className="secondary-button" type="button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>

      <section className={`document-review-shell card-glass ${pdfUrl ? 'with-pdf' : ''}`}>
        <aside className="document-info-panel">
          <p className="eyebrow">Legal document</p>
          <h1>{selectedDocument.pdf_name}</h1>
          <div className="document-meta-block">
            <span className="meta-pill">PDF</span>
            <span className="meta-pill">Secure review</span>
          </div>
          <p>
            Ask legal questions about this uploaded document and review AI-generated answers in a
            focused, full-screen workspace.
          </p>
          <div className="info-card">
            <strong>Suggested questions</strong>
            {suggestionsLoading ? (
              <p className="suggestions-status">Reading this document...</p>
            ) : suggestedQuestions.length > 0 ? (
              <div className="suggested-question-list">
                {suggestedQuestions.map((question) => (
                  <button
                    className="suggested-question"
                    type="button"
                    key={question}
                    onClick={() => {
                      setChatInput(question);
                      submitQuestion(question);
                    }}
                    disabled={loading}
                  >
                    {question}
                  </button>
                ))}
              </div>
            ) : (
              <p className="suggestions-status">Ask anything about this document.</p>
            )}
          </div>
          <div className="info-card history-card">
            <div className="history-heading">
              <strong>Chat history</strong>
              <button className="history-new-button" type="button" onClick={startNewChat}>New chat</button>
            </div>
            {historyLoading ? (
              <p className="suggestions-status">Loading history...</p>
            ) : chatHistory.length === 0 ? (
              <p className="suggestions-status">No questions yet.</p>
            ) : (
              <div className="history-list">
                {chatHistory.map((item) => (
                  <div className={`history-item ${activeHistoryId === item.id ? 'is-active' : ''}`} key={item.id}>
                    <button className="history-item-content" type="button" onClick={() => openHistoryItem(item)}>
                      <span>{item.question}</span>
                      <small>{formatHistoryTimestamp(item.created_at)}</small>
                    </button>
                    <button
                      className="history-delete-button"
                      type="button"
                      aria-label={`Delete chat: ${item.question}`}
                      title="Delete this chat"
                      onClick={() => handleDeleteChat(item)}
                      disabled={deletingChatId === item.id}
                    >
                      {deletingChatId === item.id ? '...' : 'Delete'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>

        <div className="document-chat-panel">
          <div className="chat-header">
            <div>
              <p className="eyebrow">Document review</p>
              <h2>{selectedDocument.pdf_name}</h2>
            </div>
            <div className="chat-header-actions">
              <button className="secondary-button compact-button" type="button" onClick={startNewChat}>
                New chat
              </button>
              <button className="secondary-button compact-button" type="button" onClick={togglePdf} disabled={pdfLoading}>
                {pdfLoading ? 'Loading PDF...' : pdfUrl ? 'Close PDF' : 'View Original PDF'}
              </button>
              <button className="secondary-button compact-button" type="button" onClick={onBack}>
                Exit review
              </button>
            </div>
          </div>

          <div className="chat-thread">
            {chatMessages.length === 0 ? (
              <div className="empty-chat-state">
                <p>No conversation selected.</p>
                <button className="secondary-button compact-button" type="button" onClick={startNewChat}>
                  Start New Chat
                </button>
              </div>
            ) : chatMessages.map((message) => (
              <div key={message.id} className={`chat-bubble ${message.sender}`}>
                <span className="chat-role">{message.sender === 'user' ? 'You' : 'Legal AI'}</span>
                <p>{message.text}</p>
                {message.sender === 'assistant' && message.answerId && (
                  <button
                    className="simpler-button"
                    type="button"
                    onClick={() => handleSimplerAnswer(message)}
                    disabled={simplifyingId === message.id}
                  >
                    {simplifyingId === message.id
                      ? 'Simplifying...'
                      : message.simplified
                        ? 'Explained simply'
                        : 'Explain Simpler'}
                  </button>
                )}
                {message.sources?.length > 0 && (
                  <div className="chat-sources">
                    <strong>Sources from this document</strong>
                    {message.sources.map((source, index) => (
                      <div className="chat-source" key={`${message.id}-source-${index}`}>
                        <div className="chat-source-heading">
                          <span>
                            Section {source.section_number || 'Unavailable'}
                            {source.title ? `: ${source.title}` : ''}
                            {source.page ? ` (page ${source.page})` : ''}
                          </span>
                          <button
                            className="copy-citation-button"
                            type="button"
                            onClick={() => handleCopyCitation(source, `${message.id}-${index}`)}
                            aria-label="Copy citation"
                          >
                            {copiedCitation === `${message.id}-${index}` ? 'Copied' : 'Copy citation'}
                          </button>
                        </div>
                        <small>{source.text}</small>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble assistant loading-message" aria-live="polite">
                <span className="chat-role">Legal AI</span>
                <div className="typing-indicator" aria-label="Generating response">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          {notice && <div className="upload-status success">{notice}</div>}
          {error && <div className="form-alert">{error}</div>}
          <form className="chat-input-row" onSubmit={handleSubmitQuestion}>
            <input
              type="text"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Ask about this legal document..."
              aria-label="Ask a question about the uploaded document"
            />
            <button className="primary-button" type="submit" disabled={!chatInput.trim() || loading}>
              {loading ? 'Searching...' : 'Ask'}
            </button>
          </form>
        </div>

        {pdfUrl && (
          <aside className="pdf-viewer-panel">
            <div className="pdf-viewer-header">
              <div>
                <p className="eyebrow">Original file</p>
                <h2>PDF viewer</h2>
              </div>
              <button className="secondary-button compact-button" type="button" onClick={togglePdf}>
                Close PDF
              </button>
            </div>
            <iframe className="pdf-viewer" title={`Original PDF: ${selectedDocument.pdf_name}`} src={pdfUrl} />
          </aside>
        )}
      </section>
    </main>
  );
}

function DashboardPage({ session, onLogout, onNavigate, onOpenDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState({ type: '', message: '' });
  const [deletingDocumentId, setDeletingDocumentId] = useState(null);
  const [documentNotice, setDocumentNotice] = useState('');
  const [openDocumentMenuId, setOpenDocumentMenuId] = useState(null);
  const fileInputRef = useRef(null);

  async function refreshDocuments() {
    try {
      setLoading(true);
      setError('');
      const response = await fetchDocuments();
      setDocuments(response.documents || []);
    } catch (error) {
      setError(error.message || 'Unable to load documents');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function loadDocuments() {
      try {
        setLoading(true);
        setError('');
        const response = await fetchDocuments();
        if (active) {
          setDocuments(response.documents || []);
        }
      } catch (error) {
        if (active) {
          setError(error.message || 'Unable to load documents');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadDocuments();

    return () => {
      active = false;
    };
  }, [session.userId]);

  async function handleUploadSubmit(event) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadStatus({ type: 'error', message: 'Choose a PDF file before uploading.' });
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus({ type: 'error', message: 'Only PDF files are supported.' });
      return;
    }

    try {
      setUploading(true);
      setUploadStatus({ type: 'processing', message: 'Uploading PDF and extracting text...' });
      await uploadDocument(selectedFile);
      await refreshDocuments();
      setUploadStatus({ type: 'success', message: 'PDF uploaded successfully.' });
    } catch (error) {
      await refreshDocuments().catch(() => {});
      setUploadStatus({ type: 'error', message: error.message || 'Upload failed.' });
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteDocument(document) {
    if (deletingDocumentId || !window.confirm(`Delete ${document.pdf_name}? This permanently deletes the PDF, parsed data, and chat history.`)) {
      return;
    }

    try {
      setDeletingDocumentId(document.id);
      setDocumentNotice('');
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setOpenDocumentMenuId(null);
      setDocumentNotice('Document deleted successfully.');
    } catch {
      setDocumentNotice('Unable to delete document. Please try again.');
    } finally {
      setDeletingDocumentId(null);
    }
  }

  function handleFileSelection(file) {
    setSelectedFile(file || null);
    setUploadStatus({ type: '', message: '' });
  }

  function handleFileDrop(event) {
    event.preventDefault();
    handleFileSelection(event.dataTransfer.files?.[0]);
  }

  function resetUploadForm() {
    setSelectedFile(null);
    setUploadStatus({ type: '', message: '' });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  return (
    <main className="page dashboard-page">
      <header className="topbar dashboard-topbar">
        <div>
          <button className="brand-mark brand-button" type="button" onClick={() => onNavigate('landing')}>
            LexGov
          </button>
          <p className="topbar-subtitle">Personal document dashboard</p>
        </div>
        <div className="topbar-actions">
          <div className="user-pill">
            <strong>{session.name}</strong>
            <span>{session.email}</span>
          </div>
          <button className="secondary-button" type="button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>

      <section className="dashboard-layout">
        <aside className="dashboard-summary card-surface">
          <p className="eyebrow">Account overview</p>
          <h1>Welcome, {session.name}.</h1>
          <p>
            This workspace only surfaces the PDFs mapped to your account, keeping the view clean
            and focused.
          </p>
          <div className="summary-metrics">
            <div>
              <strong>{documents.length}</strong>
              <span>Linked PDFs</span>
            </div>
            <div>
              <strong>{loading ? 'Syncing' : 'Ready'}</strong>
              <span>Current status</span>
            </div>
          </div>

        </aside>

        <section className="documents-panel card-glass">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Your files</p>
              <h2>PDF list</h2>
            </div>
            <div className="document-list-actions">
              <span className="panel-chip">User-specific</span>
              <button
                className="upload-icon-button"
                type="button"
                onClick={() => setShowUploadForm((current) => !current)}
                aria-label={showUploadForm ? 'Close PDF upload form' : 'Upload a PDF'}
                title={showUploadForm ? 'Close PDF upload form' : 'Upload a PDF'}
              >
                {showUploadForm ? '×' : '+'}
              </button>
            </div>
          </div>

          {showUploadForm && (
            <form className="upload-card list-upload-card" onSubmit={handleUploadSubmit}>
              <label
                className={`upload-dropzone ${selectedFile ? 'has-file' : ''} ${uploading ? 'is-uploading' : ''} ${uploadStatus.type === 'success' ? 'is-complete' : ''}`}
                htmlFor="document-file-input"
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleFileDrop}
              >
                <span className="upload-dropzone-icon">
                  {uploadStatus.type === 'success' ? '✓' : 'PDF'}
                </span>
                <span className="upload-dropzone-copy">
                  <strong>{selectedFile ? selectedFile.name : 'Add a legal PDF'}</strong>
                  <span>
                    {uploading
                      ? 'Uploading and parsing your document...'
                      : uploadStatus.type === 'success'
                        ? 'Upload complete'
                        : selectedFile
                          ? 'Ready to upload'
                          : 'Click to browse or drag and drop here'}
                  </span>
                </span>
                {uploading && <span className="upload-spinner" aria-hidden="true" />}
                <input
                  ref={fileInputRef}
                  id="document-file-input"
                  className="upload-file-input"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => handleFileSelection(event.target.files?.[0])}
                  required
                />
              </label>

              <p className="upload-help">Upload a PDF to parse it and add it to your private document list.</p>

              {uploadStatus.type === 'processing' && (
                <div className="upload-processing" role="status">
                  <strong>Processing document</strong>
                  <span>Uploading PDF, extracting text, and identifying legal sections...</span>
                  <div className="processing-steps">
                    <span className="active">Processing</span>
                    <span>Ready after parsing</span>
                  </div>
                </div>
              )}

              {uploadStatus.type === 'success' && (
                <div className="upload-feedback upload-feedback-success" role="status">
                  <span className="upload-feedback-icon">✓</span>
                  <span>
                    <strong>PDF added successfully</strong>
                    <small>Your document is now available in the list below.</small>
                  </span>
                </div>
              )}

              {uploadStatus.type === 'error' && uploadStatus.message && (
                <div className={`upload-status ${uploadStatus.type}`}>
                  {uploadStatus.message}
                </div>
              )}

              {uploadStatus.type === 'success' ? (
                <button className="secondary-button submit-button" type="button" onClick={resetUploadForm}>
                  Upload another PDF
                </button>
              ) : (
                <button className="primary-button submit-button" type="submit" disabled={uploading}>
                  {uploading ? 'Uploading...' : 'Upload PDF'}
                </button>
              )}
            </form>
          )}

          {loading && <div className="empty-state">Loading your documents...</div>}
          {documentNotice && <div className="upload-status success">{documentNotice}</div>}
          {error && <div className="form-alert">{error}</div>}
          {!loading && !error && documents.length === 0 && (
            <div className="empty-state">
              No PDFs are linked to this account yet. Once documents are parsed, they will appear
              here.
            </div>
          )}

          {!loading && !error && documents.length > 0 && (
            <div className="document-grid">
              {documents.map((document) => (
                <article
                  className={`document-card ${document.status === 'completed' ? 'is-openable' : ''}`}
                  key={document.unique_identifier_name}
                  onClick={() => {
                    if (openDocumentMenuId === document.id) {
                      setOpenDocumentMenuId(null);
                    } else if (document.status === 'completed') {
                      onOpenDocument(document);
                    }
                  }}
                  onKeyDown={(event) => {
                    if ((event.key === 'Enter' || event.key === ' ') && document.status === 'completed') {
                      event.preventDefault();
                      onOpenDocument(document);
                    }
                  }}
                  role={document.status === 'completed' ? 'button' : undefined}
                  tabIndex={document.status === 'completed' ? 0 : undefined}
                >
                  <div className="document-icon">PDF</div>
                  <div>
                    <h3>{document.pdf_name}</h3>
                    <p>
                      {document.status === 'completed'
                        ? 'Ready for secure review.'
                        : document.status === 'failed'
                          ? 'Processing failed. Upload the file again to retry.'
                          : `Processing: ${document.stage.replaceAll('_', ' ')}`}
                    </p>
                    <div className="document-card-menu-wrap">
                      <button
                        type="button"
                        className="document-menu-button"
                        aria-label={`More actions for ${document.pdf_name}`}
                        aria-expanded={openDocumentMenuId === document.id}
                        title="More actions"
                        onClick={(event) => {
                          event.stopPropagation();
                          setOpenDocumentMenuId((current) => current === document.id ? null : document.id);
                        }}
                      >
                        <span aria-hidden="true">•••</span>
                      </button>
                      {openDocumentMenuId === document.id && (
                        <div className="document-card-menu" role="menu">
                          <button
                            type="button"
                            className="document-menu-delete"
                            role="menuitem"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteDocument(document);
                            }}
                            disabled={deletingDocumentId === document.id}
                          >
                            {deletingDocumentId === document.id ? 'Deleting...' : 'Delete document'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;