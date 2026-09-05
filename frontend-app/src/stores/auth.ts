import { create } from 'zustand';
import { authApi, creditsApi, type User } from '../lib/api';

interface AuthState {
  user: User | null;
  credits: number;
  costPerForge: number;
  loading: boolean;
  desktopMode: boolean;
  setUser: (user: User | null) => void;
  setCredits: (credits: number) => void;
  checkAuth: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchCredits: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  credits: 0,
  costPerForge: 1,
  loading: true,
  desktopMode: new URLSearchParams(window.location.search).get('desktop') === '1',

  setUser: (user) => set({ user }),
  setCredits: (credits) => set({ credits }),

  checkAuth: async () => {
    const { desktopMode } = get();
    if (desktopMode) {
      set({ user: null, loading: false });
      return;
    }
    try {
      const r = await authApi.me();
      if (r?.user) {
        set({ user: r.user, loading: false });
        get().fetchCredits();
        return;
      }
    } catch {}
    set({ user: null, loading: false });
  },

  login: async (email, password) => {
    const r = await authApi.login(email, password);
    set({ user: r.user });
    if (r.credits != null) set({ credits: r.credits });
    get().fetchCredits();
  },

  signup: async (email, password, displayName) => {
    const r = await authApi.signup(email, password, displayName || '');
    set({ user: r.user, credits: r.credits });
  },

  logout: async () => {
    try { await authApi.logout(); } catch {}
    set({ user: null, credits: 0 });
  },

  fetchCredits: async () => {
    try {
      const c = await creditsApi.balance();
      set({ credits: c.balance, costPerForge: c.cost_per_forge });
    } catch {}
  },
}));
