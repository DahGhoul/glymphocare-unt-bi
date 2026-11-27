import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiFetch, clearAuthSession, getStoredToken, getStoredUser, setAuthSession } from '../services/api';
import type { AuthUser } from '../types/glympho';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setSession: (token: string, user: AuthUser) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser<AuthUser>());
  const [loading, setLoading] = useState<boolean>(!!getStoredToken());

  useEffect(() => {
    const onUnauth = () => setUser(null);
    window.addEventListener('glympho:unauthorized', onUnauth);
    if (getStoredToken()) {
      apiFetch<AuthUser>('/api/auth/me')
        .then((u) => setUser(u))
        .catch(() => {
          clearAuthSession();
          setUser(null);
        })
        .finally(() => setLoading(false));
    }
    return () => window.removeEventListener('glympho:unauthorized', onUnauth);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string; user: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthSession(data.access_token, data.user);
    setUser(data.user);
  };

  const setSession = (token: string, newUser: AuthUser) => {
    setAuthSession(token, newUser);
    setUser(newUser);
  };

  const logout = () => {
    clearAuthSession();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setSession }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
