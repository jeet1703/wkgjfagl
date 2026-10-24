# Video script (target 9 min, hard limit 10)

Lead with the insight, not the code. Numbers below are from the January 2026 snapshot at the default D-1 09:00 cutoff.

## Part 1: Client pitch (≈4.5 min)

1. **The problem (30 s).**
   - "Every morning your desk buys tomorrow's power. Wind is the biggest unknown, and you only see it through a forecast."
   - "Whatever the wind misses by, you settle at the imbalance price."

2. **The headline (1 min). Open the Forecast accuracy tab.**
   - "Against the wind you actually received, the forecast ran **1.7 GW high** on average, every single week."
   - "That looks like a bad forecast. It isn't. On average **1.6 GW of wind was paid to switch off** by the grid because of network constraints. That explains **91%** of the gap."
   - Point at the *Over-forecast vs wind switched off* chart: "Bars and line move together. 11–12 Jan: the forecast was right about the wind; the grid just didn't take it."
   - Flip to **Wind available**: "Judged fairly, the bias is +163 MW and the typical error halves, from 2.0 to 1.2 GW."
   - "So: plan on forecast *minus expected curtailment*, not the raw forecast."

3. **What it cost (45 s). Finding 2.**
   - "Buying against the raw forecast cost about **£3.0m** in imbalance in January, sized as if you bought for all of GB's wind. Scale by your share."
   - "Buying against our plan figure would have cost **£1.5m**, halving it."

4. **The morning brief (1.5 min). Day-ahead tab, pick 15 Jan.**
   - Decision banner: "Exactly what you knew at 09:00 the day before, and which forecast run that was."
   - Brief: "Forecast says 11.6 GW. **Plan on 9.8 GW.** You can count on **6.8 GW** 9 times out of 10. Last 14 days, the forecast ran 16% high."
   - "All three numbers come only from days already settled at the decision. No hindsight."
   - Chart: dashed forecast, plan line, shaded firm-to-plan range, grey dotted = wind switched off.
   - "How the forecast evolved": "Later runs still moved. That's the cost of deciding at 09:00." Switch the cutoff to 06:00 and back to 11:00.

5. **Close (30 s).**
   - "Three takeaways: correct for curtailment, plan on the plan figure, hold the firm buffer."
   - Next phase: forecast curtailment itself, add demand and solar, and send a morning alert when runs disagree.

## Part 2: Tech lead review (≈4.5 min)

1. **Architecture (40 s).** One container: React with Vite and Recharts, FastAPI, a pure pandas domain layer, and a CSV snapshot of four Elexon datasets (FUELHH, WINDFOR, wind bid volumes, prices). The demo never calls Elexon at request time.

2. **The rule that matters (60 s).** `domain/selection.py` plus its test:
   - the cutoff is D-1 at UK local time, converted to UTC (BST-safe);
   - `merge_asof(by=start_time, direction="backward")` picks the latest `publish_time` ≤ cutoff;
   - show `test_picks_latest_forecast_published_before_cutoff`: the 11:30 run exists but was not yet available at 09:00, so it is never used;
   - other tests cover an exact-cutoff publish, no eligible forecast and no cross-target leakage.

3. **No hindsight, twice (60 s).** `domain/planning.py`:
   - planning figures for day D use only days D-15..D-2, all settled before the D-1 cutoff;
   - show `test_rolling_window_is_d15_to_d2_only`: a 9,999 MW error on D-1, D and D-16 changes nothing;
   - the backtest is honest: the firm figure held in **87%** of hours against a 90% target. "Slightly under-covered. I'm showing it rather than tuning it away."

4. **Curtailment and cost (45 s).**
   - `domain/curtailment.py`: available = metered + accepted bids on wind units. Every endpoint takes `basis=metered|available`.
   - `domain/cost.py`: cost = error × (imbalance − market price) per half-hour. The sign convention is pinned by `test_cost_sign_convention`.

5. **Practices and limitations (50 s).**
   - 34 pytest tests, ruff, CI (backend, frontend, Docker build), non-root multi-stage image.
   - Deployed on Render's free plan with a self-ping keep-alive and a health check.
   - Limitations:
     - curtailment volumes are Elexon's *indicative* figures;
     - MID is a proxy for the price of buying ahead;
     - the cost is at national scale;
     - one month of data.
