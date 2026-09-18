const BASE = '';

// Per-launch capability token (task 03): injected by the server into served
// pages via <meta name="clpz-capability">. Read at startup; sent on
// state-changing requests. Never logged and never placed in URLs.
const CAPABILITY =
  typeof document !== 'undefined'
    ? document.querySelector('meta[name="clpz-capability"]')?.content || ''
    : '';

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const method = (opts.method || 'GET').toUpperCase();
  const headers: Record<string, string> = Object.assign({}, opts.headers as Record<string, string>);
  if (CAPABILITY && method !== 'GET' && method !== 'HEAD') {
    headers['X-CLPZ-Capability'] = CAPABILITY;
  }
  const r = await fetch(BASE + path, Object.assign({}, opts, { headers }));
  const ct = r.headers.get('content-type') || '';
  const d = ct.includes('application/json') ? await r.json() : null;
  if (!r.ok) throw new Error(d?.detail || d?.message || `Request failed (${r.status})`);
  return d as T;
}

export interface User {
  id: string;
  email: string;
  display_name?: string;
  email_verified?: boolean;
  credits?: number;
}

export interface CreditBalance {
  balance: number;
  cost_per_forge: number;
}

export interface Clip {
  index: number;
  title?: string;
  hook?: string;
  start: number;
  end: number;
  duration?: number;
  status: string;
  stream_url?: string;
  download_url?: string;
  thumbnail_url?: string;
  validation?: {
    width?: number;
    height?: number;
    video_codec?: string;
    audio_codec?: string;
    duration?: number;
  };
  caption_words?: Array<{ word: string; start: number; end: number }>;
  ass_file?: string;
  layout?: string;
  render_plan?: { mode?: string };
}

export interface Job {
  id: string;
  stage: string;
  progress?: number;
  input_type?: string;
  video?: { title?: string };
  clips: Clip[];
  created_at?: number;
  started_at?: number;
  completed_at?: number;
  failed_at?: number;
  error?: string;
}

export interface Diagnostics {
  ffmpeg?: string;
  ffprobe?: string;
  'yt-dlp'?: string;
  whisper?: string;
  ram_total_gb?: number;
  ram_available_gb?: number;
  ram_percent?: number;
  disk_free_gb?: number;
  cpu_count?: number;
}

// Auth
export const authApi = {
  signup: (email: string, password: string, display_name = '') =>
    api<{ user: User; credits: number }>('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    api<{ user: User; credits: number; email_verified?: boolean }>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  logout: () => api('/api/auth/logout', { method: 'POST' }),
  me: () => api<{ user: User }>('/api/auth/me'),
};

// Credits
export const creditsApi = {
  balance: () => api<CreditBalance>('/api/credits/balance'),
  transactions: () => api<{ transactions: unknown[] }>('/api/credits/transactions'),
};

// Jobs
export const jobsApi = {
  list: () => api<Job[]>('/api/jobs'),
  get: (id: string) => api<Job>(`/api/jobs/${id}`),
  createYouTube: (url: string, max_clips = 5, idempotency_key?: string) =>
    api<{ job_id: string; credits_remaining?: number }>('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_clips, idempotency_key }),
    }),
  upload: (file: File, max_clips = 5, idempotency_key?: string) => {
    const b = new FormData();
    b.append('file', file);
    b.append('max_clips', String(max_clips));
    if (idempotency_key) b.append('idempotency_key', idempotency_key);
    return api<{ job_id: string; credits_remaining?: number }>('/api/jobs/upload', {
      method: 'POST',
      body: b,
    });
  },
  cancel: (id: string) => api(`/api/jobs/${id}/cancel`, { method: 'POST' }),
  edit: (jobId: string, clipIndex: number, editState: unknown) =>
    api<{ folder: string }>(`/api/jobs/${jobId}/clips/${clipIndex}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editState),
    }),
  saveClip: (jobId: string, clipIndex: number) =>
    api<{ folder: string }>(`/api/jobs/${jobId}/clips/${clipIndex}/save`, { method: 'POST' }),
};

// Diagnostics
export const diagnosticsApi = {
  get: () => api<Diagnostics>('/api/diagnostics'),
};

// Admin
export const adminApi = {
  stats: () => api<Record<string, unknown>>('/api/admin/stats'),
  users: () => api<{ users: User[] }>('/api/admin/users'),
  searchUsers: (q: string) => api<{ users: User[] }>(`/api/admin/users/search?q=${encodeURIComponent(q)}`),
  transactions: (userId: string) => api<{ transactions: unknown[] }>(`/api/admin/transactions/${userId}`),
  addCredits: (userId: string, amount: number, reason: string) =>
    api<{ new_balance: number }>(`/api/admin/credits/add?user_id=${userId}&amount=${amount}&reason=${encodeURIComponent(reason)}`, { method: 'POST' }),
  removeCredits: (userId: string, amount: number, reason: string) =>
    api<{ new_balance: number }>(`/api/admin/credits/remove?user_id=${userId}&amount=${amount}&reason=${encodeURIComponent(reason)}`, { method: 'POST' }),
  jobs: (limit = 20) => api<{ jobs: Job[] }>(`/api/admin/jobs?limit=${limit}`),
};
