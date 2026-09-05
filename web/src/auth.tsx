import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, clearTokens } from './api';
import type { User } from './types';

interface AuthValue {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<User>;
  logout(): Promise<void>;
  changePassword(currentPassword: string, newPassword: string): Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem('attendance_access')) {
      setLoading(false);
      return;
    }
    api
      .get<User>('/auth/me/')
      .then(({ data }) => setUser(data))
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const { data } = await api.post('/auth/login/', { email, password });
        localStorage.setItem('attendance_access', data.access);
        localStorage.setItem('attendance_refresh', data.refresh);
        setUser(data.user);
        return data.user;
      },
      async logout() {
        const refresh = localStorage.getItem('attendance_refresh');
        try {
          if (refresh) await api.post('/auth/logout/', { refresh });
        } catch {
          // Local sign-out must still complete when the API is unavailable.
        } finally {
          clearTokens();
          setUser(null);
        }
      },
      async changePassword(currentPassword, newPassword) {
        await api.post('/auth/change-password/', {
          current_password: currentPassword,
          new_password: newPassword,
        });
        setUser((current) => (current ? { ...current, must_change_password: false } : null));
      },
    }),
    [loading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is missing.');
  return value;
}
