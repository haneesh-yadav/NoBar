import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiFetch, getToken, setToken } from '../lib/api';

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  dob: string;
  gender: string;
  marital_status: string;
  disability_status: string;
  disability_type: string;
  caste_category: string;
  bpl_status: string;
  annual_income: number | null;
  employment_type: string;
  state: string;
  district: string;
  pincode: string;
  aadhaar_masked: string;
}

interface AuthContextValue {
  user: UserProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  updateProfile: (updates: Partial<UserProfile>) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    try {
      const data = await apiFetch<UserProfile>('/api/users/me');
      setUser(data);
    } catch (err: any) {
      if (err?.status === 401) setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiFetch<{ token: string; user: UserProfile }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setToken(data.token);
    setUser(data.user);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const data = await apiFetch<{ token: string; user: UserProfile }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    setToken(data.token);
    setUser(data.user);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  const updateProfile = async (updates: Partial<UserProfile>) => {
    const data = await apiFetch<UserProfile>('/api/users/me', {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
    setUser(data);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateProfile, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};