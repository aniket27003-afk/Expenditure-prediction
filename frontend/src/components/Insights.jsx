export default function Insights({ result, history, onGenerate, busy }) {
  return (
    <div className="card">
      <h2>AI Spending Analysis (PRD §4E/F/G)</h2>
      <button onClick={onGenerate} disabled={busy}>{busy ? 'Analyzing…' : 'Generate AI Insights'}</button>
      {result && (
        <>
          <h3>💡 Spending insights</h3>
          <SummaryView value={result.summary} />
          <h3>🚨 Anomaly detection</h3>
          <AnomalyView value={result.anomalies} />
          <h3>🔮 Spending forecast <span className="muted" style={{ fontWeight: 400 }}>(AI estimate)</span></h3>
          <ForecastView value={result.forecast} />
        </>
      )}
      {history.length > 0 && (
        <>
          <h3>Saved insights</h3>
          {history.slice(0, 6).map((h) => (
            <div key={h.id} style={{ marginBottom: 12 }}>
              <span className="pill">{h.insight_type} · {(h.created_at || '').slice(0, 10)}</span>
              <div style={{ marginTop: 6 }}>
                {h.insight_type === 'summary' && <SummaryView value={h.message} compact />}
                {h.insight_type === 'anomaly' && <AnomalyView value={h.message} compact />}
                {h.insight_type === 'forecast' && <ForecastView value={h.message} compact />}
                {!['summary', 'anomaly', 'forecast'].includes(h.insight_type) && (
                  <div className="insight">{h.message}</div>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */

// Fresh /generate results arrive as objects; saved rows arrive as JSON strings;
// pre-existing rows are raw markdown text.
function asObject(value) {
  if (value && typeof value === 'object') return value;
  if (typeof value === 'string') {
    const t = value.trim();
    if (t.startsWith('{')) {
      try {
        const o = JSON.parse(t);
        if (o && typeof o === 'object') return o;
      } catch { /* legacy raw text */ }
    }
  }
  return null;
}

const inr = (v) => `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

function Legacy({ text }) {
  return <div className="insight">{text}</div>;
}

/* ---------- section views ---------- */

function SummaryView({ value, compact }) {
  const o = asObject(value);
  if (!o || !Array.isArray(o.bullets)) return <Legacy text={value} />;
  return (
    <div className="insight-grid">
      {o.bullets.map((b, i) => (
        <div key={i} className="insight-card">
          <h4>{b.title || `Insight ${i + 1}`}</h4>
          <p>{b.text}</p>
        </div>
      ))}
    </div>
  );
}

function AnomalyView({ value, compact }) {
  const o = asObject(value);
  if (!o || !Array.isArray(o.flagged)) return <Legacy text={value} />;
  return (
    <div>
      {o.flagged.length === 0 ? (
        <p className="ok-note">✅ No unusual transactions — everything looks normal.</p>
      ) : (
        <table>
          <thead><tr><th>Transaction</th><th>Why flagged</th></tr></thead>
          <tbody>
            {o.flagged.map((f, i) => (
              <tr key={i}><td><b>{f.transaction}</b></td><td>{f.reason}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {o.note && !compact && <p className="muted">{o.note}</p>}
      {o.note && compact && o.flagged.length > 0 && <p className="muted">{o.note}</p>}
    </div>
  );
}

function ForecastView({ value, compact }) {
  const o = asObject(value);
  if (!o || typeof o.baseline_low !== 'number' || typeof o.baseline_high !== 'number') {
    return <Legacy text={typeof value === 'object' ? (o?.reasoning || JSON.stringify(value)) : value} />;
  }
  return (
    <div>
      <div className="forecast-hero">
        <div className="muted">Expected next month</div>
        <div className="range">{inr(o.baseline_low)} – {inr(o.baseline_high)}</div>
      </div>
      {o.one_off && <p>📌 <b>One-off excluded:</b> {o.one_off}</p>}
      {o.reasoning && !compact && <p className="muted">{o.reasoning}</p>}
      <p className="muted" style={{ fontSize: '.75rem' }}>AI-generated estimate, not financial advice.</p>
    </div>
  );
}
