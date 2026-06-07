# Vendor Insight360 — Vendor Analytics & Optimization Platform

A Streamlit analytics platform for managing a 120-vendor portfolio across
**performance**, **financials**, **risk**, and **compliance** — with a
supervised churn model, backtested forecasting, statistical hypothesis
testing, and cohort/funnel analysis built on a realistic 24-month demo
dataset.

> **The headline:** every model in this project reports honest, validated
> metrics. The churn classifier publishes its held-out ROC-AUC; the
> forecaster must beat a naive baseline in a rolling-origin backtest before
> it earns a place on the dashboard; null statistical findings stay on the
> board alongside significant ones.

---

## What's inside

| Capability | Method | Evidence |
|---|---|---|
| **Churn prediction** | Logistic regression / gradient boosting on labelled quarterly outcomes; features from quarter *t*, target from *t+1* (leakage-safe); GroupKFold CV by vendor | Test ROC-AUC **0.73** vs 1.7% base churn rate |
| **Performance forecasting** | Holt-Winters (damped trend + seasonality) with rolling-origin backtest | MAPE **0.67%** vs naive baseline **0.87%** |
| **Statistical insights** | Welch's t-test, chi-squared, one-way ANOVA, Pearson — all with effect sizes | e.g. escalations ↘ renewals (p<.001, V=0.15); spend does *not* buy ROI (r=0.007, n.s.) |
| **Cohort & retention analysis** | Initial-performance-quartile cohorts, survival matrices, lifecycle funnel | Early performance is a leading indicator of retention |
| **Vendor segmentation** | K-Means with standardised features; k chosen by silhouette, segments named as business personas | "Watch List" segment = high spend + low performance → renegotiation list |
| **Business impact** | Churn-probability-weighted contract value | Top-10 at-risk vendors quantified in $ exposure |
| **Analytical SQL** | 10 window-function/CTE queries (LAG, RANK, NTILE, rolling frames) | [`sql/analytical_queries.sql`](sql/analytical_queries.sql) — all verified against the bundled SQLite DB |

Plus: AI assistant (mock → local Ollama → Anthropic API fallback chain),
PDF/Excel/HTML report generation, alerting & scheduled-report automation,
JWT-authenticated Flask API, and PBKDF2-hashed login.

## Tech stack

Python · Streamlit · SQLite · scikit-learn · statsmodels · SciPy · Plotly · Pytest · Flask

## Project structure

```
├── app.py                      # Streamlit dashboard (entry point)
├── ai_integration.py           # AI features with safe local fallback
├── core_modules/
│   ├── analytics.py            # KPI aggregation
│   ├── churn_model.py          # Supervised churn classifier (leakage-safe panel)
│   ├── forecasting.py          # Backtested Holt-Winters forecasting
│   ├── stats_tests.py          # Hypothesis tests with effect sizes
│   ├── cohort_analysis.py      # Cohorts, retention, lifecycle funnel
│   ├── vendor_clustering.py    # K-Means segmentation (silhouette-selected k)
│   ├── database.py             # SQLite + CSV data access layer
│   ├── auth.py                 # PBKDF2 password hashing, JWT
│   └── config.py               # Env-driven configuration
├── ui_pages/                   # Dashboard pages (AI, risk, reports, analytics lab…)
├── enhancements/               # Report generator, anomaly detection, extras
├── api/                        # Flask REST API (JWT-protected)
├── sql/analytical_queries.sql  # Portfolio of analytical SQL
├── Data layer/                 # Demo CSVs (120 vendors × 24 months) + SQLite DB
├── automation/                 # Alert monitor & report scheduler scripts
├── web/                        # Static assets & templates
└── tests/                      # Pytest suite (incl. data-contract tests)
```

## Quick start

```bash
git clone https://github.com/Helloworld880/Temp-vendor-.git
cd Temp-vendor-
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Login with the demo credentials shown on the login screen
(configurable via `.env` — see `core_modules/config.py`).

### Run the tests

```bash
pytest -q          # 20 tests, incl. leakage checks and backtest assertions
```

### AI features (optional)

The AI workspace works out of the box in mock mode. For real LLM responses:

```bash
# Local (free): install Ollama, then
export AI_MODE=ollama

# Anthropic API:
pip install anthropic
export AI_MODE=real ANTHROPIC_API_KEY=sk-ant-...
```

## Methodology notes (read before trusting any number)

- **Churn is a rare event** (~1.7% of vendor-quarters). The model card
  reports ROC-AUC and PR-AUC against that base rate — never accuracy.
  Class-weighted probabilities are for *ranking* vendors, not calibrated
  likelihoods, and the UI says so.
- **No target leakage:** churn features come strictly from the quarter
  before the outcome; cross-validation folds are grouped by vendor so no
  vendor straddles train and validation.
- **Forecasts must beat naive:** the dashboard shows the model's
  rolling-origin backtest MAPE next to a last-value baseline. If the model
  ever loses, you'll see it.
- **Effect sizes over p-values:** every hypothesis test reports Cramér's V,
  Cohen's d, η² or r — and non-significant results are displayed, because
  "spend doesn't buy ROI" is a finding, not a failure.
- **Cohort design:** all demo contracts share a start date, so join-date
  cohorts would be degenerate; vendors are cohorted by initial performance
  quartile instead ("do strong starters stay longer?").

## Automation scripts

```bash
python automation/scripts/alert_monitor.py --dry-run     # threshold alerts
python automation/scripts/report_scheduler.py --run      # daily/weekly reports
```

## Author

**Yash Dudhani** — [github.com/Helloworld880](https://github.com/Helloworld880)

## License

MIT — see [LICENSE](LICENSE).
