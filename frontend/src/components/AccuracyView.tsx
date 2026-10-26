import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api, type AccuracyResponse, type Basis } from '../api'
import { fmtShortDay, gbp, mw, pct, signed } from '../format'
import { useAsync } from '../hooks'
import { C, axisProps, legendStyle, tooltipStyle } from './chartTheme'
import { ErrorBox, FigureTable, Loading, Section } from './Stat'

interface Props {
  cutoff: string
  basis: Basis
  accuracy: AccuracyResponse | null
  onPickDay: (day: string) => void
}

export function AccuracyView({ cutoff, basis, accuracy, onPickDay }: Props) {
  const horizons = useAsync(() => api.horizons(basis), [basis])
  if (!accuracy) return <Loading />
  const s = accuracy.summary
  const c = accuracy.curtailment
  const bt = accuracy.backtest
  const cost = accuracy.cost
  const saved = cost.forecast && cost.plan ? cost.forecast.net_cost - cost.plan.net_cost : null

  return (
    <div className="accuracy">
      <section className="lede" aria-label="Key findings">
        <p className="lede__statement">
          <span className="accent">{pct(c.explained_pct)}</span> of the forecast’s over-prediction was wind the grid paid to switch off.
        </p>
        <ol className="findings">
          <li>
            <h3>The weather forecast was mostly right</h3>
            <p>
              Against delivered wind the forecast ran <b>{signed(c.bias_metered)} MW</b> high. On average <b>{mw(c.mean_curtailed)} MW</b> was
              curtailed. Against available wind the bias is <b>{signed(c.bias_available)} MW</b> and the MAE falls from {mw(c.mae_metered)} to{' '}
              {mw(c.mae_available)} MW. Plan on forecast minus expected curtailment.
            </p>
          </li>
          <li>
            <h3>What it cost in January</h3>
            <p>
              Buying against the raw forecast left <b>{mw((cost.forecast?.imbalance_mwh ?? 0) / 1000)} GWh</b> to settle at imbalance, a net{' '}
              <b>{gbp(cost.forecast?.net_cost)}</b>. Against the plan figure: <b>{gbp(cost.plan?.net_cost)}</b>
              {saved != null && saved > 0 && <>, saving {gbp(saved)}</>}.
            </p>
            <p className="small">
              National scale, so scale by your share. Error × (imbalance − market price) per half-hour, D-1 {cutoff} forecasts. Average prices{' '}
              {gbp(cost.mean_market_price)} market, {gbp(cost.mean_imbalance_price)} imbalance per MWh.
            </p>
          </li>
          <li>
            <h3>A buffer tested without hindsight</h3>
            <p>
              Each day’s buffer used only the 14 days settled before the decision. The firm figure held in <b>{pct(bt.firm_coverage_pct)}</b> of
              hours against a 90% target, across {bt.days} days. The plan figure cut the typical error from {mw(bt.raw_mae)} to{' '}
              <b>{mw(bt.plan_mae)} MW</b>.
            </p>
          </li>
        </ol>
      </section>

      <Section
        kicker="Curtailment"
        title="Over-forecast against wind switched off, by day"
        subtitle="Bars: how far the forecast ran above delivered wind. Line: wind the grid paid to switch off. Where they match, the forecast was right about the wind and the grid did not take it."
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={c.by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" tickFormatter={fmtShortDay} minTickGap={24} {...axisProps} />
              <YAxis width={52} tickFormatter={(v) => mw(v)} {...axisProps} axisLine={false} />
              <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtShortDay(String(l))} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
              <Legend wrapperStyle={legendStyle} />
              <Bar dataKey="bias" name="Forecast − delivered (bias)" fill={C.shortfall} isAnimationActive={false}>
                {c.by_day.map((d) => (
                  <Cell key={d.day} fill={d.bias >= 0 ? C.shortfall : C.surplus} />
                ))}
              </Bar>
              <Line dataKey="curtailed" name="Wind switched off" stroke={C.actual} strokeWidth={1.75} dot={{ r: 2, fill: C.actual }} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Section>

      <div className="split split--wide">
        <Section kicker={basis === 'metered' ? 'Delivered wind' : 'Available wind'} title={`Accuracy at D-1 ${cutoff}`}>
          <FigureTable
            rows={[
              { label: 'Typical error (MAE)', value: mw(s.mae), unit: 'MW', note: `${s.nmae_pct?.toFixed(1)}% of average wind output` },
              { label: 'Bias', value: signed(s.bias), unit: 'MW', note: s.bias != null && s.bias > 0 ? 'Forecasts ran high on average' : 'Forecasts ran low on average' },
              { label: '90% of periods within', value: `±${mw(s.p90_abs)}`, unit: 'MW', note: `P99 ±${mw(s.p99_abs)}, worst ${mw(s.max_abs)} MW` },
              { label: 'Shortfall to plan for (P90)', value: mw(s.shortfall_p90), unit: 'MW', note: 'Hold this much less wind to be covered 9 times in 10', tone: 'accent' },
              { label: 'Shortfall, P95', value: mw(s.shortfall_p95), unit: 'MW', note: 'Wind falls short by more than this only 5% of the time' },
              { label: 'Agreement (R²)', value: s.r2 ?? '—', note: `${s.n.toLocaleString()} paired periods, ${Math.round(s.coverage * 100)}% coverage` },
            ]}
          />
        </Section>

        <Section
          kicker="Lead time"
          title="Error grows with lead time"
          subtitle="The latest forecast published at least H hours before each target. Shaded: where day-ahead decisions sit."
        >
          {horizons.error ? (
            <ErrorBox message={horizons.error} />
          ) : !horizons.data ? (
            <Loading />
          ) : (
            <div className="chart">
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={horizons.data.rows} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="horizon_h" type="number" domain={[0, 48]} ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]} unit="h" {...axisProps} />
                  <YAxis width={52} domain={[0, 'auto']} tickFormatter={(v) => mw(v)} {...axisProps} axisLine={false} />
                  <ReferenceArea x1={15} x2={39} fill={C.actual} fillOpacity={0.04} label={{ value: 'day-ahead', position: 'insideTop', fill: C.axis, fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} labelFormatter={(l) => `${l} h ahead`} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
                  <Legend iconType="plainline" wrapperStyle={legendStyle} />
                  <Line dataKey="mae" name="MAE" stroke={C.actual} strokeWidth={2} dot={{ r: 2.5, fill: C.actual }} isAnimationActive={false} />
                  <Line dataKey="p90_abs" name="P90 absolute error" stroke={C.forecast} strokeWidth={1.5} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
      </div>

      <div className="split split--even">
        <Section title="Error by delivery day" subtitle="Mean absolute error per day. Red: worse than the month’s P90. Select a bar to open that day.">
          <div className="chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={accuracy.by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="day" tickFormatter={fmtShortDay} minTickGap={24} {...axisProps} />
                <YAxis width={52} tickFormatter={(v) => mw(v)} {...axisProps} axisLine={false} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtShortDay(String(l))} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
                <Bar dataKey="mae" name="MAE" cursor="pointer" onClick={(e) => onPickDay(String((e as { day?: string }).day))}>
                  {accuracy.by_day.map((d) => (
                    <Cell key={d.day} fill={s.p90_abs != null && d.mae > s.p90_abs ? C.shortfall : C.surplus} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="Error distribution" subtitle="Forecast − actual, half-hourly. Right of zero: wind fell short.">
          <div className="chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={accuracy.histogram} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={1}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="from" tickFormatter={(v) => (Number(v) / 1000).toFixed(1)} minTickGap={20} unit=" GW" {...axisProps} />
                <YAxis width={40} unit="%" {...axisProps} axisLine={false} />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={(_, p) => {
                    const b = p?.[0]?.payload as { from: number; to: number } | undefined
                    return b ? `${signed(b.from)} to ${signed(b.to)} MW` : ''
                  }}
                  formatter={(v) => [`${v}% of periods`, 'Share']}
                />
                <Bar dataKey="pct" isAnimationActive={false}>
                  {accuracy.histogram.map((b) => (
                    <Cell key={b.from} fill={b.from >= 0 ? C.shortfall : C.surplus} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>

      <Section title="Error by time of day" subtitle="Where in the day the forecast is least reliable (UK local time).">
        <div className="chart">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={accuracy.by_hour} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, '0')}:00`} {...axisProps} />
              <YAxis width={52} tickFormatter={(v) => mw(v)} {...axisProps} axisLine={false} />
              <Tooltip {...tooltipStyle} labelFormatter={(h) => `${String(h).padStart(2, '0')}:00`} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
              <Legend wrapperStyle={legendStyle} />
              <Bar dataKey="mae" name="MAE" fill={C.actual} isAnimationActive={false} />
              <Bar dataKey="p90_abs" name="P90 absolute error" fill={C.later} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Section>
    </div>
  )
}
