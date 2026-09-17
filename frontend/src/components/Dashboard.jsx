import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts';

const COLORS = ['#22d3ee', '#a78bfa', '#f472b6', '#facc15', '#4ade80', '#fb923c', '#60a5fa', '#f87171', '#2dd4bf', '#e879f9'];

// Compact axis ticks: 45000 -> "₹45k"
const inrCompact = (v) => (v >= 1000 ? `₹${Math.round(v / 1000)}k` : `₹${v}`);

export default function Dashboard({ data }) {
  if (!data) return null;
  const catData = Object.entries(data.category_spending || {}).map(([name, value]) => ({ name, value }));
  const trendData = data.trend || [];

  return (
    <div className="card">
      <h2>Dashboard (PRD §4D — computed in Python/SQL)</h2>
      <div className="grid">
        <div className="stat"><h3>Total spending</h3><p>₹{(data.total_spending || 0).toLocaleString('en-IN')}</p></div>
        <div className="stat"><h3>Transactions</h3><p>{data.transaction_count}</p></div>
        <div className="stat"><h3>Avg. transaction</h3><p>₹{(data.average_transaction || 0).toLocaleString('en-IN')}</p></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, marginTop: 16 }}>
        <div>
          <h3>Category-wise spending</h3>
          {catData.length === 0 ? <p className="muted">No data yet.</p> : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={catData}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={95}
                  label={({ name, percent }) => (percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : '')}
                  labelLine={false}
                >
                  {catData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v, name) => [`₹${Number(v).toLocaleString('en-IN')}`, name]} />
                <Legend formatter={(v) => <span style={{ color: '#e2e8f0' }}>{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
        <div>
          <h3>Spending trend</h3>
          {trendData.length === 0 ? <p className="muted">No data yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="month" stroke="#94a3b8" tickLine={false} />
                <YAxis
                  stroke="#94a3b8"
                  width={55}
                  tickFormatter={inrCompact}
                  domain={[0, (dataMax) => Math.ceil(((dataMax || 0) * 1.15) / 5000) * 5000]}
                />
                <Tooltip formatter={(v) => `₹${Number(v).toLocaleString('en-IN')}`} />
                <Line type="monotone" dataKey="total" stroke="#22d3ee" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <h3>Top merchants</h3>
      <div className="row">
        {(data.top_merchants || []).map((m) => (
          <span key={m.merchant} className="pill">{m.merchant} · ₹{m.total.toLocaleString('en-IN')}</span>
        ))}
        {(data.top_merchants || []).length === 0 && <span className="muted">—</span>}
      </div>

      <h3>Recent transactions</h3>
      <table>
        <thead><tr><th>Date</th><th>Description</th><th>Merchant</th><th>Category</th><th>Amount</th></tr></thead>
        <tbody>
          {(data.recent_transactions || []).map((t) => (
            <tr key={t.id}>
              <td>{(t.transaction_date || '').slice(0, 10)}</td>
              <td>{t.description}</td>
              <td>{t.merchant}</td>
              <td><span className="pill">{t.category}</span></td>
              <td>₹{Number(t.amount).toLocaleString('en-IN')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
