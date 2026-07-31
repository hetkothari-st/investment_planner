# 02 — Data Layer

## Universe

Track **NSE equity, Nifty 500 constituents + any symbol the user pins**, plus indices.
Not all 2000+ listed names — the marginal value is negative (illiquid, unresearchable)
and it triples ingestion cost.

Store the universe as a dated table so historical membership is known (survivorship bias
matters when you later backtest your own scoring).

## Kite Connect integration

### Auth
Kite access tokens expire daily. For a personal single-user app:
- Store `api_key`, `api_secret` in `.env`.
- A `/auth/kite/login` route redirects to Kite; callback exchanges `request_token` → `access_token`.
- Persist `access_token` in Redis with a TTL to next 06:00 IST.
- On any `TokenException`, mark the pipeline degraded and surface a re-auth prompt.
  Do not retry silently — it will just burn requests.

### What Kite gives you
| Need | Kite endpoint | Notes |
|---|---|---|
| Instrument master | `kite.instruments()` | Full dump, refresh daily. ~1.5MB CSV. |
| Daily OHLCV | `kite.historical_data(token, from, to, "day")` | Max ~2000 candles/request. Backfill in chunks. |
| Intraday | same, interval `minute`/`5minute` | Only fetch for pinned symbols; storage grows fast. |
| Live quotes | WebSocket `KiteTicker` | Proxy through your API; don't expose creds to browser. |
| Corporate actions | **not reliably** | Use `historical_data(..., continuous=False)` unadjusted + separate CA source. |

### What Kite does NOT give you — plan for these separately
- Fundamentals (P&L, balance sheet, ratios)
- Corporate announcements text
- Shareholding patterns / promoter pledge
- Concall transcripts, annual reports
- IPO calendar

**Sourcing plan for these:** NSE/BSE public corporate-filing endpoints and the company's
own investor-relations pages. Build each as a separate `ingest/sources/<name>.py` with a
common `Source` protocol so any one can be swapped without touching downstream code.
Treat all of them as unreliable: retry, cache aggressively, and degrade gracefully.

```python
class Source(Protocol):
    name: str
    async def fetch(self, symbol: str, since: date) -> list[RawRecord]: ...
    def health(self) -> SourceHealth: ...
```

Expose source health in the UI. When promoter-pledge data is 90 days stale, the report
says so rather than quietly using old numbers.

---

## Schema

### Reference

```sql
CREATE TABLE instruments (
  instrument_token  BIGINT PRIMARY KEY,
  tradingsymbol     TEXT NOT NULL,
  exchange          TEXT NOT NULL,
  name              TEXT,
  isin              TEXT,
  segment           TEXT,
  lot_size          INT,
  tick_size         NUMERIC(10,4),
  expiry            DATE,
  instrument_type   TEXT,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tradingsymbol, exchange)
);

CREATE TABLE companies (
  isin              TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  sector            TEXT,
  industry          TEXT,
  mcap_band         TEXT CHECK (mcap_band IN ('LARGE','MID','SMALL','MICRO')),
  incorporated      DATE,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE universe_membership (
  isin              TEXT REFERENCES companies(isin),
  index_name        TEXT NOT NULL,      -- 'NIFTY500', 'PINNED'
  from_date         DATE NOT NULL,
  to_date           DATE,               -- NULL = current
  PRIMARY KEY (isin, index_name, from_date)
);

CREATE TABLE trading_calendar (
  trade_date        DATE PRIMARY KEY,
  exchange          TEXT NOT NULL DEFAULT 'NSE',
  is_trading_day    BOOLEAN NOT NULL,
  note              TEXT
);
```

### Market data (TimescaleDB hypertables)

```sql
CREATE TABLE ohlcv_daily (
  instrument_token  BIGINT NOT NULL,
  trade_date        DATE   NOT NULL,
  open   NUMERIC(18,4), high NUMERIC(18,4),
  low    NUMERIC(18,4), close NUMERIC(18,4),
  volume BIGINT,
  adj_close NUMERIC(18,4),          -- corporate-action adjusted
  source TEXT NOT NULL DEFAULT 'kite',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_token, trade_date)
);
SELECT create_hypertable('ohlcv_daily','trade_date', chunk_time_interval => INTERVAL '1 year');

CREATE TABLE corporate_actions (
  id BIGSERIAL PRIMARY KEY,
  isin TEXT NOT NULL,
  ex_date DATE NOT NULL,
  action_type TEXT NOT NULL,        -- SPLIT | BONUS | DIVIDEND | RIGHTS | MERGER
  ratio_from NUMERIC, ratio_to NUMERIC,
  amount NUMERIC(18,4),
  source TEXT NOT NULL,
  UNIQUE (isin, ex_date, action_type)
);
```

### Fundamentals & filings

```sql
CREATE TABLE fundamentals_period (
  isin TEXT NOT NULL,
  period_end DATE NOT NULL,
  period_type TEXT NOT NULL CHECK (period_type IN ('Q','H','FY')),
  consolidated BOOLEAN NOT NULL DEFAULT true,
  line_item TEXT NOT NULL,          -- 'revenue','ebitda','pat','total_debt','equity',...
  value NUMERIC(20,4),
  unit TEXT NOT NULL DEFAULT 'INR_CR',
  source TEXT NOT NULL,
  as_of TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (isin, period_end, period_type, consolidated, line_item)
);

CREATE TABLE filings (
  id BIGSERIAL PRIMARY KEY,
  isin TEXT NOT NULL,
  filed_at TIMESTAMPTZ NOT NULL,
  category TEXT NOT NULL,           -- RESULTS | ANNOUNCEMENT | PLEDGE | SHP | CONCALL | AR
  headline TEXT,
  body TEXT,
  url TEXT,
  content_hash TEXT NOT NULL UNIQUE,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shareholding (
  isin TEXT NOT NULL,
  period_end DATE NOT NULL,
  promoter_pct NUMERIC(6,3),
  promoter_pledged_pct NUMERIC(6,3),
  fii_pct NUMERIC(6,3),
  dii_pct NUMERIC(6,3),
  public_pct NUMERIC(6,3),
  source TEXT NOT NULL,
  PRIMARY KEY (isin, period_end)
);
```

### The deterministic spine

```sql
CREATE TABLE metric_values (
  isin        TEXT NOT NULL,
  field_id    TEXT NOT NULL,        -- e.g. 'val.pe_pctl_5y' — see 06-METRIC-REGISTRY
  as_of       DATE NOT NULL,
  value       NUMERIC(20,6),
  unit        TEXT NOT NULL,        -- 'pct','ratio','inr_cr','x','days','score'
  inputs_hash TEXT NOT NULL,        -- hash of the raw rows used; enables cache invalidation
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (isin, field_id, as_of)
);
SELECT create_hypertable('metric_values','as_of', chunk_time_interval => INTERVAL '1 year');

CREATE TABLE metric_gaps (
  isin TEXT NOT NULL, field_id TEXT NOT NULL, as_of DATE NOT NULL,
  reason TEXT NOT NULL,             -- 'INSUFFICIENT_HISTORY','SOURCE_STALE','NOT_APPLICABLE'
  PRIMARY KEY (isin, field_id, as_of)
);
```

### Qualitative facts (LLM extraction output — data, not prose)

```sql
CREATE TABLE qual_facts (
  id BIGSERIAL PRIMARY KEY,
  isin TEXT NOT NULL,
  filing_id BIGINT REFERENCES filings(id),
  fact_type TEXT NOT NULL,          -- CAPEX | ORDER_WIN | GUIDANCE | LITIGATION |
                                    -- MGMT_CHANGE | CAPITAL_RAISE | ACQUISITION | RISK
  direction TEXT CHECK (direction IN ('POSITIVE','NEGATIVE','NEUTRAL')),
  magnitude_band TEXT,              -- 'SMALL','MATERIAL','TRANSFORMATIVE'
  horizon_relevance TEXT[],         -- {'SHORT','MID','LONG'}
  summary TEXT NOT NULL,            -- <= 220 chars, no numbers unless quoted from filing
  evidence_span TEXT,               -- verbatim excerpt from source, for audit
  extracted_by TEXT NOT NULL,       -- model id
  extracted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Recommendations, falsifiers, simulation

```sql
CREATE TABLE recommendations (
  id UUID PRIMARY KEY,
  isin TEXT NOT NULL,
  horizon TEXT NOT NULL CHECK (horizon IN ('SHORT','MID','LONG')),
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_on DATE NOT NULL,
  ref_price NUMERIC(18,4) NOT NULL,
  band_bear_pct NUMERIC(8,3) NOT NULL,
  band_base_pct NUMERIC(8,3) NOT NULL,
  band_bull_pct NUMERIC(8,3) NOT NULL,
  conviction TEXT NOT NULL CHECK (conviction IN ('LOW','MODERATE','HIGH')),
  suggested_size_inr NUMERIC(18,2) NOT NULL,
  score_snapshot JSONB NOT NULL,     -- all metric values used, frozen
  weights_version TEXT NOT NULL,
  report_md TEXT NOT NULL,           -- rendered, post-substitution
  net_of_costs_hurdle_pct NUMERIC(8,3) NOT NULL,
  status TEXT NOT NULL DEFAULT 'LIVE' -- LIVE | EXPIRED | INVALIDATED
);
-- IMMUTABLE. Add a trigger that rejects UPDATE on all columns except `status`.

CREATE TABLE falsifiers (
  id UUID PRIMARY KEY,
  recommendation_id UUID REFERENCES recommendations(id),
  field_id TEXT NOT NULL,
  operator TEXT NOT NULL CHECK (operator IN ('LT','LTE','GT','GTE','CROSSES_BELOW','CROSSES_ABOVE')),
  threshold NUMERIC(20,6) NOT NULL,
  human_text TEXT NOT NULL,
  breached_at TIMESTAMPTZ
);

CREATE TABLE sim_positions (
  id UUID PRIMARY KEY,
  recommendation_id UUID REFERENCES recommendations(id),
  isin TEXT NOT NULL,
  opened_on DATE NOT NULL,
  qty INT NOT NULL,
  entry_price NUMERIC(18,4) NOT NULL,
  entry_costs_inr NUMERIC(18,2) NOT NULL,
  thesis_snapshot_md TEXT NOT NULL,   -- frozen copy; never regenerate
  closed_on DATE,
  exit_price NUMERIC(18,4),
  close_reason TEXT
);

CREATE TABLE sim_marks (
  position_id UUID NOT NULL,
  trade_date DATE NOT NULL,
  close_price NUMERIC(18,4) NOT NULL,
  mtm_inr NUMERIC(18,2) NOT NULL,
  unrealised_pct NUMERIC(10,4) NOT NULL,
  drawdown_from_peak_pct NUMERIC(10,4) NOT NULL,
  PRIMARY KEY (position_id, trade_date)
);

CREATE TABLE calibration_results (
  recommendation_id UUID PRIMARY KEY REFERENCES recommendations(id),
  scored_on DATE NOT NULL,
  actual_return_pct NUMERIC(10,4) NOT NULL,
  actual_net_return_pct NUMERIC(10,4) NOT NULL,
  in_band BOOLEAN NOT NULL,
  direction_correct BOOLEAN NOT NULL,
  brier NUMERIC(8,5),
  band_error_pct NUMERIC(10,4)
);

CREATE TABLE cascade_gap (
  id BIGSERIAL PRIMARY KEY,
  stage TEXT NOT NULL,
  isin TEXT, horizon TEXT,
  reason TEXT NOT NULL,
  raw_output TEXT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### User state

```sql
CREATE TABLE profile (
  id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),   -- single user, enforced
  display_name TEXT,
  monthly_inflow NUMERIC(18,2),
  fixed_outflow NUMERIC(18,2),
  variable_outflow NUMERIC(18,2),
  liquid_balance NUMERIC(18,2),
  dependants INT DEFAULT 0,
  job_stability TEXT CHECK (job_stability IN ('LOW','MEDIUM','HIGH')),
  max_tolerable_drawdown_inr NUMERIC(18,2),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE debts (
  id UUID PRIMARY KEY, label TEXT NOT NULL,
  principal_outstanding NUMERIC(18,2) NOT NULL,
  annual_rate_pct NUMERIC(6,3) NOT NULL,
  min_emi NUMERIC(18,2), tax_deductible BOOLEAN DEFAULT false
);

CREATE TABLE goals (
  id UUID PRIMARY KEY, label TEXT NOT NULL,
  target_amount NUMERIC(18,2) NOT NULL,
  target_date DATE NOT NULL,
  priority TEXT CHECK (priority IN ('MUST','SHOULD','WANT'))
);

CREATE TABLE plan_versions (
  id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  profile_snapshot JSONB NOT NULL,
  allocation JSONB NOT NULL,
  rationale_md TEXT NOT NULL,
  superseded_by UUID
);
```

## Backfill plan

1. Instrument dump → resolve Nifty 500 ISINs.
2. OHLCV: **10 years daily** for every universe member. ~500 symbols × ~2500 candles.
   At 3 req/s with 2000-candle chunks, that's roughly 2 requests per symbol → ~6 minutes.
   Do it once, then incremental daily.
3. Fundamentals: 20 quarters + 5 annual. Slowest part; run overnight, tolerate gaps.
4. Filings: 24 months of announcements. Store body text for LLM extraction.

Write `scripts/backfill.py` with `--symbols`, `--since`, `--only` flags and a resume file.
It will crash. Make it resumable.

## Implementation notes (M1, where reality diverged)

- **Trading calendar**: historical trading days are *observed* — a date is a trading
  day iff the NIFTY 50 index has an OHLCV bar for it. This is a record of what traded,
  not an inference from weekday rules, and it captures ad-hoc sessions (Budget
  Saturdays) exactly. Future holidays can't be observed, so they load from the
  exchange's published list via `load_holiday_csv` (`corpus/ingest/jobs/calendar.py`).
- **Corporate actions**: until a trustworthy automated source is wired, actions enter
  through a hand-maintained CSV (`scripts/load_corporate_actions.py`). Deliberate: a
  wrong split ratio silently corrupts every adjusted close, so the file must be
  auditable line by line. The `Source` protocol slot for an automated feed remains.
- **Adjustment scope**: only SPLIT and BONUS adjust `adj_close`. Dividends are cash
  in return computations; rights/mergers need case-by-case terms. Recorded, not
  auto-adjusted.
