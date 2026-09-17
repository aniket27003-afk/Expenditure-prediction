const BASE = import.meta.env.VITE_API_URL || '';

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => req('/health'),
  createUser: (name, email) => req('/api/users', { method: 'POST', body: JSON.stringify({ name, email }) }),
  listUsers: () => req('/api/users'),
  addTransaction: (t) => req('/api/transactions', { method: 'POST', body: JSON.stringify(t) }),
  listTransactions: (user_id) => req(`/api/transactions?user_id=${user_id}&limit=100`),
  deleteTransaction: (id) => req(`/api/transactions/${id}`, { method: 'DELETE' }),
  dashboard: (user_id) => req(`/api/dashboard?user_id=${user_id}`),
  generateInsights: (user_id) => req(`/api/insights/generate?user_id=${user_id}`, { method: 'POST' }),
  listInsights: (user_id) => req(`/api/insights?user_id=${user_id}`),
  seed: (user_id) => req(`/api/seed?user_id=${user_id}`, { method: 'POST' }),
};
