export default function Insights({ result, history, onGenerate, busy }) {
  return (
    <div className="card">
      <h2>AI Spending Analysis (PRD §4E/F/G)</h2>
      <button onClick={onGenerate} disabled={busy}>{busy ? 'Asking Grok…' : 'Generate AI Insights'}</button>
      {result && (
        <>
          <h3>Spending insights</h3>
          <div className="insight">{result.summary}</div>
          <h3>Anomaly detection</h3>
          <div className="insight">{result.anomalies}</div>
          <h3>Spending forecast (AI estimate)</h3>
          <div className="insight">{result.forecast}</div>
        </>
      )}
      {history.length > 0 && (
        <>
          <h3>Saved insights</h3>
          {history.slice(0, 6).map((h) => (
            <div key={h.id} className="insight"><b>[{h.insight_type}]</b> {h.message}</div>
          ))}
        </>
      )}
    </div>
  );
}
