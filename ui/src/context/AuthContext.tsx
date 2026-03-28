import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '../types';
import { setAuthToken, getAuthToken, googleAuth, fetchMe, fetchClientConfig } from '../api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  googleClientId: string;
  login: (idToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [googleClientId, setGoogleClientId] = useState('');

  // On mount: load Google client ID and check for existing JWT
  useEffect(() => {
    let cancelled = false;

    async function init() {
      // Fetch Google client ID for OAuth button
      try {
        const config = await fetchClientConfig();
        if (!cancelled) setGoogleClientId(config.google_client_id);
      } catch {
        // No client ID — auth might not be configured (local mode)
      }

      // Check existing JWT
      const token = getAuthToken();
      if (token) {
        try {
          const me = await fetchMe();
          if (!cancelled) setUser(me);
        } catch {
          // Token expired or invalid
          setAuthToken(null);
        }
      }
      if (!cancelled) setLoading(false);
    }

    init();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (idToken: string) => {
    const result = await googleAuth(idToken);
    setAuthToken(result.jwt);
    setUser(result.user);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, googleClientId, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
