import { BarChart3, CalendarDays, ChevronLeft, ChevronRight, Clock, Database, Layers, Radio, Timer, Wind } from 'lucide-react'
import { useState, type ReactNode } from 'react'

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
  { value: 'metered', label: 'Wind delivered', title: 'Metered output – what you actually receive.' },
  { value: 'available', label: 'Wind available', title: 'Delivered + wind the grid paid to switch off – fair test of forecast skill.' },
]

/** Mesh-gradient decoration behind the glass layer. Purely visual. */
function Shell({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="orbs" aria-hidden>
        <div className="orb orb--1" />
        <div className="orb orb--2" />
        <div className="orb orb--3" />
      </div>
      <div className="app">{children}</div>
    </>
  )
}

const ico = { size: 15, strokeWidth: 1.75, className: 'ico', 'aria-hidden': true } as const

export default function App() {
  const meta = useAsync(() => api.meta(), [])
  const [tab, setTab] = useState<Tab>('day')
  const [date, setDate] = useState('2026-01-15')
  const [cutoff, setCutoff] = useState('09:00')
  const [basis, setBasis] = useState<Basis>('metered')
  const accuracy = useAsync(() => api.accuracy(cutoff, basis), [cutoff, basis])

  if (meta.error) return <Shell><ErrorBox message={meta.error} /></Shell>
  if (!meta.data) return <Shell><Loading /></Shell>
  const [first, last] = meta.data.delivery_window
  const clamp = (d: string) => (d < first ? first : d > last ? last : d)

  return (
    <Shell>
      <header className="top">
        <div className="brand">
          <div className="brand__logo glass">
            <Wind size={24} strokeWidth={1.75} aria-hidden />
          </div>
          <div>
            <h1>Windcast Desk</h1>
            <p>GB national wind · day-ahead purchasing pilot · decisions in January 2026</p>
          </div>
        </div>
        <nav className="tabs" aria-label="Views">
          <button className={tab === 'day' ? 'on' : ''} onClick={() => setTab('day')}>
            <CalendarDays {...ico} />
            Day-ahead view
          </button>
          <button className={tab === 'accuracy' ? 'on' : ''} onClick={() => setTab('accuracy')}>
            <BarChart3 {...ico} />
            Forecast accuracy
          </button>
        </nav>
      </header>

      <div className="controls">
        {tab === 'day' && (
          <label className="field">
            <span>
              <CalendarDays {...ico} size={13} /> Delivery day
            </span>
            <div className="daypick">
              <button aria-label="Previous day" disabled={date <= first} onClick={() => setDate(clamp(addDays(date, -1)))}>
                <ChevronLeft size={16} strokeWidth={1.75} aria-hidden />
              </button>
              <input type="date" min={first} max={last} value={date} onChange={(e) => e.target.value && setDate(clamp(e.target.value))} />
              <button aria-label="Next day" disabled={date >= last} onClick={() => setDate(clamp(addDays(date, 1)))}>
                <ChevronRight size={16} strokeWidth={1.75} aria-hidden />
              </button>
            </div>
            <small>{fmtDay(date)} · decided {fmtDay(addDays(date, -1))}</small>
          </label>
        )}
        <label className="field">
          <span>
            <Clock {...ico} size={13} /> Decision cutoff (D-1, UK time)
          </span>
          <div className="seg">
            {CUTOFF_PRESETS.map((p) => (
              <button key={p.value} className={cutoff === p.value ? 'on' : ''} onClick={() => setCutoff(p.value)} title={p.label}>
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
        </label>
        <label className="field">
          <span>
            <Layers {...ico} size={13} /> Compare forecast against
          </span>
          <div className="seg">
            {BASES.map((b) => (
              <button key={b.value} className={basis === b.value ? 'on' : ''} onClick={() => setBasis(b.value)} title={b.title}>
                {b.label}
              </button>
            ))}
          </div>
          <small>{BASES.find((b) => b.value === basis)!.title}</small>
        </label>
        <div className="meta-chip">
          <span>
            <Radio {...ico} size={12} />
            {meta.data.forecast_runs.toLocaleString()} forecast runs
          </span>
          <span>
            <Timer {...ico} size={12} />
            every ~{meta.data.forecast_run_interval_h} h
          </span>
          <span>
            <Wind {...ico} size={12} />
            {meta.data.actual_rows.toLocaleString()} half-hours of actuals
          </span>
          <span>
            <Database {...ico} size={12} />
            Elexon BMRS
          </span>
        </div>
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
        Actuals: FUELHH (fuelType WIND). Forecasts: WINDFOR. Error = forecast − actual. Times in Europe/London.
      </footer>
    </Shell>
  )
}
