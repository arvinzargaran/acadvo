import { createContext, useContext, useState, useEffect } from 'react';
import client from '../api/client';
import * as authApi from '../api/auth';
import { clearCachedUserData } from '../utils/localCache';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const { data } = await client.get('/users/me');
      setUser(data);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    fetchUser().finally(() => setIsLoading(false));
  }, []);

  const login = async (email, password) => {
    await authApi.login({ email, password });
    await fetchUser();
  };

  const register = async (registerData) => {
    await authApi.register(registerData);
    await fetchUser();
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    } finally {
      setUser(null);
      // Clearing React state does not touch localStorage, where the AI weekly
      // summary and DSA progress are cached — on a shared machine those would
      // otherwise be readable by whoever signs in next.
      clearCachedUserData();
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, login, register, logout, setUser, refreshUser: fetchUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
