'use client';

import { useEffect, useMemo, useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const CASE_CODE = 'CASE-001';
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const supabase = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

const products = ['Biberons', 'Tétines', 'Sucettes', 'Anneaux de dentition', 'Tasses d’apprentissage'];
const criteria = ['Prix', 'Marque connue', 'Qualité', 'Résistance', 'Silicone', 'Facilité de nettoyage', 'Disponibilité des accessoires', 'Design'];
const supplyOptions = ['Importateurs locaux', 'Grossistes', 'Distributeurs spécialisés', 'Achat direct fabricant', 'Autre'];
const demandLevels = ['Très forte', 'Forte', 'Moyenne', 'Faible', 'Inconnue'];

export default function Page() {
  const [caseId, setCaseId] = useState('');
  const [configError, setConfigError] = useState('');
  const [caseError, setCaseError] = useState('');
  const [form, setForm] = useState({
    outlet_name: '', outlet_type: 'Pharmacie', city: 'Cotonou', district: '', respondent_role: '',
    observed_at: new Date().toISOString().slice(0, 16), market_potential: '', observations: ''
  });
  const [demand, setDemand] = useState({});
  const [brands, setBrands] = useState(['', '', '', '']);
  const [prices, setPrices] = useState([
    { product: 'Biberon ~60 ml', brand: '', price: '' },
    { product: 'Biberon ~120/125 ml', brand: '', price: '' },
    { product: 'Biberon ~240/250 ml', brand: '', price: '' },
    { product: 'Tétines', brand: '', price: '' },
    { product: 'Sucettes', brand: '', price: '' }
  ]);
  const [selectedCriteria, setSelectedCriteria] = useState([]);
  const [supply, setSupply] = useState([]);
  const [priority, setPriority] = useState(['', '', '']);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!supabase) {
      setConfigError('Le formulaire n’est pas configuré. Merci de réessayer plus tard.');
      return;
    }
    (async () => {
      const { data, error } = await supabase
        .from('cases')
        .select('id')
        .eq('case_code', CASE_CODE)
        .maybeSingle();
      if (error || !data) {
        setCaseError('Impossible de préparer le formulaire.');
        return;
      }
      setCaseId(data.id);
    })();
  }, []);

  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
  const toggle = (arr, setter, value) => setter(arr.includes(value) ? arr.filter(x => x !== value) : [...arr, value]);

  async function submit(e) {
    e.preventDefault();
    if (!supabase || !caseId) {
      setError('Le formulaire n’est pas prêt. Veuillez réessayer.');
      return;
    }
    setBusy(true);
    setError('');
    const payload = {
      case_id: caseId,
      ...form,
      observed_at: new Date(form.observed_at).toISOString(),
      demand,
      brands: brands.filter(Boolean),
      prices: prices.filter(x => x.brand || x.price),
      customer_criteria: selectedCriteria,
      supply_channels: supply,
      priority_products: priority.filter(Boolean)
    };
    const { error: insertError } = await supabase.from('market_field_observations').insert(payload);
    setBusy(false);
    if (insertError) {
      setError('Impossible d’enregistrer l’observation. Veuillez réessayer.');
      return;
    }
    setDone(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const ready = useMemo(() => Boolean(caseId && supabase), [caseId]);

  if (done) return <main className="wrap"><div className="card success"><div className="mark">✓</div><h1>Merci.</h1><p>Votre observation a bien été enregistrée.</p><p className="muted">Cette information sera traitée comme une observation terrain.</p></div></main>;

  return <main className="wrap">
    <header>
      <div className="brand">ALAGBARA</div>
      <div className="eyebrow">HIMMA COMMERCIAL EXPANSION · MARKET INTELLIGENCE</div>
      <h1>Baby Care / Baby Feeding</h1>
      <p>Benin Field Check</p>
      <div className="note">Merci de renseigner uniquement ce que vous connaissez. Les estimations sont acceptées.</div>
    </header>

    {(configError || caseError) && <div className="error">{configError || caseError}</div>}

    <form onSubmit={submit}>
      <Section title="1 · Établissement">
        <div className="grid">
          <Field label="Nom de l’établissement" value={form.outlet_name} onChange={v => set('outlet_name', v)} required />
          <Select label="Type" value={form.outlet_type} onChange={v => set('outlet_type', v)} options={['Pharmacie', 'Boutique', 'Grossiste', 'Distributeur', 'Supermarché', 'Autre']} />
          <Field label="Ville" value={form.city} onChange={v => set('city', v)} />
          <Field label="Quartier" value={form.district} onChange={v => set('district', v)} />
          <Field label="Fonction du répondant" value={form.respondent_role} onChange={v => set('respondent_role', v)} />
        </div>
      </Section>

      <Section title="2 · Demande">
        <p className="hint">Niveau de demande observé</p>
        <div className="chips">{products.map(product => <label className="chipbox" key={product}><span>{product}</span><select value={demand[product] || ''} onChange={e => setDemand(prev => ({ ...prev, [product]: e.target.value }))}><option value="">—</option>{demandLevels.map(level => <option key={level}>{level}</option>)}</select></label>)}</div>
      </Section>

      <Section title="3 · Marques les plus présentes">
        {brands.map((value, i) => <Field key={i} label={`Marque ${i + 1}`} value={value} onChange={v => setBrands(prev => prev.map((x, j) => j === i ? v : x))} />)}
      </Section>

      <Section title="4 · Prix observés">
        {prices.map((row, i) => <div className="price" key={row.product}><b>{row.product}</b><Field label="Marque" value={row.brand} onChange={v => setPrices(prev => prev.map((x, j) => j === i ? { ...x, brand: v } : x))} /><Field label="Prix FCFA" type="number" value={row.price} onChange={v => setPrices(prev => prev.map((x, j) => j === i ? { ...x, price: v } : x))} /></div>)}
      </Section>

      <Section title="5 · Critères clients">
        <div className="checks">{criteria.map(item => <label key={item}><input type="checkbox" checked={selectedCriteria.includes(item)} onChange={() => toggle(selectedCriteria, setSelectedCriteria, item)} />{item}</label>)}</div>
      </Section>

      <Section title="6 · Approvisionnement">
        <div className="checks">{supplyOptions.map(item => <label key={item}><input type="checkbox" checked={supply.includes(item)} onChange={() => toggle(supply, setSupply, item)} />{item}</label>)}</div>
      </Section>

      <Section title="7 · Potentiel d’une nouvelle marque">
        <Select label="Votre avis" value={form.market_potential} onChange={v => set('market_potential', v)} options={['Oui', 'Oui, avec certaines conditions', 'Difficile', 'Non']} />
      </Section>

      <Section title="8 · Trois produits à tester en priorité">
        {priority.map((value, i) => <Field key={i} label={`Produit ${i + 1}`} value={value} onChange={v => setPriority(prev => prev.map((x, j) => j === i ? v : x))} />)}
      </Section>

      <Section title="9 · Observations terrain">
        <textarea value={form.observations} onChange={e => set('observations', e.target.value)} placeholder="Clients, concurrence, prix, fournisseurs, produits qui tournent…" />
      </Section>

      {error && <div className="error">{error}</div>}
      <button disabled={busy || !ready}>{busy ? 'Enregistrement…' : 'Enregistrer l’observation'}</button>
      <p className="foot">Source : FIELD FORM · BENIN · ALAGBARA — Commercial Expansion Layer.</p>
    </form>
  </main>;
}

function Section({ title, children }) { return <section className="card"><h2>{title}</h2>{children}</section>; }
function Field({ label, value, onChange, type = 'text', required = false }) { return <label className="field"><span>{label}</span><input required={required} type={type} value={value} onChange={e => onChange(e.target.value)} /></label>; }
function Select({ label, value, onChange, options }) { return <label className="field"><span>{label}</span><select value={value} onChange={e => onChange(e.target.value)}><option value="">Sélectionner…</option>{options.map(option => <option key={option}>{option}</option>)}</select></label>; }
