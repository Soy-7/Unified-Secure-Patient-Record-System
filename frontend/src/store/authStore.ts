import { create } from 'zustand';
import type { UserResponse } from '../types';

interface AuthState {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: UserResponse, token: string) => void;
  logout: () => void;
  initialize: () => void;
}

const getInitialState = () => {
  const token = localStorage.getItem('ehr_token');
  const raw   = localStorage.getItem('ehr_user');
  if (token && raw) {
    try {
      const user = JSON.parse(raw) as UserResponse;
      return { user, token, isAuthenticated: true };
    } catch {
      localStorage.removeItem('ehr_token');
      localStorage.removeItem('ehr_user');
    }
  }
  return { user: null, token: null, isAuthenticated: false };
};

export const useAuthStore = create<AuthState>((set) => ({
  ...getInitialState(),

  login: (user, token) => {
    localStorage.setItem('ehr_token', token);
    localStorage.setItem('ehr_user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('ehr_token');
    localStorage.removeItem('ehr_user');
    set({ user: null, token: null, isAuthenticated: false });
  },

  initialize: () => {
    set(getInitialState());
  },
}));
