# Boeing Event Study: Alaska Airlines Flight 1282 Door Plug Incident

## Question

How much shareholder value did Boeing lose because of the January 5, 2024 Alaska Airlines Flight 1282 door plug incident, separate from normal market movement?

## Answer

On Monday, January 8, 2024, the first trading day after the incident, Boeing stock returned **-8.03%** while a market model predicted **1.48%**. The difference, an abnormal return of **-9.52%**, is statistically significant (t = -6.13, p < 0.001). Applied to Boeing's market value, that is a change of **-$14.46 billion** in a single day.

By January 23, 2024 (day +10), Boeing closed at $211.50 against a but-for price of $259.60, a gap of **$48.10 per share**.

![Actual vs. but-for price](output/actual_vs_but_for_price.png)

### Cumulative abnormal return (CAR) by window

Day 0 is the headline result. The longer windows are sensitivity checks, chosen before looking at the results, and they mix in later news.

| Window | Dates | Abnormal return | t-stat | p-value | Change in market value |
|---|---|---|---|---|---|
| [0] | Jan 8 | -9.52% | -6.13 | < 0.001 | -$14.46 billion |
| [0, +1] | Jan 8 to Jan 9 | -10.84% | -4.94 | < 0.001 | -$16.30 billion |
| [0, +5] | Jan 8 to Jan 16 | -22.75% | -5.99 | < 0.001 | -$32.33 billion |
| [0, +10] | Jan 8 to Jan 23 | -19.67% | -3.82 | < 0.001 | -$28.68 billion |

The dollar column adds up each day's abnormal dollar change. The $48.10 per-share gap on the chart compounds returns forward from the January 5 close instead, so the two measures are close but not identical.

### Daily abnormal returns, day -5 to day +10

![Daily abnormal returns](output/daily_abnormal_returns.png)

No day before the incident is significant, which supports the model. After the incident, day 0 and day +5 (January 16) show large significant drops, and day +7 (January 18) shows a significant partial rebound.

## Method

This is a standard market model event study, the approach used in securities litigation and economic damages work. The design was fixed before looking at the results.

1. **Returns.** Daily simple returns for Boeing (BA) and the S&P 500 ETF (SPY), the market proxy.
2. **Event day (day 0).** Monday, January 8, 2024. The incident happened Friday evening, January 5, after the market closed, so January 8 is the first trading reaction.
3. **Estimation window.** 250 trading days, November 23, 2022 to November 21, 2023, ending 30 trading days before day 0 so that pre-event news does not leak into the model.
4. **Market model.** OLS regression `BA_return = alpha + beta * SPY_return + error`. Result: alpha = 0.000559, beta = 1.0003, R-squared = 0.257, residual SD = 1.55%. Full output in [`output/market_model_summary.txt`](output/market_model_summary.txt).
5. **But-for return.** `alpha + beta * SPY_return` on each event day: what Boeing would have returned given that day's market move if the incident had not happened.
6. **Abnormal return (AR).** Actual minus but-for. t-stat = AR / residual SD, with a two-sided p-value from the t-distribution (248 degrees of freedom).
7. **Cumulative abnormal return (CAR).** Sum of ARs over [0], [0, +1], [0, +5] and [0, +10]. t-stat = CAR / (residual SD x sqrt(number of days)).
8. **Dollar impact.** For each day, AR x prior day close x shares outstanding, summed over the window. Shares outstanding: 610,135,205 as of January 24, 2024 ([Boeing FY2023 Form 10-K cover page](https://www.sec.gov/Archives/edgar/data/12927/000001292724000010/ba-20231231.htm)).
9. **But-for price path.** Start from the January 5, 2024 close ($249.00) and compound actual and expected returns forward to show the per-share gap.

## How to run

Requires Python 3.11 or later.

```bash
pip install -r requirements.txt
python event_study.py
```

The script reads `data/ba.csv` and `data/spy.csv` and writes everything to `output/`:

| File | Contents |
|---|---|
| `actual_vs_but_for_price.png` | Actual vs. but-for price, gap shaded |
| `daily_abnormal_returns.png` | Daily ARs from day -5 to +10, significant days highlighted |
| `daily_abnormal_returns.csv` | Daily returns, expected return, AR, t-stat, p-value, dollar impact |
| `cumulative_abnormal_returns.csv` | CAR by window with t-stat, p-value, dollar impact |
| `market_model_summary.txt` | Full regression output |
| `key_results.txt` | Headline numbers, formatted exactly as quoted in this README and the memo |
| `Findings_Summary.pdf` | One-page memo for a non-technical reader |

### Interactive view

A small Streamlit page lets you pick any event window from day -5 to day +10 and see the cumulative abnormal return, t-stat, p-value, dollar impact, and charts for that window. It uses the same calculations as `event_study.py`.

```bash
streamlit run app.py
```

To refresh the data, go to the Nasdaq.com historical data page for [BA](https://www.nasdaq.com/market-activity/stocks/ba/historical) and [SPY](https://www.nasdaq.com/market-activity/etf/spy/historical), choose the 5Y range, click "Download historical data", and save the files as `data/ba.csv` and `data/spy.csv`.

## Limitations

- **Overlapping news.** The FAA grounded 171 Boeing 737 MAX 9 jets on Saturday, January 6, so day 0 reflects the incident and the grounding together. Later news, including the FAA investigation and added production oversight, overlaps the longer windows, so multi-day CARs mix several events. This is why day 0 is the headline.
- **Dividends.** SPY closing prices are not dividend-adjusted. The effect is negligible over these windows.
- **Single-factor model.** Only the broad market is controlled for. A fuller analysis could add an aerospace or industrials index as a second factor.
- **Not a damages opinion.** This is an educational analysis of public data. Shareholder damages in a real case depend on trading patterns, class periods, and legal theory.

## Data sources

- Daily prices for BA and SPY: [Nasdaq.com historical data](https://www.nasdaq.com/market-activity/stocks/ba/historical), 5-year range, retrieved October 21, 2026. Columns: `Date, Close/Last, Volume, Open, High, Low`.
- Shares outstanding: [Boeing FY2023 Form 10-K](https://www.sec.gov/Archives/edgar/data/12927/000001292724000010/ba-20231231.htm), cover page.
