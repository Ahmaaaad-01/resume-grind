import { StrictMode, useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthProvider } from './context/AuthContext'
import { fetchClientConfig } from './api'
import './index.css'
import App from './App.tsx'

function Root() {
  const [clientId, setClientId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchClientConfig()
      .then(cfg => setClientId(cfg.google_client_id || ''))
      .catch(() => setClientId(''))  // local mode — no Google OAuth
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="text-text-body text-sm">Loading...</div>
      </div>
    );
  }

  // If no client ID configured (local mode), skip GoogleOAuthProvider
  if (!clientId) {
    return (
      <AuthProvider>
        <App />
      </AuthProvider>
    );
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </GoogleOAuthProvider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
