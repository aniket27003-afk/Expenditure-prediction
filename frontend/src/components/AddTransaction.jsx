import { useState } from 'react';

const METHODS = ['UPI', 'Cash', 'Debit Card', 'Credit Card', 'Netbanking', 'Wallet'];

export default function AddTransaction({ onAdd }) {
  const [form, setForm] = useState({ amount: '', description: '', payment_method: 'UPI', transaction_date: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setMsg('');
    try {
      await onAdd({
        amount: parseFloat(form.amount),
        description: form.description,
        payment_method: form.payment_method,
        transaction_date: form.transaction_date ? new Date(form.transaction_date).toISOString() : null,
      });
      setMsg('Saved + auto-categorized by AI.');
      setForm({ amount: '', description: '', payment_method: 'UPI', transaction_date: '' });
    } catch (err) {
      setMsg('Error: ' + err.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h2>Add Expense (PRD §4A)</h2>
      <form onSubmit={submit} className="row">
        <input type="number" step="0.01" required placeholder="Amount ₹" value={form.amount} onChange={set('amount')} />
        <input required placeholder="e.g. UPI-UBER-TRIP-284" style={{ flex: 2, minWidth: 220 }} value={form.description} onChange={set('description')} />
        <select value={form.payment_method} onChange={set('payment_method')}>
          {METHODS.map((m) => <option key={m}>{m}</option>)}
        </select>
        <input type="date" value={form.transaction_date} onChange={set('transaction_date')} />
        <button disabled={busy}>{busy ? 'Analyzing…' : 'Add + AI Categorize'}</button>
      </form>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
