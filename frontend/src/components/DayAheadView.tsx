import { useMemo } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api, type Basis, type SeriesPoint } from '../api'
import { fmtDateTime, fmtDay, fmtTime, gw, mw, pct, signed } from '../format'
import { useAsync } from '../hooks'
import { AiNote } from './AiNote'
import { C, axisProps, legendStyle, tooltipStyle } from './chartTheme'
import { ErrorBox, FigureTable, Loading, Section } from './Stat'

interface Props {
  date: string
  cutoff: string
  basis: Basis
}

const gwTick = (v: number) => (v / 1000).toLocaleString('en-GB', { maximumFractionDigits: 1 })

/** Share of half-hours where at least the firm figure arrived. */
function firmHeld(series: SeriesPoint[]) {
  const p = series.filter((x) => x.actual != null && x.firm != null)
  if (!p.length) return null
  return (100 * p.filter((x) => x.actual! >= x.firm!).length) / p.length
}

export function DayAheadView({ date, cutoff, basis }: Props) {
  const day = useAsync(() => api.day(date, cutoff, basis), [date, cutoff, basis])

  const rows = useMemo(() => {
    if (!day.data) return []
    const metered = day.data.basis === 'metered'
    return day.data.series.map((p) => ({
      t: p.t,
      actual: p.actual,
      forecast: p.forecast,
      plan: p.plan,
      firm: p.firm,
      // Between the firm figure and the plan: where to expect delivered wind.
      band: p.firm == null || p.plan == null ? null : [p.firm, Math.max(p.firm, p.plan)],
      // On the delivered basis, what wind could have done without the grid switching it off.
      available: metered && p.actual != null && (p.curtailed ?? 0) > 0 ? p.actual + (p.curtailed ?? 0) : null,
    }))
  }, [day.data])

  const vintageRows = useMemo(() => {
    if (!day.data) return []
    const byT = new Map<string, Record<string, number | string | null>>()
    for (const p of day.data.series) byT.set(p.t, { t: p.t, actual: p.actual })
    day.data.vintages.forEach((v, i) => {
      for (const pt of v.points) {
        const row = byT.get(pt.t) ?? { t: pt.t }
        row[`v${i}`] = pt.v
        byT.set(pt.t, row)
      }
    })
    return [...byT.values()].sort((a, b) => String(a.t).localeCompare(String(b.t)))
  }, [day.data])

  if (day.loading && !day.data) return <Loading />
  if (day.error) return <ErrorBox message={day.error} />
  const d = day.data!
  const s = d.summary
  const o = d.outlook
  const curtailed = d.series.map((p) => p.curtailed ?? 0)
  const meanCurtailed = curtailed.length ? curtailed.reduce((a, b) => a + b, 0) / curtailed.length : 0
  const held = firmHeld(d.series)
  const used = d.forecast_publish_time
  const leadAtStart = used && d.series.length ? (new Date(d.series[0].t).getTime() - new Date(used).getTime()) / 3.6e6 : null

  return (
    <div className="split">
      <aside className="split__side">
        <dl className="decision">
          <div>
            <dt>Decision point</dt>
            <dd>{d.cutoff_utc ? fmtDateTime(d.cutoff_utc) : '—'}</dd>
            <dd className="muted">for delivery on {fmtDay(d.date)}</dd>
          </div>
          <div>
            <dt>Latest forecast available</dt>
            {used ? (
              <>
                <dd>Published {fmtDateTime(used)}</dd>
                <dd className="muted">{leadAtStart?.toFixed(0)} h before delivery starts</dd>
              </>
            ) : (
              <dd className="warn">No forecast had been published yet</dd>
            )}
          </div>
        </dl>

        <section className="brief" aria-label="Morning brief">
          <h2 className="brief__title">Morning brief</h2>
          <p className="brief__lede">
            Buying for {fmtDay(d.date)}.
            {o.ran_high_pct != null && (
              <>
                {' '}
                Over the last {o.n_days} days the forecast ran <b>{pct(Math.abs(o.ran_high_pct))} {o.ran_high_pct > 0 ? 'high' : 'low'}</b>.
              </>
            )}
          </p>
          <dl className="brief__nums">
            <div>
              <dt>Forecast says</dt>
              <dd className="num">
                {gw(o.forecast_mean)}
                <span className="unit">GW</span>
              </dd>
              <dd className="note">latest run before the cutoff</dd>
            </div>
            <div className="brief__plan">
              <dt>Plan on</dt>
              <dd className="num">
                {gw(o.plan_mean)}
                <span className="unit">GW</span>
              </dd>
              <dd className="note">forecast {signed(o.bias != null ? -o.bias : null)} MW recent bias</dd>
            </div>
            <div>
              <dt>Firm, 90% safe</dt>
              <dd className="num">
                {gw(o.firm_mean)}
                <span className="unit">GW</span>
              </dd>
              <dd className="note">forecast − {mw(o.buffer_p90)} MW buffer</dd>
            </div>
          </dl>
          <p className="brief__foot">
            {o.plan_mean == null
              ? `Not enough settled history before this day (${o.n_days ?? 0} days) to size planning figures.`
              : `Sized only from the ${o.n_days} delivery days already settled at the decision (D-15 to D-2), so no hindsight.`}
          </p>
        </section>

        <AiNote date={d.date} cutoff={d.cutoff_local} basis={d.basis} />
      </aside>

      <div className="split__main">
        <Section
          kicker={fmtDay(d.date)}
          title="Forecast at decision time against what happened"
          subtitle="Red line: the plan figure. Shaded: from the firm figure up to the plan, both sized from settled days only. Grey dotted: wind that was available but switched off by the grid."
        >
          <div className="chart">
            <ResponsiveContainer width="100%" height={360}>
              <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="t" tickFormatter={fmtTime} minTickGap={40} {...axisProps} />
                <YAxis tickFormatter={gwTick} width={40} {...axisProps} axisLine={false} label={{ value: 'GW', angle: -90, position: 'insideLeft', fill: C.axis, fontSize: 11 }} />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={(l) => fmtTime(String(l))}
                  formatter={(v, name) =>
                    Array.isArray(v) ? [`${mw(v[0] as number)} – ${mw(v[1] as number)} MW`, name] : [`${mw(v as number)} MW`, name]
                  }
                />
                <Legend iconType="plainline" wrapperStyle={legendStyle} />
                <Area dataKey="band" name="Firm → plan range" fill={C.band} fillOpacity={0.09} stroke="none" connectNulls isAnimationActive={false} />
                <Line dataKey="forecast" name="Day-ahead forecast" stroke={C.forecast} strokeWidth={1.75} strokeDasharray="5 4" dot={false} connectNulls isAnimationActive={false} />
                <Line dataKey="plan" name="Plan figure" stroke={C.plan} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                <Line dataKey="firm" name="Firm (90%)" stroke={C.plan} strokeWidth={1} strokeDasharray="2 3" dot={false} connectNulls isAnimationActive={false} />
                <Line dataKey="available" name="Available (incl. switched off)" stroke={C.forecast} strokeWidth={1.25} strokeDasharray="1 3" dot={false} connectNulls isAnimationActive={false} />
                <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="The day in numbers">
          <FigureTable
            rows={[
              {
                label: 'Actual wind, day average',
                value: gw(s.mean_actual),
                unit: 'GW',
                note: d.basis === 'metered' ? 'Metered, delivered (FUELHH)' : 'Delivered plus switched off',
              },
              {
                label: 'Forecast error (MAE)',
                value: mw(s.mae),
                unit: 'MW',
                note: s.bias != null ? `Bias ${signed(s.bias)} MW, ${s.bias > 0 ? 'wind fell short' : 'wind beat the forecast'}` : undefined,
              },
              { label: 'Wind switched off by the grid', value: gw(meanCurtailed), unit: 'GW', note: 'Paid to reduce output, mostly network constraints' },
              {
                label: 'Firm figure held',
                value: pct(held),
                note: 'Share of half-hours where delivered wind reached the firm figure (target 90%)',
                tone: held != null && held < 80 ? 'accent' : 'default',
              },
            ]}
          />
        </Section>

        <Section
          title="How the forecast evolved"
          subtitle="Solid grey runs were available before your cutoff; dashed light runs arrived after it. Black is what actually happened."
        >
          <div className="chart">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={vintageRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="t" tickFormatter={fmtTime} minTickGap={40} {...axisProps} />
                <YAxis tickFormatter={gwTick} width={40} {...axisProps} axisLine={false} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtTime(String(l))} formatter={(v, name) => [`${mw(v as number)} MW`, name]} />
                {d.vintages.map((v, i) => (
                  <Line
                    key={v.publish_time}
                    dataKey={`v${i}`}
                    name={`Run ${fmtDateTime(v.publish_time)}${v.available_at_cutoff ? '' : ' (after cutoff)'}`}
                    stroke={v.available_at_cutoff ? C.forecast : C.later}
                    strokeDasharray={v.available_at_cutoff ? undefined : '4 3'}
                    strokeWidth={1.25}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
                <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>
    </div>
  )
}
