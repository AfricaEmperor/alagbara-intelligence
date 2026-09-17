'use client';

import { useState } from 'react';
import styles from './page.module.css';

const copy = {
  question: { en: 'What do you need to understand?', fr: 'Que devez-vous comprendre ?' },
  market: { en: 'Market', fr: 'Marché' },
  decision: { en: 'Decision', fr: 'Décision' },
  useful: { en: 'What would make the answer useful?', fr: 'Qu’est-ce qui rendrait la réponse utile ?' },
  example: { en: 'Example: What are the key observable developments around the Dangote IPO, and what commercial implications should we investigate next?', fr: 'Exemple : Quels sont les principaux développements observables autour de l’IPO de Dangote et quelles implications commerciales devons-nous examiner ensuite ?' },
  decisionPlaceholder: { en: 'What decision will this inform?', fr: 'Quelle décision cette analyse doit-elle éclairer ?' },
  usefulPlaceholder: { en: 'Current facts, changes, unknowns, implications, next actions…', fr: 'Faits actuels, changements, inconnues, implications, prochaines actions…' },
  intro: { en: 'Turn an economic question into a structured intelligence request.', fr: 'Transformez une question économique en demande d’intelligence structurée.' },
  pulse: { en: 'Pulse', fr: 'Pulse' },
  facts: { en: 'Facts', fr: 'Faits' },
  unknowns: { en: 'Unknowns', fr: 'Inconnues' },
  assumptions: { en: 'Assumptions', fr: 'Hypothèses' },
  analysis: { en: 'Analysis', fr: 'Analyse' },
  next: { en: 'Next step', fr: 'Prochaine étape' },
  risks: { en: 'Risks', fr: 'Risques' },
  confidence: { en: 'Confidence', fr: 'Niveau de confiance' },
  asking: { en: 'SCOUTING / ANALYZING…', fr: 'SCOUTING / ANALYSE…' },
  submit: { en: 'ASK BIG', fr: 'ASK BIG' },
  request: { en: 'REQUEST', fr: 'DEMANDE' },
  pending: { en: 'Intelligence processing pending.', fr: 'Traitement de l’intelligence en attente.' },
};

function Bi({ en, fr, className = '' }) {
  return <span className={className}><span>{en}</span><small>{fr}</small></span>;
}

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
      if (!response.ok && response.status !== 202) throw new Error(data.error || 'Intelligence request failed / Échec de la demande d’intelligence');
      setResult(data);
    } catch (err) { setError(err.message || 'Intelligence request failed / Échec de la demande d’intelligence'); }
    finally { setBusy(false); }
  }

  return <main className={styles.wrap}>
    <header className={styles.header}>
      <div className={styles.brand}>ALAGBARA</div>
      <div className={styles.eyebrow}>BIG CONSULTING · ASK BIG</div>
      <h1 className={styles.title}>Ask BIG</h1>
      <p className={styles.subtitle}>{copy.intro.en}<br /><span>{copy.intro.fr}</span></p>
    </header>

    <form onSubmit={submit} className={styles.card}>
      <label className={styles.label}><Bi {...copy.question} />
        <textarea className={styles.textarea} required maxLength={4000} value={form.question} onChange={e => set('question', e.target.value)} placeholder={`${copy.example.en}\n${copy.example.fr}`} />
      </label>
      <div className={styles.grid}>
        <label className={styles.label}><Bi {...copy.market} /><input className={styles.input} value={form.market} onChange={e => set('market', e.target.value)} placeholder="Nigeria / Nigeria" /></label>
        <label className={styles.label}><Bi {...copy.decision} /><input className={styles.input} value={form.decision} onChange={e => set('decision', e.target.value)} placeholder={`${copy.decisionPlaceholder.en} / ${copy.decisionPlaceholder.fr}`} /></label>
      </div>
      <label className={styles.label}><Bi {...copy.useful} />
        <textarea className={styles.textarea} value={form.useful} onChange={e => set('useful', e.target.value)} placeholder={`${copy.usefulPlaceholder.en}\n${copy.usefulPlaceholder.fr}`} />
      </label>
      {error && <div className={styles.error}>{error}</div>}
      <button className={styles.button} disabled={busy}>{busy ? copy.asking.en + ' / ' + copy.asking.fr : copy.submit.en}</button>
    </form>

    {result && <section className={`${styles.card} ${styles.result}`}>
      <div className={styles.status}>{copy.request.en} · {copy.request.fr} · {result.status}</div>
      {result.request_id && <div className={styles.id}>{result.request_id}</div>}
      {result.intelligence && <>
        <Bi {...copy.pulse} className={styles.resultHeading} /><p>{result.intelligence.pulse}</p>
        <Bi {...copy.facts} className={styles.resultHeading} /><ul>{result.intelligence.facts.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <Bi {...copy.unknowns} className={styles.resultHeading} /><ul>{result.intelligence.unknowns.map((x, i) => <li key={i}>{x}</li>)}</ul>
        {result.intelligence.assumptions?.length > 0 && <><Bi {...copy.assumptions} className={styles.resultHeading} /><ul>{result.intelligence.assumptions.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
        <Bi {...copy.analysis} className={styles.resultHeading} /><p>{result.intelligence.analysis}</p>
        <Bi {...copy.next} className={styles.resultHeading} /><p>{result.intelligence.recommendation}</p>
        {result.intelligence.risks?.length > 0 && <><Bi {...copy.risks} className={styles.resultHeading} /><ul>{result.intelligence.risks.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
        <div className={styles.confidence}>{copy.confidence.en} / {copy.confidence.fr}: {result.intelligence.confidence}</div>
      </>}
      {result.next && <p>{copy.pending.en}<br /><span>{copy.pending.fr}</span></p>}
    </section>}
  </main>;
}
