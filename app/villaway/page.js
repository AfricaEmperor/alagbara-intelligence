import styles from './dashboard.module.css';

const gates = [
  { id: 'SPEC', title: 'Dashboard specification + data contract', lane: 'FOUNDATION', state: 'READY_FOR_REVIEW', note: 'Committed to the isolated VILLAWAY branch; review evidence still required.' },
  { id: 'UI', title: 'Isolated dashboard interface', lane: 'ENGINEERING', state: 'IN_PROGRESS', note: 'Read-only route; no live commercial connection.' },
  { id: 'SRC', title: 'Authoritative source adapters', lane: 'IN_PROGRESS', note: 'GitHub metadata is partially verified; VILLAWAY commercial read model is not connected.' },
  { id: 'QA', title: 'Build, responsive and contract validation', lane: 'GOVERNANCE', state: 'NOT_STARTED', note: 'Must be executed in the repository runtime before release.' },
  { id: 'PILOT', title: 'One attributable paid hospitality transaction', lane: 'COMMERCIAL', state: 'NOT_STARTED', note: 'No commercial transaction evidence is connected to this dashboard.' }
];

const blockers = [
  { severity: 'HIGH', title: 'No verified VILLAWAY commercial read model', detail: 'Buyer, requirement, property, booking and commission records cannot yet be presented as live operational data.', state: 'OPEN' },
  { severity: 'HIGH', title: 'Dashboard runtime validation pending', detail: 'The Next.js build and browser review have not yet been run in the repository environment.', state: 'OPEN' },
  { severity: 'MEDIUM', title: 'Access-control readiness not established', detail: 'Keep this surface synthetic/read-only until server-side authorization and tenant boundaries are verified.', state: 'OPEN' }
];

function State({ value }) {
  const key = (value || 'UNKNOWN').toLowerCase().replaceAll('_', '-');
  return <span className={styles.state} data-state={key}>{(value || 'UNKNOWN').replaceAll('_', ' ')}</span>;
}

function Metric({ label, value, detail, tone = 'neutral' }) {
  return <article className={styles.metric} data-tone={tone}><div className={styles.metricLabel}>{label}</div><div className={styles.metricValue}>{value}</div><div className={styles.metricDetail}>{detail}</div></article>;
}

export const metadata = {
  title: 'VILLAWAY Command Center',
  description: 'Read-only operational command center for VILLAWAY-001.'
};

export default function VillawayDashboard() {
  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <div className={styles.brandLine}><span className={styles.brandMark}>V</span><span>VILLAWAY <span className={styles.muted}>/ COMMAND CENTER</span></span></div>
          <h1>Mission control</h1>
          <p className={styles.subtitle}>One attributable, completed, paid hospitality transaction.</p>
        </div>
        <div className={styles.headerMeta}>
          <span className={styles.preview}>READ-ONLY PREVIEW</span>
          <span className={styles.metaText}>VILLAWAY-001 · Isolated branch</span>
        </div>
      </header>

      <section className={styles.notice} aria-label="Data status">
        <span className={styles.noticeDot} />
        <div><strong>Partial source coverage.</strong> Engineering metadata is partially known. Commercial records are not connected. Unknown is not zero; no live booking or revenue claims are made here.</div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}><div><p className={styles.kicker}>01 / EXECUTIVE VIEW</p><h2>Current operating position</h2></div><span className={styles.asOf}>Snapshot · branch evidence</span></div>
        <div className={styles.metrics}>
          <Metric label="Current phase" value="Foundation" detail="Specification → isolated interface" />
          <Metric label="Next gate" value="Review" detail="Approve spec and data contract" tone="blue" />
          <Metric label="Critical blockers" value="3" detail="Source connection, runtime QA, access controls" tone="amber" />
          <Metric label="Paid transactions" value="Unknown" detail="Commercial source not connected" tone="neutral" />
        </div>
      </section>

      <div className={styles.columns}>
        <section className={styles.panel}>
          <div className={styles.sectionHead}><div><p className={styles.kicker}>02 / DELIVERY ROADMAP</p><h2>Gate progression</h2></div></div>
          <div className={styles.gates}>
            {gates.map((gate, index) => <article className={styles.gate} key={gate.id}>
              <div className={styles.gateRail}><span className={styles.gateNode}>{String(index + 1).padStart(2, '0')}</span>{index < gates.length - 1 && <span className={styles.gateLine} />}</div>
              <div className={styles.gateBody}><div className={styles.gateTop}><div><span className={styles.lane}>{gate.lane}</span><h3>{gate.title}</h3></div><State value={gate.state} /></div><p>{gate.note}</p></div>
            </article>)}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.sectionHead}><div><p className={styles.kicker}>03 / ENGINEERING</p><h2>Repository evidence</h2></div><State value="PARTIAL" /></div>
          <dl className={styles.facts}>
            <div><dt>Repository</dt><dd>AfricaEmperor/alagbara-intelligence</dd></div>
            <div><dt>Work branch</dt><dd><code>feat/villaway-001-acquisition-intelligence</code></dd></div>
            <div><dt>Dashboard commit</dt><dd><code>f3560e1</code> · dashboard styling</dd></div>
            <div><dt>Base branch</dt><dd><code>feat/museops-pi-001-partner-intelligence</code></dd></div>
            <div><dt>CI / tests</dt><dd><State value="UNKNOWN" /> <span className={styles.inlineNote}>No run evidence attached</span></dd></div>
          </dl>
          <div className={styles.sourceFoot}>Source: GitHub branch and committed files. Live issue, PR and workflow synchronization is not yet wired.</div>
        </section>
      </div>

      <section className={styles.section}>
        <div className={styles.sectionHead}><div><p className={styles.kicker}>04 / COMMERCIAL PIPELINE</p><h2>Transaction proof</h2></div><State value="NOT_CONNECTED" /></div>
        <div className={styles.pipeline}>
          {['Prospect', 'Requirement', 'Qualification', 'Property match', 'Introduction', 'Booking', 'Commission', 'Reconciliation'].map((stage, i) => <div className={styles.stage} key={stage}><span className={styles.stageNo}>{String(i + 1).padStart(2, '0')}</span><span>{stage}</span><span className={styles.stageUnknown}>—</span></div>)}
        </div>
        <p className={styles.emptyNote}>No live commercial records are connected. Counts and financial values are intentionally withheld rather than shown as zero.</p>
      </section>

      <div className={styles.columns}>
        <section className={styles.panel}>
          <div className={styles.sectionHead}><div><p className={styles.kicker}>05 / BLOCKERS</p><h2>What prevents the next gate?</h2></div></div>
          <div className={styles.blockers}>{blockers.map((item) => <article className={styles.blocker} key={item.title}><div className={styles.blockerTop}><span className={styles.severity}>{item.severity}</span><State value={item.state} /></div><h3>{item.title}</h3><p>{item.detail}</p></article>)}</div>
        </section>
        <section className={styles.panel}>
          <div className={styles.sectionHead}><div><p className={styles.kicker}>06 / GOVERNANCE</p><h2>Release controls</h2></div></div>
          <div className={styles.controlList}>
            <div><span>Read-only dashboard</span><State value="IN_PROGRESS" /></div>
            <div><span>Tenant isolation</span><State value="NOT_VERIFIED" /></div>
            <div><span>Server-side authorization</span><State value="NOT_VERIFIED" /></div>
            <div><span>Production data access</span><State value="BLOCKED" /></div>
            <div><span>Production deployment</span><State value="NOT_STARTED" /></div>
          </div>
          <p className={styles.sourceFoot}>No production database, external action or write capability is enabled by this preview.</p>
        </section>
      </div>

      <footer className={styles.footer}><span>ALAGBARA · VILLAWAY-001</span><span>Operational claims require source evidence.</span></footer>
    </main>
  );
}
