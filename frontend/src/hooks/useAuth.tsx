import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import api from '../api';
import { TokenResponse, LoginRequest, RegisterRequest } from '../types';

interface User {
  tenant_id: string;
  user_id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

function decodeToken(token: string): User | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return {
      tenant_id: payload.tenant_id,
      user_id: payload.sub,
      email: payload.email,
    };
  } catch {
    return null;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) return null;
  try {
    const resp = await api.post<TokenResponse>('/auth/refresh', {
      refresh_token: refresh,
    });
    const token = resp.data.access_token;
    localStorage.setItem('access_token', token);
    if (resp.data.refresh_token) {
      localStorage.setItem('refresh_token', resp.data.refresh_token);
    }
    return token;
  } catch {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      const decoded = decodeToken(token);
      if (decoded) {
        setUser(decoded);
      } else {
        refreshAccessToken().then((newToken) => {
          if (newToken) {
            const decoded = decodeToken(newToken);
            if (decoded) setUser(decoded);
          }
        });
      }
    }
  }, []);

  const login = async (data: LoginRequest) => {
    const resp = await api.post<TokenResponse>('/auth/login', data);
    localStorage.setItem('access_token', resp.data.access_token);
    localStorage.setItem('refresh_token', resp.data.refresh_token);
    localStorage.setItem('tenant_name', data.tenant_name);
    const decoded = decodeToken(resp.data.access_token);
    if (decoded) setUser(decoded);
  };

  const register = async (data: RegisterRequest) => {
    const resp = await api.post<TokenResponse>('/auth/register', data);
    localStorage.setItem('access_token', resp.data.access_token);
    localStorage.setItem('refresh_token', resp.data.refresh_token);
    localStorage.setItem('tenant_name', data.tenant_name);
    const decoded = decodeToken(resp.data.access_token);
    if (decoded) setUser(decoded);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('tenant_name');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
