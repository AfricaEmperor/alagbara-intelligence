'use client';
import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

// ── ALAGBARA / HIMMA Commercial Expansion — dedicated Supabase project ──
// Strictly separate from himma-foods-crm. Do not point this at the Foods CRM.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://hbcxiyyuqgjokvypqrqr.supabase.co';
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_2XRZBSdnfnDep4yQAwYeFA_K8MCWzas';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const products = ['Biberons','Tétines','Sucettes','Anneaux de dentition','Tasses d’apprentissage'];
const criteria = ['Prix','Marque connue','Qualité','Résistance','Silicone','Facilité de nettoyage','Disponibilité des accessoires','Design'];

export default function Page(){
  const [cases,setCases]=useState([]);
  const [caseId,setCaseId]=useState('');
  const [casesError,setCasesError]=useState('');
  const [form,setForm]=useState({outlet_name:'',outlet_type:'Pharmacie',city:'Cotonou',district:'',respondent_role:'',observed_at:new Date().toISOString().slice(0,16),market_potential:'',observations:''});
  const [demand,setDemand]=useState({});
  const [brands,setBrands]=useState(['','','','']);
  const [prices,setPrices]=useState([{product:'Biberon ~60 ml',brand:'',price:''},{product:'Biberon ~120/125 ml',brand:'',price:''},{product:'Biberon ~240/250 ml',brand:'',price:''},{product:'Tétines',brand:'',price:''},{product:'Sucettes',brand:'',price:''}]);
  const [selectedCriteria,setSelectedCriteria]=useState([]);
  const [supply,setSupply]=useState([]);
  const [priority,setPriority]=useState(['','','']);
  const [busy,setBusy]=useState(false);
  const [done,setDone]=useState(false);
  const [error,setError]=useState('');

  const set=(k,v)=>setForm({...form,[k]:v});
  const toggle=(arr,setter,v)=>setter(arr.includes(v)?arr.filter(x=>x!==v):[...arr,v]);

  useEffect(()=>{
    (async()=>{
      const {data,error}=await supabase.from('cases').select('id,case_code,name').order('opened_at',{ascending:true});
      if(error){setCasesError(error.message);return;}
      setCases(data||[]);
      const defaultCase=(data||[]).find(c=>c.case_code==='CASE-001')||(data||[])[0];
      if(defaultCase) setCaseId(defaultCase.id);
    })();
  },[]);

  async function submit(e){
    e.preventDefault();
    if(!caseId){setError('Aucun dossier (case) sélectionné.');return;}
    setBusy(true);setError('');
    const payload={case_id:caseId,...form,observed_at:new Date(form.observed_at).toISOString(),demand,brands:brands.filter(Boolean),prices:prices.filter(x=>x.brand||x.price),customer_criteria:selectedCriteria,supply_channels:supply,priority_products:priority.filter(Boolean)};
    const {error}=await supabase.from('market_field_observations').insert(payload);
    setBusy(false); if(error){setError(error.message);return;} setDone(true); window.scrollTo({top:0,behavior:'smooth'});
  }

  if(done) return <main className="wrap"><div className="card success"><div className="mark">✓</div><h1>Merci.</h1><p>Votre observation a bien été enregistrée.</p><p className="muted">Cette information sera traitée comme une observation terrain, rattachée au dossier sélectionné.</p></div></main>;

  return <main className="wrap"><header><div className="brand">ALAGBARA</div><div className="eyebrow">HIMMA COMMERCIAL EXPANSION · MARKET INTELLIGENCE</div><h1>Baby Care / Baby Feeding</h1><p>Benin Field Check</p><div className="note">Merci de renseigner uniquement ce que vous connaissez. Les estimations sont acceptées.</div></header>
  <form onSubmit={submit}>
  <Section title="0 · Dossier (Case)">{casesError && <div className="error">Impossible de charger les dossiers : {casesError}</div>}<label className="field"><span>Dossier concerné</span><select value={caseId} onChange={e=>setCaseId(e.target.value)} required><option value="">Sélectionner…</option>{cases.map(c=><option key={c.id} value={c.id}>{c.case_code} — {c.name}</option>)}</select></label></Section>
  <Section title="1 · Établissement"><div className="grid"><Field label="Nom de l’établissement" value={form.outlet_name} onChange={v=>set('outlet_name',v)} required/><Select label="Type" value={form.outlet_type} onChange={v=>set('outlet_type',v)} options={['Pharmacie','Boutique','Grossiste','Distributeur','Supermarché','Autre']}/><Field label="Ville" value={form.city} onChange={v=>set('city',v)}/><Field label="Quartier" value={form.district} onChange={v=>set('district',v)}/><Field label="Fonction du répondant" value={form.respondent_role} onChange={v=>set('respondent_role',v)}/></div></Section>
  <Section title="2 · Demande"><p className="hint">Niveau de demande observé</p><div className="chips">{products.map(p=><label className="chipbox" key={p}><span>{p}</span><select value={demand[p]||''} onChange={e=>setDemand({...demand,[p]:e.target.value})}><option value="">—</option><option>Très forte</option><option>Forte</option><option>Moyenne</option><option>Faible</option><option>Inconnue</option></select></label>)}</div></Section>
  <Section title="3 · Marques les plus présentes">{brands.map((v,i)=><Field key={i} label={`Marque ${i+1}`} value={v} onChange={x=>{let a=[...brands];a[i]=x;setBrands(a)}}/> )}</Section>
  <Section title="4 · Prix observés">{prices.map((r,i)=><div className="price" key={i}><b>{r.product}</b><Field label="Marque" value={r.brand} onChange={v=>{let a=[...prices];a[i]={...a[i],brand:v};setPrices(a)}}/><Field label="Prix FCFA" type="number" value={r.price} onChange={v=>{let a=[...prices];a[i]={...a[i],price:v};setPrices(a)}}/></div>)}</Section>
  <Section title="5 · Critères clients"><div className="checks">{criteria.map(c=><label key={c}><input type="checkbox" checked={selectedCriteria.includes(c)} onChange={()=>toggle(selectedCriteria,setSelectedCriteria,c)}/>{c}</label>)}</div></Section>
  <Section title="6 · Approvisionnement"><div className="checks">{['Importateurs locaux','Grossistes','Distributeurs spécialisés','Achat direct fabricant','Autre'].map(c=><label key={c}><input type="checkbox" checked={supply.includes(c)} onChange={()=>toggle(supply,setSupply,c)}/>{c}</label>)}</div></Section>
  <Section title="7 · Potentiel d’une nouvelle marque"><Select label="Votre avis" value={form.market_potential} onChange={v=>set('market_potential',v)} options={['Oui','Oui, avec certaines conditions','Difficile','Non']}/></Section>
  <Section title="8 · Trois produits à tester en priorité">{priority.map((v,i)=><Field key={i} label={`Produit ${i+1}`} value={v} onChange={x=>{let a=[...priority];a[i]=x;setPriority(a)}}/>)}</Section>
  <Section title="9 · Observations terrain"><textarea value={form.observations} onChange={e=>set('observations',e.target.value)} placeholder="Clients, concurrence, prix, fournisseurs, produits qui tournent…"/></Section>
  {error && <div className="error">Impossible d’enregistrer : {error}</div>}
  <button disabled={busy}>{busy?'Enregistrement…':'Enregistrer l’observation'}</button>
  <p className="foot">Source : FIELD FORM · BENIN · ALAGBARA — Commercial Expansion Layer.</p>
  </form></main>
}
function Section({title,children}){return <section className="card"><h2>{title}</h2>{children}</section>}
function Field({label,value,onChange,type='text',required=false}){return <label className="field"><span>{label}</span><input required={required} type={type} value={value} onChange={e=>onChange(e.target.value)}/></label>}
function Select({label,value,onChange,options}){return <label className="field"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}><option value="">Sélectionner…</option>{options.map(o=><option key={o}>{o}</option>)}</select></label>}
