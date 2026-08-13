import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchDocuments, login, signup, uploadDocument } from './api';

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
  const [view, setView] = useState(() => getViewFromHash(window.location.hash));

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
      setView(getViewFromHash(window.location.hash));
    }

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  useEffect(() => {
    if (session && (view === 'login' || view === 'signup')) {
      setHashRoute('dashboard');
    }
  }, [session, view]);

  const resolvedView = session || view !== 'dashboard' ? view : 'dashboard';

  function handleNavigate(nextView) {
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
            handleNavigate('landing');
          }}
          onNavigate={handleNavigate}
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

  return 'landing';
}

function setHashRoute(nextView) {
  const nextPath = ROUTES[nextView] || ROUTES.landing;
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
            <div className="panel-item">
              <span>01</span>
              <div>
                <strong>Sign up</strong>
                <p>Register a profile in seconds.</p>
              </div>
            </div>
            <div className="panel-item">
              <span>02</span>
              <div>
                <strong>Log in</strong>
                <p>Access your personal document area.</p>
              </div>
            </div>
            <div className="panel-item">
              <span>03</span>
              <div>
                <strong>View PDFs</strong>
                <p>See the documents linked to your account.</p>
              </div>
            </div>
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
      const nextSession = {
        userId: Number(result.user_id),
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

function DashboardPage({ session, onLogout, onNavigate }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState({ type: '', message: '' });
  const fileInputRef = useRef(null);

  async function refreshDocuments() {
    try {
      setLoading(true);
      setError('');
      const response = await fetchDocuments(session.userId);
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
        const response = await fetchDocuments(session.userId);
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
      setUploadStatus({ type: '', message: '' });
      await uploadDocument(session.userId, selectedFile);
      await refreshDocuments();
      setShowUploadForm(false);
      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      setUploadStatus({ type: 'success', message: 'PDF uploaded successfully.' });
    } catch (error) {
      setUploadStatus({ type: 'error', message: error.message || 'Upload failed.' });
    } finally {
      setUploading(false);
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
          <button className="primary-button" type="button" onClick={() => setShowUploadForm((current) => !current)}>
            {showUploadForm ? 'Close upload' : 'Add PDF'}
          </button>
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

          <button className="secondary-button upload-trigger" type="button" onClick={() => setShowUploadForm((current) => !current)}>
            {showUploadForm ? 'Hide upload form' : 'Add PDF'}
          </button>

          {showUploadForm && (
            <form className="upload-card" onSubmit={handleUploadSubmit}>
              <label className="upload-field">
                Select PDF
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => {
                    const file = event.target.files?.[0] || null;
                    setSelectedFile(file);
                    setUploadStatus({ type: '', message: '' });
                  }}
                  required
                />
              </label>

              <p className="upload-help">Upload a PDF to link it to this account and generate the parsed JSON record automatically.</p>

              {uploadStatus.message && (
                <div className={`upload-status ${uploadStatus.type}`}>
                  {uploadStatus.message}
                </div>
              )}

              <button className="primary-button submit-button" type="submit" disabled={uploading}>
                {uploading ? 'Uploading...' : 'Upload PDF'}
              </button>
            </form>
          )}
        </aside>

        <section className="documents-panel card-glass">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Your files</p>
              <h2>PDF list</h2>
            </div>
            <span className="panel-chip">User-specific</span>
          </div>

          {loading && <div className="empty-state">Loading your documents...</div>}
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
                <article className="document-card" key={document.unique_identifier_name}>
                  <div className="document-icon">PDF</div>
                  <div>
                    <h3>{document.pdf_name}</h3>
                    <p>Stored securely in your account.</p>
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