'use client';

import { useState } from 'react';
import styles from './page.module.css';

export default function AskBigPage() {
  const [form, setForm] = useState({ question: '', market: 'Nigeria', decision: '', useful: '' });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  async function submit(e) {
    e.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch('/api/intelligence-request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, source: 'big-consulting-ui' }) });
      const data = await response.json();
      if (!response.ok && response.status !== 202) throw new Error(data.error || 'Intelligence request failed');
      setResult(data);
    } catch (err) { setError(err.message || 'Intelligence request failed'); }
    finally { setBusy(false); }
  }

  return <main className={styles.wrap}>
    <header className={styles.header}>
      <div className={styles.brand}>ALAGBARA</div>
      <div className={styles.eyebrow}>BIG CONSULTING · ASK BIG</div>
      <h1 className={styles.title}>Ask BIG</h1>
      <p className={styles.subtitle}>Turn an economic question into a structured intelligence request.</p>
    </header>

    <form onSubmit={submit} className={styles.card}>
      <label className={styles.label}><span>What do you need to understand?</span><textarea className={styles.textarea} required maxLength={4000} value={form.question} onChange={e => set('question', e.target.value)} placeholder="Example: What are the key observable developments around the Dangote IPO, and what commercial implications should we investigate next?" /></label>
      <div className={styles.grid}>
        <label className={styles.label}><span>Market</span><input className={styles.input} value={form.market} onChange={e => set('market', e.target.value)} placeholder="Nigeria" /></label>
        <label className={styles.label}><span>Decision</span><input className={styles.input} value={form.decision} onChange={e => set('decision', e.target.value)} placeholder="What decision will this inform?" /></label>
      </div>
      <label className={styles.label}><span>What would make the answer useful?</span><textarea className={styles.textarea} value={form.useful} onChange={e => set('useful', e.target.value)} placeholder="Current facts, changes, unknowns, implications, next actions…" /></label>
      {error && <div className={styles.error}>{error}</div>}
      <button className={styles.button} disabled={busy}>{busy ? 'SCOUTING / ANALYZING…' : 'ASK BIG'}</button>
    </form>

    {result && <section className={`${styles.card} ${styles.result}`}>
      <div className={styles.status}>REQUEST · {result.status}</div>
      {result.request_id && <div className={styles.id}>{result.request_id}</div>}
      {result.intelligence && <>
        <h2>Pulse</h2><p>{result.intelligence.pulse}</p>
        <h2>Facts</h2><ul>{result.intelligence.facts.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <h2>Unknowns</h2><ul>{result.intelligence.unknowns.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <h2>Analysis</h2><p>{result.intelligence.analysis}</p>
        <h2>Next step</h2><p>{result.intelligence.recommendation}</p>
        <div className={styles.confidence}>Confidence: {result.intelligence.confidence}</div>
      </>}
      {result.next && <p>{result.next}</p>}
    </section>}
  </main>;
}
