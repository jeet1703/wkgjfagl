// One palette for every chart: ink and greys on paper, with vermilion as the single accent.
// The accent always marks the number the desk should act on (plan, shortfall), never decoration.
export const C = {
  actual: '#16161a', // what happened
  forecast: '#8c8a84', // the raw forecast: context, not the recommendation
  plan: '#c8411b', // the accent: what to plan on
  band: '#c8411b',
  later: '#c9c6bf',
  shortfall: '#c8411b',
  surplus: '#b7b4ad',
  grid: '#e6e3dc',
  axis: '#6b6963',
}

const MONO = 'IBM Plex Mono, ui-monospace, monospace'

export const axisProps = {
  stroke: C.axis,
  tick: { fill: C.axis, fontSize: 11, fontFamily: MONO },
  tickLine: false,
  axisLine: { stroke: '#16161a' },
}

export const tooltipStyle = {
  contentStyle: {
    borderRadius: 0,
    background: '#fbfaf7',
    border: '1px solid #16161a',
    boxShadow: 'none',
    fontSize: 12,
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  labelStyle: { fontWeight: 600, color: '#16161a', marginBottom: 4 },
  itemStyle: { color: '#16161a', fontFamily: MONO, fontSize: 11.5 },
  cursor: { stroke: '#16161a', strokeWidth: 1, fill: 'rgba(22,22,26,0.04)' },
}

export const legendStyle = { fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif', color: '#3a3936' }
