import type { ReactNode } from 'react'

/** A titled block separated by a hairline rule. No card container: space does the grouping. */
export function Section({
  title,
  kicker,
  subtitle,
  children,
  aside,
  className = '',
}: {
  title: string
  kicker?: string
  subtitle?: ReactNode
  children: ReactNode
  aside?: ReactNode
  className?: string
}) {
  return (
    <section className={`section ${className}`}>
      <header className="section__head">
        <div>
          {kicker && <span className="kicker">{kicker}</span>}
          <h2>{title}</h2>
          {subtitle && <p className="section__sub">{subtitle}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  )
}

export interface FigureRow {
  label: string
  value: ReactNode
  unit?: string
  note?: ReactNode
  /** Accent marks the one figure to act on. */
  tone?: 'default' | 'accent' | 'muted'
}

/** Figures as a ruled data table: label, value, note. */
export function FigureTable({ rows, caption }: { rows: FigureRow[]; caption?: string }) {
  return (
    <table className="figtable">
      {caption && <caption>{caption}</caption>}
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} className={`figtable__row figtable__row--${r.tone ?? 'default'}`}>
            <th scope="row">{r.label}</th>
            <td className="figtable__value">
              {r.value}
              {r.unit && <span className="unit">{r.unit}</span>}
            </td>
            <td className="figtable__note">{r.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function Loading() {
  return <div className="state">Loading…</div>
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="state state--error">Couldn’t load data. {message}</div>
}
