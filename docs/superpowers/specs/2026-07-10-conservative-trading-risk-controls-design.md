# Conservative Trading Risk Controls Design

## Context

Recent realized-trade analysis showed the strategy is not failing because every pick is wrong. The current realized win rate is above 50%, but the payoff ratio is below 1.0: average losses are larger than average wins. A small number of large losses, especially high-volatility chased entries, can wipe out many small profitable exits.

The current engine already has Agent-driven stock selection and trend-first position management. This design keeps that architecture and adds hard execution-layer guardrails so Agent recommendations remain useful but cannot create outsized losses or low-quality entries.

## Goals

1. Reduce large single-trade losses.
2. Reduce chasing entries after excessive intraday gains.
3. Make position sizing more suitable for a ¥10,000 account.
4. Require reliable buy confidence before opening new positions.
5. Improve decision logs so skipped trades explain the hard rule that blocked them.

## Non-goals

1. Do not replace the Agent architecture.
2. Do not add new external dependencies.
3. Do not optimize for maximum trade frequency.
4. Do not change database schema.
5. Do not implement predictive backtesting in this iteration.

## Design

### Strategy parameters

Update the default `AutonomousTradingEngine` parameters from balanced-aggressive to conservative-enhanced:

- `stop_loss_pct`: `5.0` remains the standard hard-loss threshold for normal positions.
- `max_position_pct`: reduce from `50.0` to `30.0`.
- `max_buy_per_day`: reduce from `8000.0` to `5000.0`.
- `single_buy_min`: reduce from `3000.0` to `2000.0`.
- `single_buy_max`: reduce from `5000.0` to `3000.0`.
- Add `min_buy_confidence = 70.0`.
- Add `max_chase_pct = 7.0`.
- Add `late_buy_cutoff = 14:30`.
- Add `profit_protect_pct = 6.0`.

### Buy execution guardrails

Before executing a new buy pick, the execution layer must reject it when:

1. `confidence` is missing or cannot be parsed as a number.
2. `confidence <= min_buy_confidence`.
3. Quote percentage change is greater than `max_chase_pct` for non-ETF symbols.
4. Current Beijing time is at or after 14:30.
5. Existing cash, lot size, max position count, single-buy amount, or daily-buy amount checks fail.

Rejected candidates are logged to `decision_log` with `action='skip'`, the candidate symbol/name/price, optional confidence score when available, and a reason that states the exact rule.

### Hard stop loss

Before running the Agent position actions, the engine already loops through current positions. Replace the current extreme-only forced stop with standard hard stop behavior:

- If available-to-sell quantity is greater than zero and `pnl_pct <= -stop_loss_pct`, sell all available quantity immediately.
- Keep the existing extreme stop behavior conceptually, but it becomes redundant because `-5%` triggers first.
- If available-to-sell quantity is zero and the position is below the hard stop, log a skip/hold note explaining that T+1 prevents immediate sell. Do not buy more of that symbol.

This is intentionally execution-layer behavior, not Agent behavior. The Agent can still recommend hold, but the engine does not allow a sellable position to remain below hard stop.

### Profit protection

Profit protection is introduced as a helper and light execution-layer guardrail:

- If a position has `pnl_pct >= profit_protect_pct`, compute a protected stop level at the maximum of current stored stop and approximate breakeven.
- Breakeven stop can be the average cost rounded to 3 decimals.
- Do not force sell at `+6%`; only update stored stop metadata when it would tighten risk.
- When `price <= pos.stop_loss` and the position is sellable, the hard stop logic exits.

This preserves trend-following upside while reducing the chance that a good trade turns into a loss.

### Confidence logging

Confidence must be parsed through one helper:

```python
def parse_confidence(value) -> Optional[float]
```

Rules:

- Return `None` for missing, blank, non-numeric, NaN, or infinite values.
- Return a rounded float for valid numbers.

Buy execution uses `None` as a hard reject. Position actions may still display confidence as `unknown` in logs when the Agent omits it, but this iteration only requires strict buy enforcement.

## Testing Strategy

Add focused unit tests in `tests/test_position_management.py` for pure helpers and engine defaults:

1. `parse_confidence` accepts valid numeric input.
2. `parse_confidence` rejects missing and non-numeric input.
3. `should_skip_buy_pick` rejects missing confidence.
4. `should_skip_buy_pick` rejects confidence equal to the minimum threshold.
5. `should_skip_buy_pick` rejects non-ETF candidates whose quote pct exceeds the chase limit.
6. `should_skip_buy_pick` allows ETF candidates above the chase limit.
7. `should_skip_buy_pick` rejects late-session new buys at or after 14:30.
8. `should_force_exit` already covers hard stop behavior and remains the core pure stop-loss test.
9. `AutonomousTradingEngine` defaults reflect the conservative sizing parameters.

Manual verification after implementation:

1. Run `pytest tests/test_position_management.py -v`.
2. Run the existing test suite with `pytest -v`.
3. Start the app and verify `/api/metrics` still responds.

## Expected Outcome

The system should trade less aggressively, reject weak or overextended entries, and cut sellable losing positions at the configured hard stop. The short-term effect may be fewer trades. The intended quality improvement is lower average loss, lower max single-trade loss, and a payoff ratio above 1.0 after enough new trades accumulate.
