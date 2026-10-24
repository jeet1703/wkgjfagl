import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  unit?: string
  note?: ReactNode
  tone?: 'default' | 'accent' | 'warn'
}

export function Stat({ label, value, unit, note, tone = 'default' }: Props) {
  return (
    <div className={`stat stat--${tone}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value">
        {value}
        {unit && <span className="stat__unit">{unit}</span>}
      </div>
      {note && <div className="stat__note">{note}</div>}
    </div>
  )
}

export function Panel({ title, subtitle, children, aside }: { title: string; subtitle?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel__head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="panel__sub">{subtitle}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  )
}

export function Loading() {
  return <div className="state">Loading…</div>
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="state state--error">Couldn’t load data. {message}</div>
}
