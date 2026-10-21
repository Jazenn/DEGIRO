// Throwaway: three structurally different dashboard layouts on /?prototype=1&variant=A.
// Fictional fixtures only. No API calls, credentials, storage or financial mutations.
import { useEffect, useState } from 'react';
import { ArrowDownLeft, ArrowRight, ArrowUpRight, BarChart3, Check, ChevronLeft, ChevronRight, CircleHelp, Coins, LayoutDashboard, PieChart, Plus, RefreshCw, ShieldCheck, Wallet, X } from 'lucide-react';
import './PrototypeDashboard.css';

type Tab = 'overview' | 'performance' | 'contribute' | 'crypto' | 'exposure';
type Variant = 'A' | 'B' | 'C';
type Scenario = 'normal' | 'fees' | 'sold' | 'stale' | 'missing' | 'gap' | 'partial';
type Period = 'ALL' | 'YTD' | '1Y' | '3M' | '1M' | '1W';
type Asset = { symbol: string; name: string; value: number; cost: number; buyFee: number; price: number; target: number; color: string; crypto?: boolean };
const eur = (n: number, digits = 0) => new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR', maximumFractionDigits: digits }).format(n);
const pct = (n: number) => `${n.toFixed(1).replace('.', ',')}%`;
const signed = (n: number) => `${n >= 0 ? '+' : '−'}${eur(Math.abs(n))}`;
const baseAssets: Asset[] = [
  { symbol: 'VWCE', name: 'Wereldwijd', value: 24000, cost: 21000, buyFee: 40, price: 125, target: 55, color: '#b4e6a2' },
  { symbol: 'EXUS', name: 'Wereld ex-VS', value: 9000, cost: 8000, buyFee: 15, price: 60, target: 20, color: '#a5c6ed' },
  { symbol: 'IMAE', name: 'Europa', value: 4500, cost: 4100, buyFee: 10, price: 75, target: 10, color: '#c9b4e7' },
  { symbol: 'ASWC', name: 'Defensie', value: 3000, cost: 2600, buyFee: 5, price: 15, target: 5, color: '#edbd91' },
  { symbol: 'BTC', name: 'Bitcoin', value: 6000, cost: 4400, buyFee: 8, price: 90000, target: 7, color: '#e5c278', crypto: true },
  { symbol: 'ETH', name: 'Ethereum', value: 1800, cost: 1440, buyFee: 2, price: 3000, target: 3, color: '#aea9ec', crypto: true },
];
const periods: Record<Period, { label: string; gain: number; flow: number; realized: number; held: number; income: number; other: number; fees: number }> = {
  ALL: { label: 'Sinds de start', gain: 8250, flow: 40500, realized: 1610, held: 6680, income: 160, other: 200, fees: 320 },
  YTD: { label: 'Dit jaar', gain: 4250, flow: 2500, realized: 1010, held: 3300, income: 100, other: 160, fees: 200 },
  '1Y': { label: '1 jaar', gain: 5750, flow: 3000, realized: 1460, held: 4450, income: 120, other: 280, fees: 320 },
  '3M': { label: '3 maanden', gain: 1750, flow: 1500, realized: 450, held: 1370, income: 30, other: 100, fees: 125 },
  '1M': { label: '1 maand', gain: 740, flow: 500, realized: 280, held: 500, income: 10, other: 50, fees: 65 },
  '1W': { label: '1 week', gain: 550, flow: 0, realized: 0, held: 560, income: 0, other: 10, fees: 10 },
};
const tabs: { id: Tab; label: string; icon: typeof Wallet }[] = [
  { id: 'overview', label: 'Overzicht', icon: LayoutDashboard }, { id: 'performance', label: 'Resultaat', icon: BarChart3 },
  { id: 'contribute', label: 'Inleggen', icon: Plus }, { id: 'crypto', label: 'Crypto', icon: Coins }, { id: 'exposure', label: 'Verdeling', icon: PieChart },
];
const names: Record<Variant, string> = { A: 'Rustig overzicht', B: 'Actie eerst', C: 'Werkruimte' };
const scenarioNames: Record<Scenario, string> = { normal: 'Gewoon overzicht', fees: 'Historische aankoopkosten', sold: 'Bitcoinwinst naar ETF', stale: 'Prijzen verouderd', missing: 'Historie ontbreekt', gap: 'Meerdere verkoopniveaus geraakt', partial: 'Gedeeltelijk verkocht' };
function quantile(values: number[], p: number) {
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * p;
  const lo = Math.floor(index);
  return sorted[lo] + (sorted[Math.ceil(index)] - sorted[lo]) * (index - lo);
}
function fictionalPrices(coin: string) {
  const scale = coin === 'BTC' ? 1 : 1 / 30;
  return Array.from({ length: 365 }, (_, d) => (62000 + d * 90 + Math.sin(d / 28) * 10500 + Math.cos(d / 7) * 2100) * scale);
}

export function PrototypeDashboard() {
  const raw = new URLSearchParams(location.search).get('variant');
  const [variant, setVariant] = useState<Variant>(raw === 'B' || raw === 'C' ? raw : 'A');
  const [tab, setTab] = useState<Tab>('overview');
  const [period, setPeriod] = useState<Period>('ALL');
  const [scenario, setScenario] = useState<Scenario>('normal');
  const [budget, setBudget] = useState(1000);
  const [cryptoShare, setCryptoShare] = useState(0);
  const [coin, setCoin] = useState('BTC');
  const [core, setCore] = useState({ BTC: 50, ETH: 50 });
  const [plans, setPlans] = useState<Record<string, { coin: string; core: number; prices: number[]; originalQty: number }>>({});
  const [reported, setReported] = useState<Record<string, number[]>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const [details, setDetails] = useState(false);
  const [toast, setToast] = useState('');
  const [chartMode, setChartMode] = useState<'gain' | 'value'>('gain');
  const shortExample = scenario === 'fees' || scenario === 'sold';
  const assets = shortExample ? scenario === 'fees'
    ? [{ ...baseAssets[0], value: 1100, cost: 1000, buyFee: 5, target: 100 }]
    : [{ ...baseAssets[0], value: 750, cost: 750, buyFee: 0, target: 55 }, { ...baseAssets[4], value: 600, cost: 500, buyFee: 0 }]
    : baseAssets.map(a => {
      if (scenario !== 'gap' || !a.crypto) return a;
      const price = quantile(fictionalPrices(a.symbol), .95) * 1.05;
      return { ...a, price, value: a.value / a.price * price };
    });
  const cash = shortExample ? 0 : 450;
  const total = assets.reduce((sum, a) => sum + a.value, cash);
  const chosen = periods[period];
  const data = scenario === 'fees'
    ? { ...periods.ALL, gain: 95, flow: 1005, held: 95, realized: 0, income: 0, other: 0, fees: 5, label: 'Sinds aankoop' }
    : scenario === 'sold'
      ? { ...periods.ALL, gain: 350, flow: 1000, held: 100, realized: 250, income: 0, other: 0, fees: 0, label: 'Sinds aankoop' }
      : { ...chosen, gain: chosen.gain + total - 48750, held: chosen.held + total - 48750 };
  const missing = scenario === 'missing';
  const stale = scenario === 'stale';
  const changeVariant = (next: Variant) => {
    const url = new URL(location.href); url.searchParams.set('variant', next); history.replaceState({}, '', url);
    setVariant(next);
  };
  const cycle = (direction: number) => changeVariant((['A', 'B', 'C'] as Variant[])[(['A', 'B', 'C'].indexOf(variant) + direction + 3) % 3]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('input,textarea,select,[contenteditable]')) return;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); cycle(e.key === 'ArrowRight' ? 1 : -1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(''), 4000); return () => clearTimeout(t); } }, [toast]);
  useEffect(() => { document.title = `Prototype ${variant} · Portefeuille`; }, [variant]);
  const notify = (text: string) => setToast(text);
  const refresh = () => { setRefreshing(true); setTimeout(() => { setRefreshing(false); setRefreshed(true); notify(stale ? 'Voorbeeld: ophalen mislukt. Vorige cijfers blijven staan.' : 'Voorbeeld: volledige prijsbatch bijgewerkt. Geen netwerkverzoek gedaan.'); }, 750); };
  const heading = tabs.find(t => t.id === tab)!.label;

  function Status() {
    return <div className={`pf-status ${stale ? 'pf-warning' : ''}`}><span className="pf-dot" />{refreshing ? 'Prijzen ophalen…' : stale ? 'Prijzen van gisteren · vernieuwen mislukt' : refreshed ? 'Voorbeeld: zojuist vernieuwd' : 'Voorbeeldprijzen · 14:32'}<button onClick={refresh} aria-label="Prijzen vernieuwen" title="Simuleer snelle prijsverversing"><RefreshCw size={14} className={refreshing ? 'pf-spin' : ''} /></button></div>;
  }
  function Navigation({ rail = false }: { rail?: boolean }) {
    return <nav className={rail ? 'pf-rail-nav' : 'pf-nav'} aria-label="Dashboard">{tabs.map(t => <button key={t.id} className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}><t.icon size={18} /><span>{t.label}</span>{rail && <ChevronRight size={14} />}</button>)}</nav>;
  }
  function Periods() {
    return <div className="pf-periods" aria-label="Periode">{(['1W', '1M', '3M', '1Y', 'YTD', 'ALL'] as Period[]).map(p => <button key={p} disabled={shortExample && p !== 'ALL'} aria-pressed={(shortExample ? 'ALL' : period) === p} onClick={() => setPeriod(p)}>{p === 'ALL' ? 'Alles' : p === 'YTD' ? 'Dit jaar' : p}</button>)}</div>;
  }
  function Summary({ compact = false }: { compact?: boolean }) {
    return <div className={`pf-summary ${compact ? 'compact' : ''}`}>
      <div className="pf-value"><span className="pf-eyebrow">Portefeuillewaarde</span><strong>{eur(total)}</strong><small>Inclusief {eur(cash)} beschikbaar saldo</small></div>
      <div className="pf-gain"><span className="pf-eyebrow">Totale winst · {data.label.toLowerCase()}</span><strong className="pf-positive">{missing ? 'Niet beschikbaar' : signed(data.gain)}</strong><small>{missing ? 'Prijshistorie nodig voor dit resultaat' : <>{pct(data.gain / (total - data.gain) * 100)} voorbeeldrendement · na kosten<br /><button className="pf-text-link" onClick={() => setDetails(true)}>Hoe is dit opgebouwd?</button></>}</small></div>
      <div className="pf-contribution"><span className="pf-eyebrow">Bijgestort · deze periode</span><strong>{eur(data.flow)}</strong><small>Je eigen geld, geen winst</small></div>
    </div>;
  }
  function Breakdown({ full = false }: { full?: boolean }) {
    const rows = [{ label: 'Winst op wat je nog bezit', value: data.held }, { label: 'Winst uit eerdere verkopen', value: data.realized }, { label: 'Dividend & inkomsten', value: data.income }, { label: 'Overige rekeningkosten', value: -data.other }];
    return <section className="pf-panel pf-breakdown"><div className="pf-section-head"><div><span className="pf-eyebrow">Waar komt je winst vandaan?</span><h2>Het hele resultaat telt mee.</h2></div><button className="pf-icon-button" aria-label="Uitleg winst" onClick={() => setDetails(true)}><CircleHelp size={18} /></button></div>
      {rows.map((r, i) => <div className="pf-result-row" key={r.label}><span><i className={`pf-result-marker marker-${i}`} />{r.label}</span><b className={r.value < 0 ? 'pf-negative' : ''}>{missing ? '—' : signed(r.value)}</b></div>)}
      <div className="pf-result-row pf-result-total"><span>Totale winst na kosten</span><b className="pf-positive">{missing ? '—' : signed(data.gain)}</b></div>
      <p className="pf-note">Aankoop- en verkoopkosten zitten al in de Asset-resultaten. De {eur(data.fees)} totale kosten worden hier niet nogmaals afgetrokken.</p>
      {full && <div className="pf-info"><ShieldCheck size={18} /><span>Een verkoop en herbelegging wissen je eerdere winst niet. Een storting telt apart als inleg.</span></div>}
    </section>;
  }
  function Chart({ small = false }: { small?: boolean }) {
    const gains = Array.from({ length: 30 }, (_, i) => Math.max(-data.gain * .08, data.gain * (i / 29 + Math.sin(i * .65) * .075 - Math.sin(29 * .65) * .075 * i / 29)) - (scenario === 'fees' ? 5 * (1 - i / 29) : 0));
    const fundedStart = total - data.gain;
    const values = chartMode === 'gain' ? gains : gains.map(g => fundedStart + g);
    const range = Math.max(Math.max(...values) - Math.min(...values), Math.abs(total) * .01, 1);
    const max = Math.max(...values) + range * .08;
    const min = (chartMode === 'gain' ? Math.min(0, ...values) : Math.min(fundedStart, ...values)) - range * .04;
    const xy = values.map((v, i) => `${i / 29 * 660},${165 - (v - min) / (max - min) * 145}`).join(' ');
    const baselineY = 165 - ((chartMode === 'gain' ? 0 : fundedStart) - min) / (max - min) * 145;
    return <section className={`pf-panel pf-chart ${small ? 'small' : ''}`}><div className="pf-section-head"><div><span className="pf-eyebrow">{data.label} · fictief verloop</span><h2>{chartMode === 'gain' ? 'Wat hebben je beleggingen opgeleverd?' : 'Waarde en inlegbasis'}</h2></div><div className="pf-segment"><button aria-pressed={chartMode === 'gain'} onClick={() => setChartMode('gain')}>Winst</button><button aria-pressed={chartMode === 'value'} onClick={() => setChartMode('value')}>Waarde</button></div></div>
      {missing ? <div className="pf-empty"><BarChart3 size={28} /><b>Nog geen betrouwbare prijshistorie</b><p>Je huidige bezit blijft zichtbaar. We vullen de grafiek niet aan met verzonnen prijzen.</p></div> : <>
        <div className="pf-chart-caption"><strong className="pf-positive">{chartMode === 'gain' ? signed(data.gain) : eur(total)}</strong><span>{chartMode === 'gain' ? 'Investeringsresultaat, zonder stortingen' : `${eur(data.flow)} bijgestort in deze periode`}</span></div>
        <div className="pf-plot"><div className="pf-y-labels"><span>{eur(max)}</span><span>{eur((max + min) / 2)}</span><span>{eur(min)}</span></div><svg viewBox="0 0 660 190" preserveAspectRatio="none" role="img" aria-label={`Illustratieve grafiek met ${eur(data.gain)} winst`}><defs><linearGradient id={`fill-${variant}-${small}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity=".17" /><stop offset="100%" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>{[20, 90, 165].map(y => <line key={y} x1="0" x2="660" y1={y} y2={y} className="pf-gridline" />)}<polygon points={`0,190 ${xy} 660,190`} fill={`url(#fill-${variant}-${small})`} /><polyline points={xy} fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />{chartMode === 'value' && <line x1="0" x2="660" y1={baselineY} y2={baselineY} stroke="var(--muted)" strokeDasharray="5 6" />}</svg></div>
        <div className="pf-x-labels"><span>Begin periode</span><span>Halverwege</span><span>Nu</span></div>
        {chartMode === 'value' && <p className="pf-note">Stippellijn: startwaarde plus nieuwe inleg. In deze fictieve rekenvoorbeelden is alle nieuwe inleg aan het begin van de periode toegevoegd.</p>}
      </>}
    </section>;
  }
  function Holdings() {
    return <section className="pf-panel pf-holdings"><div className="pf-section-head"><div><span className="pf-eyebrow">Wat je nu bezit</span><h2>Je Assets</h2></div><span className="pf-counter">{assets.length}</span></div><div className="pf-holding-table"><div className="pf-table-labels"><span>Asset</span><span>Waarde</span><span>Winst op bezit¹</span><span>Aandeel</span></div>{assets.map(a => <div className="pf-holding-row" key={a.symbol}><div className="pf-asset-name"><span className="pf-asset-icon" style={{ background: `${a.color}22`, color: a.color }}>{a.symbol === 'BTC' ? '₿' : a.symbol === 'ETH' ? 'Ξ' : a.symbol.slice(0, 2)}</span><span><b>{a.symbol}</b><small>{a.name}</small></span></div><b>{eur(a.value)}</b><span className="pf-positive">{signed(a.value - a.cost - a.buyFee)}</span><span className="pf-allocation-cell"><i style={{ width: `${a.value / total * 100}%`, background: a.color }} />{pct(a.value / total * 100)}</span></div>)}</div><p className="pf-note">¹ Na historische aankoopkosten. Winst uit verkochte delen staat apart bij Resultaat. Waarden zijn fictief.</p></section>;
  }
  function Contribution({ teaser = false }: { teaser?: boolean }) {
    const safeBudget = Math.max(0, Math.min(100000, Number(budget) || 0));
    const cryptoBudget = safeBudget * cryptoShare / 100;
    let remaining = safeBudget - cryptoBudget;
    const etfs = baseAssets.filter(a => !a.crypto);
    const quantities: Record<string, number> = Object.fromEntries(etfs.map(a => [a.symbol, 0]));
    for (let i = 0; i < 10000; i++) {
      const options = etfs.filter(a => remaining >= a.price + (quantities[a.symbol] ? 0 : 2)).map(a => ({ a, gap: (total + safeBudget) * a.target / 100 - (assets.find(x => x.symbol === a.symbol)?.value || 0) - quantities[a.symbol] * a.price })).filter(x => x.gap > 0).sort((a, b) => b.gap - a.gap);
      if (!options.length) break;
      const a = options[0].a; remaining -= a.price + (quantities[a.symbol] ? 0 : 2); quantities[a.symbol]++;
    }
    const etfFees = Object.values(quantities).filter(Boolean).length * 2;
    const cryptoFee = cryptoBudget > 5 ? 5 : 0;
    const cryptoNet = cryptoBudget > 5 ? cryptoBudget - cryptoFee : 0;
    if (cryptoBudget <= 5) remaining += cryptoBudget;
    const existingCrypto = assets.filter(a => a.crypto).reduce((s, a) => s + a.value, 0);
    const afterTotal = total + safeBudget - etfFees - cryptoFee;
    const cryptoPct = (existingCrypto + cryptoNet) / Math.max(afterTotal, 1) * 100;
    return <section className={`pf-panel pf-planner ${teaser ? 'teaser' : ''}`}><div className="pf-section-head"><div><span className="pf-eyebrow">Je volgende stap</span><h2>Geef je nieuwe inleg een plek.</h2></div><ArrowUpRight size={22} /></div><label className="pf-money-input"><span>Nieuwe inleg</span><div><b>€</b><input aria-label="Nieuwe inleg" type="number" min="0" max="100000" step="50" value={budget} onChange={e => setBudget(Number(e.target.value))} /></div></label>
      {teaser ? <><p>Bekijk welke aankopen je dichter bij je eigen verdeling brengen, of kies bewust voor meer crypto.</p><button className="pf-primary" onClick={() => setTab('contribute')}>Verdeel mijn inleg <ArrowRight size={17} /></button></> : <><div className="pf-choice-row">{[{ p: 0, label: 'Naar ETFs' }, { p: 25, label: 'Zelf verdelen' }, { p: 100, label: 'Naar crypto' }].map(c => <button key={c.p} aria-pressed={c.p === 25 ? cryptoShare > 0 && cryptoShare < 100 : cryptoShare === c.p} onClick={() => setCryptoShare(c.p)}>{c.label}</button>)}</div><label className="pf-range-label"><span>Crypto: {pct(cryptoShare)}</span><span>ETFs: {pct(100 - cryptoShare)}</span><input aria-label="Aandeel nieuwe inleg naar crypto" type="range" min="0" max="100" value={cryptoShare} onChange={e => setCryptoShare(Number(e.target.value))} /></label>
        <div className="pf-purchase-list">{etfs.filter(a => quantities[a.symbol]).map(a => <div className="pf-result-row" key={a.symbol}><span><b>{a.symbol}</b><small>{quantities[a.symbol]} hele stukken · {eur(2)} voorbeeldkosten</small></span><b>{eur(quantities[a.symbol] * a.price)}</b></div>)}{cryptoNet > 0 && <div className="pf-result-row"><span><b>Bitcoin</b><small>Nieuwe bijdrage · {eur(cryptoFee)} voorbeeldkosten</small></span><b>{eur(cryptoNet)}</b></div>}{safeBudget === 0 && <p className="pf-note">Vul een bedrag in om een verdeling te bekijken.</p>}</div>
        <div className="pf-impact"><div><span>Crypto-aandeel</span><b>{pct(existingCrypto / total * 100)} <ArrowRight size={14} /> {pct(cryptoPct)}</b></div><div><span>Voorbeeldkosten</span><b>{eur(etfFees + cryptoFee)}</b></div><div><span>Over na afronding</span><b>{eur(remaining, 2)}</b></div></div><p className="pf-note">Je bepaalt zelf wat je koopt. Kosten zijn fictieve rekenbedragen, geen DEGIRO-tarieven. Er wordt niets uitgevoerd.</p><button className="pf-primary" onClick={() => notify('Voorbeeldverdeling bekeken. Geen aankoop uitgevoerd of opgeslagen.')}>Deze verdeling bekijken <ArrowRight size={17} /></button></>}
    </section>;
  }
  function Crypto({ teaser = false }: { teaser?: boolean }) {
    const coinAsset = assets.find(a => a.symbol === coin) ?? { ...baseAssets.find(a => a.symbol === coin)!, value: 0, cost: 0, buyFee: 0 };
    const source = fictionalPrices(coin);
    const buyLevels = [.35, .2, .1].map(p => quantile(source, p));
    const sellLevels = [.75, .9, .95].map(p => quantile(source, p));
    const quote = coinAsset.price;
    const key = coin as 'BTC' | 'ETH';
    const active = plans[coin];
    const coinReports = reported[coin] ?? [];
    const originalQty = active?.originalQty ?? (coinAsset.value / coinAsset.price * (1 - core[key] / 100));
    const stageQty = originalQty * .25;
    const levels = active?.prices ?? sellLevels;
    const oldPlan = scenario === 'stale' && coin === 'BTC';
    const historyRank = source.filter(p => p <= quote).length / source.length * 100;
    return <section className={`pf-panel pf-crypto ${teaser ? 'teaser' : ''}`}><div className="pf-section-head"><div><span className="pf-eyebrow">Crypto · met een plan</span><h2>{teaser ? 'Neem winst. Houd perspectief.' : 'Een deel houden. Een deel benutten.'}</h2></div><span className="pf-coin-mark">₿</span></div>
      {teaser ? <><p>Behoud je langetermijndeel. Laat verkoopopbrengsten doorstromen naar ETFs en gebruik nieuwe inleg voor eventuele aankopen.</p><div className="pf-mini-context"><span>Bitcoin</span><b>{eur(baseAssets[4].price)}</b><span className="pf-tag">Voorbeeldkoers</span></div><button className="pf-secondary" onClick={() => setTab('crypto')}>Bekijk mijn cryptoplan <ArrowRight size={17} /></button></> : <><div className="pf-coin-tabs">{['BTC', 'ETH'].map(c => <button key={c} aria-pressed={coin === c} onClick={() => setCoin(c)}>{c === 'BTC' ? '₿ Bitcoin' : 'Ξ Ethereum'}</button>)}</div><div className="pf-crypto-quote"><strong>{eur(quote)}</strong><span>Fictieve referentieprijs · geen uitvoeringsprijs</span></div>
        <div className="pf-context-grid"><div><span>Plek in afgelopen jaar</span><b>{pct(historyRank)} van de dagen lager</b></div><div><span>Onder recente piek</span><b>{pct(Math.max(0, (Math.max(...source) - quote) / Math.max(...source) * 100))}</b></div><div><span>Huidige winst op bezit</span><b>{signed(coinAsset.value - coinAsset.cost - coinAsset.buyFee)}</b></div></div>
        <div className="pf-context-line"><span>Lager in de verdeling</span><span>Hoger in de verdeling</span><div><i style={{ left: `${Math.min(97, historyRank)}%` }} /></div></div>
        <p className="pf-note">Laatste 3 maanden in dit voorbeeld: {eur(Math.min(...source.slice(-90)))} tot {eur(Math.max(...source.slice(-90)))}. Dat is recente context, geen voorspelling.</p>
        <p className="pf-note">365 fictieve dagprijzen. Koopzones: percentiel 35/20/10; verkoopzones: 75/90/95. Dit zijn voorstelwaarden om te bespreken, geen bewezen signalen of definitieve instellingen.</p>
        <label className="pf-range-label"><span>Langetermijndeel: {pct(core[key])}</span><span>Beschikbaar voor stages: {pct(100 - core[key])}</span><input aria-label="Langetermijndeel" type="range" min="10" max="100" step="5" value={core[key]} onChange={e => setCore({ ...core, [key]: Number(e.target.value) })} /></label>
        <div className="pf-info"><ShieldCheck size={18} /><span>{active ? <>Actief plan: {pct(active.core)} langetermijndeel. De schuif past alleen je voorstel aan; je actieve stages blijven gelijk.</> : <>Voorbeeldinstelling: {pct(core[key])} behouden. Kies zelf je percentage voordat je een echt plan gebruikt.</>}</span></div>
        {missing ? <><div className="pf-empty"><b>Geen prijszones zonder historie</b><p>Er komen geen nieuwe suggesties op basis van ontbrekende prijzen.</p></div>{active && <div><h3>Je bestaande plan blijft behouden</h3>{active.prices.map((price, i) => <div className="pf-result-row" key={i}><span>Stage {i + 1}</span><b>{eur(price)} · alleen bekijken</b></div>)}</div>}</> : <><div className="pf-section-head pf-stages-heading"><h3>{active ? 'Je geaccepteerde verkoopstages' : 'Voorgestelde verkoopstages'}</h3><span className="pf-tag">25% per stage · voorbeeld</span></div>
          {levels.map((price, i) => <div className="pf-stage" key={`${coin}-${i}`}><span className="pf-stage-index">{i + 1}</span><div><b>{eur(price)}</b><small>{(stageQty).toFixed(6)} {coin} · 25% van oorspronkelijk tactisch deel</small><small>{scenario === 'partial' && i === 0 ? 'Voorbeeld: 50% uitgevoerd; rest blijft open' : `Naar ETFs: circa ${eur(Math.max(0, stageQty * price - 5))} na €5 voorbeeldkosten`}</small></div><button disabled={!active || coinReports.includes(i) || stale} className={coinReports.includes(i) ? 'pf-done' : ''} onClick={() => { setReported({ ...reported, [coin]: [...coinReports, i] }); notify('Verkoop gemeld in dit voorbeeld. Koppel later aan een geïmporteerde Transactie.'); }}>{coinReports.includes(i) ? <><Check size={13} /> Gemeld</> : quote >= price ? 'Niveau geraakt' : 'Verkoop melden'}</button></div>)}
          {scenario === 'gap' && <p className="pf-warning pf-inline-message">De koers passeert meerdere stages. Bekijk ze samen; het dashboard voert geen verkoop uit.</p>}
          <p className="pf-note">Drie stages verkopen samen 75% van het oorspronkelijke tactische deel. De overige 25% blijft zonder verkoopstage. Een gemelde verkoop wacht op koppeling aan je Transactie; dezelfde stage wordt niet opnieuw voorgesteld.</p>
          <button disabled={stale || coinAsset.value === 0 || core[key] === 100} className="pf-primary" onClick={() => { setPlans({ ...plans, [coin]: { coin, core: core[key], prices: sellLevels, originalQty: coinAsset.value / coinAsset.price * (1 - core[key] / 100) } }); setReported({ ...reported, [coin]: [] }); notify('Voorbeeldplan geaccepteerd. Alleen in dit tabblad; niet opgeslagen.'); }}>{active ? 'Voorstel als nieuw plan accepteren' : 'Dit voorbeeldplan accepteren'} <Check size={17} /></button>
          {coinAsset.value === 0 && <p className="pf-note">Je bezit geen {coin} in deze voorbeeldsituatie. Je kunt wel de koopcontext bekijken.</p>}
          {stale && <p className="pf-warning pf-inline-message">Verouderde prijzen: eerst vernieuwen voordat je nieuwe niveaus accepteert.</p>}
          {oldPlan && <div className="pf-info"><CircleHelp size={18} /><span>Voorbeeld van een oud koopniveau: €50.000. Nieuwe historische context kan aanleiding geven om dat bewust te herzien; het wordt niet stilzwijgend vervangen.</span></div>}
          <div className="pf-buy-zones"><h3>Mogelijke koopzones</h3><div>{buyLevels.map((p, i) => <span key={i}>{eur(p)}</span>)}</div><p>Bekijken wanneer je nieuwe maandinleg toevoegt. Geld uit eerdere verkopen gaat standaard naar ETFs.</p><button className="pf-text-link" onClick={() => { setCryptoShare(25); setTab('contribute'); }}>Bekijk effect op mijn nieuwe inleg <ArrowRight size={14} /></button></div>
        </>}
      </>}
    </section>;
  }
  function Exposure() {
    const held = assets.reduce((sum, a) => sum + a.value, 0);
    return <section className="pf-panel"><div className="pf-section-head"><div><span className="pf-eyebrow">Je eigen verdeling</span><h2>Waar zit je geld?</h2></div><PieChart size={20} /></div><div className="pf-allocation-strip">{assets.map(a => <span key={a.symbol} style={{ width: `${a.value / held * 100}%`, background: a.color }} title={`${a.symbol}: ${pct(a.value / held * 100)}`} />)}</div>{assets.map(a => <div className="pf-result-row" key={a.symbol}><span><i className="pf-result-marker" style={{ background: a.color }} />{a.symbol}</span><span>{pct(a.value / held * 100)} <small>doel {pct(a.target)}</small></span></div>)}<div className="pf-info"><CircleHelp size={18} /><span>Deze verdeling gaat over belegd geld; {eur(cash)} cash staat apart. ETF-overlap, sectoren en landen zijn nog niet geladen. Aantal ETFs is geen maat voor spreiding.</span></div><button className="pf-secondary" onClick={() => setTab('contribute')}>Bekijk verdeling na nieuwe inleg <ArrowRight size={16} /></button></section>;
  }
  function Fees() {
    const inResults = scenario === 'fees' ? 5 : scenario === 'sold' ? 0 : data.fees - data.other;
    return <section className="pf-panel"><div className="pf-section-head"><div><span className="pf-eyebrow">Kosten · {data.label.toLowerCase()}</span><h2>{eur(data.fees)} in rekening gebracht</h2></div><Wallet size={20} /></div><div className="pf-result-row"><span>Verwerkt in aankoop-/verkoopresultaat</span><b>{eur(inResults)}</b></div><div className="pf-result-row"><span>Overige rekeningkosten</span><b>{eur(data.other)}</b></div><p className="pf-note">Alleen historische voorbeeldkosten. Deze bedragen zijn al één keer verwerkt in je totale winst. Fondskosten die al in de koers zitten, worden niet nogmaals afgetrokken.</p><div className="pf-info"><ShieldCheck size={18} /><span>{scenario === 'fees' ? '€1.000 aankoop + €5 kosten = €1.005 betaald. Bij €1.100 marktwaarde is je winst €95.' : 'Dekking in dit ontwerp: voorbeeldadministratie. In de echte app tonen we vanaf welke datum kosten beschikbaar zijn.'}</span></div></section>;
  }
  function Content() {
    if (tab === 'performance') return <><div className="pf-page-title"><div><span className="pf-eyebrow">Resultaat, niet alleen saldo</span><h1>Wat heeft je geld gedaan?</h1></div>{Periods()}</div>{Summary({ compact: true })}{Chart({})}<div className="pf-two-columns">{Breakdown({ full: true })}{Fees()}</div>{Holdings()}</>;
    if (tab === 'contribute') return <><div className="pf-page-title"><div><span className="pf-eyebrow">Maandelijkse keuze</span><h1>Wat doe je met je volgende inleg?</h1></div></div><div className="pf-two-columns">{Contribution({})}<div>{Exposure()}<div className="pf-info"><ArrowDownLeft size={20} /><span>Crypto verkopen? De netto-opbrengst gaat standaard naar je ETF-verdeling. Nieuwe cryptoaankopen komen uit nieuwe bijdragen.</span></div></div></div></>;
    if (tab === 'crypto') return <><div className="pf-page-title"><div><span className="pf-eyebrow">Je regels, jouw keuze</span><h1>Winst nemen zonder alles los te laten.</h1></div></div>{Crypto({})}</>;
    if (tab === 'exposure') return <><div className="pf-page-title"><div><span className="pf-eyebrow">Verdeling & kosten</span><h1>Begrijp wat je bezit.</h1></div>{Periods()}</div><div className="pf-two-columns">{Exposure()}{Fees()}</div>{Holdings()}</>;
    return <><div className="pf-page-title"><div><span className="pf-eyebrow">Jouw portefeuille, helder in beeld</span><h1>Je geld. Je overzicht.</h1></div>{Periods()}</div>{Summary({})}<div className="pf-overview-main">{Chart({})}{Contribution({ teaser: true })}</div><div className="pf-two-columns">{Breakdown({})}{Crypto({ teaser: true })}</div>{Holdings()}</>;
  }
  function Brand() { return <button className="pf-brand" onClick={() => setTab('overview')}><span className="pf-brand-mark">p</span>portefeuille<span className="pf-brand-period">.</span></button>; }
  const body = Content();
  return <div className={`pf pf-${variant}`}>
    {variant === 'A' && <><header className="pf-header">{Brand()}<div className="pf-header-right"><span className="pf-fixture-tag">Prototype · fictieve gegevens</span>{Status()}</div></header><div className="pf-top-nav">{Navigation({})}</div><main className="pf-main">{body}</main></>}
    {variant === 'B' && <><header className="pf-header">{Brand()}<span className="pf-fixture-tag">Prototype · fictieve gegevens</span>{Status()}</header><main className="pf-editorial-main">{tab === 'overview' ? <><div className="pf-editorial-title"><span className="pf-eyebrow">Een rustige blik. Een bewuste volgende stap.</span><h1>Laat je geld groeien.<br /><em>Houd zelf de regie.</em></h1><p>Je resultaat begrijpen en je volgende bijdrage kiezen, op één plek.</p></div><div className="pf-editorial-actions">{Contribution({ teaser: true })}{Crypto({ teaser: true })}</div><div className="pf-editorial-ledger"><div><span className="pf-eyebrow">De stand van zaken</span><h2>Wat staat er onder de streep?</h2></div>{Periods()}{Summary({ compact: true })}</div><div className="pf-two-columns">{Chart({ small: true })}{Breakdown({})}</div>{Holdings()}</> : body}</main>{Navigation({})}</>}
    {variant === 'C' && <><aside className="pf-sidebar">{Brand()}<span className="pf-fixture-tag">Prototype · fictieve gegevens</span>{Navigation({ rail: true })}<div className="pf-sidebar-assets"><span className="pf-eyebrow">Bezit in beeld</span>{assets.map(a => <button key={a.symbol} onClick={() => { setTab(a.crypto ? 'crypto' : 'exposure'); if (a.crypto) setCoin(a.symbol); }}><span style={{ color: a.color }}>●</span><b>{a.symbol}</b><span>{eur(a.value)}</span></button>)}</div><div className="pf-sidebar-footer"><ShieldCheck size={16} /> Je eigen beslissingen.<br />Geen automatische aankopen.</div></aside><div className="pf-workspace"><header className="pf-workspace-header"><span>Portefeuille <ChevronRight size={14} /> {heading}</span>{Status()}</header><main className="pf-main">{tab === 'overview' ? <><div className="pf-page-title"><div><span className="pf-eyebrow">De werkruimte</span><h1>Alles wat je beslissing nodig heeft.</h1></div>{Periods()}</div>{Summary({ compact: true })}<div className="pf-workspace-grid"><div>{Holdings()}{Chart({ small: true })}</div><div>{Contribution({ teaser: true })}{Breakdown({})}</div></div></> : body}</main></div></>}
    {toast && <div className="pf-toast" role="status"><Check size={17} />{toast}<button aria-label="Melding sluiten" onClick={() => setToast('')}><X size={14} /></button></div>}
    {details && <div className="pf-modal-backdrop" onClick={() => setDetails(false)}><section className="pf-explanation" role="dialog" aria-modal="true" aria-label="Hoe je winst is opgebouwd" onClick={e => e.stopPropagation()}><button className="pf-modal-close" onClick={() => setDetails(false)} aria-label="Uitleg sluiten"><X size={20} /></button><span className="pf-eyebrow">Een eenvoudig voorbeeld</span><h2>Een verkoop wist je winst niet.</h2><p>Je koopt voor €1.000 Bitcoin. Het wordt €1.500 waard. Je verkoopt de helft voor €750 en koopt daarvoor een ETF.</p><p>Die verkoop leverde €250 winst op. Je resterende Bitcoin is later €600 waard: nog €100 boven de aankoopprijs.</p><div className="pf-example-total"><span>€750 ETF + €600 Bitcoin</span><strong>€1.350</strong><span>Min je €1.000 inleg</span><b className="pf-positive">€350 totale winst</b></div><p>De verkoopwinst blijft meetellen. In dit voorbeeld zijn er geen kosten of inkomsten.</p><button className="pf-primary" onClick={() => { setScenario('sold'); setPeriod('ALL'); setTab('performance'); setDetails(false); }}>Bekijk dit voorbeeld in het dashboard <ArrowRight size={16} /></button></section></div>}
    {import.meta.env.DEV && <div className="pf-prototype-tools"><div className="pf-switcher"><button onClick={() => cycle(-1)} aria-label="Vorig ontwerp"><ChevronLeft size={19} /></button><button className="pf-current-variant" onClick={() => cycle(1)}><span>ONTWERP {variant}</span><b>{names[variant]}</b></button><button onClick={() => cycle(1)} aria-label="Volgend ontwerp"><ChevronRight size={19} /></button><span className="pf-tool-divider" /><label><span className="pf-sr-only">Voorbeeldsituatie</span><select aria-label="Voorbeeldsituatie" value={scenario} onChange={e => { setScenario(e.target.value as Scenario); setRefreshed(false); if (e.target.value === 'fees' || e.target.value === 'sold') setPeriod('ALL'); }}>{Object.entries(scenarioNames).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label><details className="pf-state"><summary>Staat</summary><pre>{JSON.stringify({ variant, tab, period: shortExample ? 'ALL' : period, scenario, budget, cryptoShare, coin, core, acceptedPlans: plans, reportedStages: reported, refreshing }, null, 2)}</pre></details></div><span className="pf-prototype-caption">Wegwerpprototype · geen echte prijzen, opslag of transacties · ← → wisselt ontwerp</span></div>}
  </div>;
}
