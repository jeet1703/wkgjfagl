// Typed client for the FastAPI backend. Shapes mirror backend/app/api.py.

const BASE = import.meta.env.VITE_API_URL ?? ''

export interface Summary {
  n: number
  coverage: number
  mae?: number
  rmse?: number
  bias?: number
  nmae_pct?: number | null
  mean_actual?: number
  p50_abs?: number
  p90_abs?: number
  p99_abs?: number
  max_abs?: number
  shortfall_p90?: number
  shortfall_p95?: number
  surplus_p90?: number
  r2?: number | null
}

export interface Meta {
  decision_window: [string, string]
  delivery_window: [string, string]
  default_cutoff: string
  timezone: string
  actual_rows: number
  forecast_rows: number
  forecast_runs: number
  forecast_run_interval_h: number | null
  forecast_resolution_min: number | null
  forecast_max_horizon_h: number | null
  last_actual: string | null
}

export interface SeriesPoint {
  t: string
  actual: number | null
  forecast: number | null
  plan: number | null
  firm: number | null
  curtailed: number | null
  publish_time: string | null
  horizon_h: number | null
}

export interface Vintage {
  publish_time: string
  available_at_cutoff: boolean
  points: { t: string; v: number }[]
}

export type Basis = 'metered' | 'available'

/** Planning figures for one delivery day, sized only from days settled before the cutoff. */
export interface Outlook {
  available: boolean
  forecast_mean?: number
  plan_mean?: number
  firm_mean?: number
  bias?: number
  buffer_p90?: number
  ran_high_pct?: number
  n_days?: number
}

export interface DayResponse {
  date: string
  cutoff_local: string
  basis: Basis
  cutoff_utc: string | null
  forecast_publish_time: string | null
  summary: Summary
  outlook: Outlook
  series: SeriesPoint[]
  vintages: Vintage[]
}

export interface Backtest {
  n: number
  days?: number
  firm_coverage_pct?: number
  raw_mae?: number
  plan_mae?: number
  raw_bias?: number
  plan_bias?: number
}

export interface Curtailment {
  n: number
  mean_curtailed?: number
  max_curtailed?: number
  bias_metered?: number
  bias_available?: number
  mae_metered?: number
  mae_available?: number
  explained_pct?: number | null
  by_day: { day: string; bias: number; curtailed: number }[]
}

export interface CostLine {
  net_cost: number
  cost_shortfall: number
  cost_surplus: number
  imbalance_mwh: number
}

export interface Cost {
  n: number
  mean_market_price?: number
  mean_imbalance_price?: number
  forecast?: CostLine
  plan?: CostLine
}

export interface AccuracyResponse {
  cutoff_local: string
  basis: Basis
  summary: Summary
  backtest: Backtest
  curtailment: Curtailment
  cost: Cost
  by_day: { day: string; mae: number; bias: number; mean_actual: number; mean_forecast: number }[]
  by_hour: { hour: number; mae: number; bias: number; p90_abs: number }[]
  histogram: { from: number; to: number; count: number; pct: number }[]
}

export interface HorizonRow {
  horizon_h: number
  n: number
  mae: number
  rmse: number
  bias: number
  p90_abs: number
  shortfall_p90: number
}

export type NoteMode = 'brief' | 'review'

/** Short trading note written by Gemini from the app's own numbers (see backend/app/ai.py). */
export interface AiNote {
  headline: string
  points: string[]
  action: string
  mode: NoteMode
  model: string
  /** Exactly the figures Gemini was given. */
  facts: Record<string, unknown>
}

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE}/api${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  meta: () => get<Meta>('/meta'),
  day: (date: string, cutoff: string, basis: Basis) => get<DayResponse>('/day', { date, cutoff, basis }),
  accuracy: (cutoff: string, basis: Basis) => get<AccuracyResponse>('/accuracy', { cutoff, basis }),
  aiStatus: () => get<{ enabled: boolean; model: string | null }>('/ai/status'),
  aiNote: (date: string, cutoff: string, basis: Basis, mode: NoteMode) => get<AiNote>('/ai/note', { date, cutoff, basis, mode }),
  horizons: (basis: Basis) => get<{ rows: HorizonRow[] }>('/horizons', { basis }),
}
