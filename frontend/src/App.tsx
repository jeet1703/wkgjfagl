import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { api, type Basis } from './api'
import { AccuracyView } from './components/AccuracyView'
import { DayAheadView } from './components/DayAheadView'
import { ErrorBox, Loading } from './components/Stat'
import { addDays, fmtDay } from './format'
import { useAsync } from './hooks'

type Tab = 'day' | 'accuracy'

const CUTOFF_PRESETS = [
  { value: '06:00', label: '06:00 · early desk' },
  { value: '09:00', label: '09:00 · before auctions' },
  { value: '11:00', label: '11:00 · last call' },
  { value: '15:00', label: '15:00 · afternoon' },
]

const BASES: { value: Basis; label: string; title: string }[] = [
  { value: 'metered', label: 'Delivered', title: 'Metered output – what you actually receive.' },
  { value: 'available', label: 'Available', title: 'Delivered + wind the grid paid to switch off – a fair test of forecast skill.' },
]

export default function App() {
  const meta = useAsync(() => api.meta(), [])
  const [tab, setTab] = useState<Tab>('day')
  const [date, setDate] = useState('2026-01-15')
  const [cutoff, setCutoff] = useState('09:00')
  const [basis, setBasis] = useState<Basis>('metered')
  const accuracy = useAsync(() => api.accuracy(cutoff, basis), [cutoff, basis])

  if (meta.error) return <div className="app"><ErrorBox message={meta.error} /></div>
  if (!meta.data) return <div className="app"><Loading /></div>
  const [first, last] = meta.data.delivery_window
  const clamp = (d: string) => (d < first ? first : d > last ? last : d)

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead__title">
          <h1>Windcast Desk</h1>
          <p>GB national wind, day-ahead purchasing pilot. Decisions made in January 2026.</p>
        </div>
        <nav className="nav" aria-label="Views">
          <button className={tab === 'day' ? 'on' : ''} aria-current={tab === 'day' ? 'page' : undefined} onClick={() => setTab('day')}>
            Day ahead
          </button>
          <button className={tab === 'accuracy' ? 'on' : ''} aria-current={tab === 'accuracy' ? 'page' : undefined} onClick={() => setTab('accuracy')}>
            Accuracy
          </button>
        </nav>
      </header>

      <div className="controls">
        {tab === 'day' && (
          <div className="field">
            <span className="label">Delivery day</span>
            <div className="daypick">
              <button aria-label="Previous day" disabled={date <= first} onClick={() => setDate(clamp(addDays(date, -1)))}>
                <ChevronLeft size={16} strokeWidth={1.5} aria-hidden />
              </button>
              <input type="date" aria-label="Delivery day" min={first} max={last} value={date} onChange={(e) => e.target.value && setDate(clamp(e.target.value))} />
              <button aria-label="Next day" disabled={date >= last} onClick={() => setDate(clamp(addDays(date, 1)))}>
                <ChevronRight size={16} strokeWidth={1.5} aria-hidden />
              </button>
            </div>
            <small>
              {fmtDay(date)}, decided {fmtDay(addDays(date, -1))}
            </small>
          </div>
        )}
        <div className="field">
          <span className="label">Decision cutoff, D-1 UK time</span>
          <div className="seg" role="group" aria-label="Decision cutoff">
            {CUTOFF_PRESETS.map((p) => (
              <button key={p.value} className={cutoff === p.value ? 'on' : ''} aria-pressed={cutoff === p.value} onClick={() => setCutoff(p.value)} title={p.label}>
                {p.value}
              </button>
            ))}
            <input
              type="time"
              step={1800}
              value={cutoff}
              onChange={(e) => /^\d\d:\d\d$/.test(e.target.value) && setCutoff(e.target.value)}
              aria-label="Custom cutoff"
            />
          </div>
          <small>Only forecasts published before this moment are used.</small>
        </div>
        <div className="field">
          <span className="label">Compare against wind</span>
          <div className="seg" role="group" aria-label="Compare against">
            {BASES.map((b) => (
              <button key={b.value} className={basis === b.value ? 'on' : ''} aria-pressed={basis === b.value} onClick={() => setBasis(b.value)} title={b.title}>
                {b.label}
              </button>
            ))}
          </div>
          <small>{BASES.find((b) => b.value === basis)!.title}</small>
        </div>
        <p className="meta">
          {meta.data.forecast_runs.toLocaleString()} forecast runs, every ~{meta.data.forecast_run_interval_h} h
          <br />
          {meta.data.actual_rows.toLocaleString()} half-hours of actuals
          <br />
          Source: Elexon BMRS
        </p>
      </div>

      <main>
        {accuracy.error && <ErrorBox message={accuracy.error} />}
        {tab === 'day' ? (
          <DayAheadView date={date} cutoff={cutoff} basis={basis} />
        ) : (
          <AccuracyView
            cutoff={cutoff}
            basis={basis}
            accuracy={accuracy.data}
            onPickDay={(d) => {
              setDate(clamp(d))
              setTab('day')
            }}
          />
        )}
      </main>

      <footer className="foot">
        Actuals: FUELHH (fuelType WIND). Forecasts: WINDFOR. Curtailment: accepted bids on wind units. Prices: system price and APX
        market index. Error = forecast − actual. Times in Europe/London. All data: Elexon BMRS.
      </footer>
    </div>
  )
}
