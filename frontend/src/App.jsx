import { useEffect, useState } from 'react';
import { api } from './api.js';
import AddTransaction from './components/AddTransaction.jsx';
import Dashboard from './components/Dashboard.jsx';
import Insights from './components/Insights.jsx';

export default function App() {
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [dash, setDash] = useState(null);
  const [insights, setInsights] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [backendOk, setBackendOk] = useState(null);

  async function refresh(uid) {
    if (!uid) return;
    try {
      setDash(await api.dashboard(uid));
      setHistory(await api.listInsights(uid));
    } catch (e) { setError(e.message); }
  }

  useEffect(() => {
    api.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false));
    api.listUsers().then((u) => {
      setUsers(u);
      if (u.length > 0) { setUserId(String(u[0].id)); refresh(u[0].id); }
    }).catch(() => {});
  }, []);

  async function handleCreateUser(e) {
    e.preventDefault();
    try {
      const u = await api.createUser(name, email);
      const list = await api.listUsers();
      setUsers(list); setUserId(String(u.id));
      setName(''); setEmail('');
      refresh(u.id);
    } catch (e) { setError(e.message); }
  }

  async function handleAdd(t) {
    await api.addTransaction({ user_id: Number(userId), ...t });
    refresh(Number(userId));
  }

  async function handleGenerate() {
    setBusy(true); setError('');
    try {
      const r = await api.generateInsights(Number(userId));
      setInsights(r);
      setHistory(await api.listInsights(Number(userId)));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>💸 Smart Expense & Spending Analyzer</h1>
          <p>LLM transaction understanding + Python/SQL analytics + AI insights</p>
        </div>
        <div className="muted">{backendOk === null ? '…' : backendOk ? '🟢 Backend connected' : '🔴 Backend offline — run uvicorn'}</div>
      </header>

      {error && <div className="card"><span className="error">{error}</span></div>}

      <div className="card">
        <h2>User</h2>
        <div className="row">
          <select value={userId} onChange={(e) => { setUserId(e.target.value); refresh(e.target.value); }}>
            <option value="">— select user —</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}
          </select>
          <button className="ghost" onClick={() => userId && api.seed(Number(userId)).then(() => refresh(Number(userId))).catch((e) => setError(e.message))}>
            Load demo data
          </button>
        </div>
        <form onSubmit={handleCreateUser} className="row" style={{ marginTop: 8 }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <button className="ghost" type="submit">Create user</button>
        </form>
      </div>

      {userId && (
        <>
          <AddTransaction onAdd={handleAdd} />
          <Dashboard data={dash} />
          <Insights result={insights} history={history} onGenerate={handleGenerate} busy={busy} />
        </>
      )}
      {!userId && <div className="card muted">Create or select a user to begin. Tip: use “Load demo data” for instant charts.</div>}
    </div>
  );
}
