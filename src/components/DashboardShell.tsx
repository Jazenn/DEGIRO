import { useState } from 'react';
import { BarChart3, Coins, Home, Plus, Receipt } from 'lucide-react';
import './DashboardShell.css';

const destinations = [
  { name: 'Overview', icon: Home, heading: 'Your money, clearly explained.' },
  { name: 'Performance', icon: BarChart3, heading: 'What changed over time?' },
  { name: 'Costs', icon: Receipt, heading: 'Understand recorded costs.' },
  { name: 'Contributions', icon: Plus, heading: 'Choose your next contribution.' },
  { name: 'Crypto Scale', icon: Coins, heading: 'Keep your core. Review your stages.' },
] as const;
type Destination = typeof destinations[number]['name'];

/** Isolated visual shell: no portfolio reads, storage, calculations or mutations. */
export function DashboardShell() {
  const [destination, setDestination] = useState<Destination>('Overview');
  const current = destinations.find(item => item.name === destination)!;
  return <div className="dashboard-shell">
    <header className="shell-header">
      <a className="shell-brand" href="/dashboard-preview">portfolio<span>.</span></a>
      <a href="/">Open current dashboard</a>
    </header>
    <div className="shell-demo" role="note">Synthetic demonstration · fictional amounts only. No live prices, saved plans or Transactions.</div>
    <main id="shell-content">
      <p className="shell-eyebrow">Your portfolio / {destination}</p>
      <h1>{current.heading}</h1>
      {(destination === 'Overview' || destination === 'Performance') && <>
        <section className="shell-summary" aria-label="Illustrative portfolio summary">
          <article><span>Current portfolio value</span><strong>€1,100</strong><small>Fictional holdings · cash €0</small></article>
          <article><span>All-time net investment gain</span><strong className="shell-positive">+€95</strong><small>€1,100 value less €1,005 contributed</small></article>
          <article><span>Net external contributions</span><strong>€1,005</strong><small>Includes the €5 purchase fee</small></article>
        </section>
        <div className="shell-columns">
          <section className="shell-panel"><p className="shell-eyebrow">Portfolio History</p><h2>Separate growth from new money.</h2><p>Selected period: all time · illustrative purchase-to-valuation example.</p><div className="shell-bridge"><span>Opening value <b>€0</b></span><span>External contribution <b>+€1,005</b></span><span>Net investment gain <b>+€95</b></span><span>Closing value <b>€1,100</b></span></div><p className="shell-note">This is a worked example, not observed daily history. Percentage return and finalized UTC cutoff are unavailable in this demonstration.</p></section>
          <section className="shell-panel shell-accent"><p className="shell-eyebrow">Your next step</p><h2>Make room for your next contribution.</h2><p>Review your budget and allocation before making a purchase yourself.</p><button onClick={() => setDestination('Contributions')}>Explore contributions ?</button></section>
        </div>
        <section className="shell-panel"><h2>Current holdings</h2><div className="shell-holding"><span><b>Example global ETF</b><small>Fictional Asset · quantity 10 · price €110</small></span><strong>€1,100</strong></div><p className="shell-note">Current holdings are separate from selected-period results. No source observation timestamp is available for synthetic prices.</p></section>
      </>}
      {destination === 'Costs' && <section className="shell-panel"><p className="shell-eyebrow">All-time example</p><h2>€5 recorded purchase costs</h2><p>€1,000 purchase + €5 fee = €1,005 paid. A market value of €1,100 leaves €95 net gain.</p><p>The fee is included once in purchase cost. Future selling costs do not reduce current market value.</p><p className="shell-note">Synthetic history only. Actual recorded charges, dates and coverage will come from the accepted Snapshot; this example is not a broker tariff.</p></section>}
      {destination === 'Contributions' && <section className="shell-panel"><p className="shell-eyebrow">Budget before purchases</p><h2>Plan a contribution with confidence.</h2><p>Choose ETFs, crypto or a mix. Review estimated fees, unspent cash and the effect on your allocation.</p><p className="shell-note">Planning is not connected yet. Verified prices, quantity rules and your saved Rebalancing Targets are required before purchase suggestions can appear.</p><button onClick={() => setDestination('Crypto Scale')}>Explore Crypto Scale ?</button></section>}
      {destination === 'Crypto Scale' && <section className="shell-panel"><p className="shell-eyebrow">Your decision, never automatic execution</p><h2>Choose what stays invested.</h2><p>Your Long-Term Crypto Core stays separate from the Tactical Crypto Portion. Suggested Crypto Levels become an Accepted Crypto Plan only after your explicit review.</p><p>A reached Crypto Stage is a prompt to review, not a completed Transaction.</p><p className="shell-note">No core split, stage quantities or plan defaults have been selected. Complete price history and fresh reference quotes are required for actionable suggestions.</p></section>}
    </main>
    <nav className="shell-nav" aria-label="Dashboard destinations">{destinations.map(({ name, icon: Icon }) => <button key={name} aria-current={destination === name ? 'page' : undefined} onClick={() => setDestination(name)}><Icon size={20} aria-hidden="true" /><span>{name}</span></button>)}</nav>
  </div>;
}
