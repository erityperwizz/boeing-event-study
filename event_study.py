"""
Boeing Event Study: Alaska Airlines Flight 1282 Door Plug Incident (January 5, 2024)

Question: How much of Boeing's stock decline after the incident was caused by the
event itself, rather than by normal market movement?

Method: market model event study, the standard approach in securities litigation.
  1. Estimate how Boeing normally moves with the market (OLS: BA return on SPY return)
     over a clean 250 trading day window that ends well before the event.
  2. Use that model to predict the "but-for" return on each day after the event,
     meaning what Boeing would have done if the incident had not happened.
  3. Abnormal return = actual return minus but-for return. Test whether it is
     statistically significant and convert it to a dollar loss in market value.

Run: python event_study.py   (reads data/ba.csv and data/spy.csv, writes output/)
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

ROOT = Path(__file__).parent
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)

EVENT_DAY = pd.Timestamp("2024-01-08")   # first trading day after the Friday evening incident
EST_LEN, GAP = 250, 30                    # estimation window length and gap before the event
PRE, POST = 5, 10                         # daily abnormal returns shown from day -5 to day +10
WINDOWS = [(0, 0), (0, 1), (0, 5), (0, 10)]
SHARES_OUT = 610_135_205                  # Boeing FY2023 10-K cover page, as of January 24, 2024
ALPHA_LEVEL = 0.05

PURPLE, GRAY, RED, INK = "#5B2A86", "#8A8A8A", "#B03A2E", "#222222"


# Number formats shared by the console, the key results file and the PDF, so every
# number quoted anywhere is the same string the script printed.
def pct(x):
    return f"{x:.2%}"


def usd_bn(x):
    return f"{'-' if x < 0 else ''}${abs(x) / 1e9:,.2f} billion"


def pval(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def load_prices(path):
    """Read a daily price CSV from Nasdaq.com and return a Close series, oldest first."""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    close_col = next(c for c in ["Close/Last", "Adj Close", "Close"] if c in df.columns)
    s = df[close_col].astype(str).str.replace(r"[$,]", "", regex=True).astype(float)
    s.index = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    return s.sort_index()


def run_analysis():
    px = pd.concat([load_prices(DATA / "ba.csv").rename("BA"),
                    load_prices(DATA / "spy.csv").rename("SPY")], axis=1).dropna()
    ret = px.pct_change().dropna()

    if EVENT_DAY not in ret.index:
        sys.exit(f"{EVENT_DAY.date()} is missing from the data. Check the date range.")
    e = ret.index.get_loc(EVENT_DAY)
    if e - GAP - EST_LEN < 0 or e + POST >= len(ret):
        sys.exit("Not enough history around the event. Download the 5Y range from Nasdaq.com.")
    est = ret.iloc[e - GAP - EST_LEN: e - GAP]

    # 1. Market model, fit only on the estimation window
    model = sm.OLS(est["BA"], sm.add_constant(est["SPY"])).fit()
    alpha, beta = model.params["const"], model.params["SPY"]
    sigma = np.sqrt(model.scale)          # residual standard deviation
    dof = int(model.df_resid)

    # 2. But-for (expected) and abnormal returns, day -5 to day +10
    ev = ret.iloc[e - PRE: e + POST + 1].copy()
    ev.insert(0, "day", range(-PRE, POST + 1))
    ev["expected"] = alpha + beta * ev["SPY"]
    ev["abnormal"] = ev["BA"] - ev["expected"]
    ev["t_stat"] = ev["abnormal"] / sigma
    ev["p_value"] = 2 * stats.t.sf(ev["t_stat"].abs(), dof)
    ev["prior_close"] = px["BA"].shift(1).reindex(ev.index)
    ev["abnormal_value_change_usd"] = ev["abnormal"] * ev["prior_close"] * SHARES_OUT
    ev.index.name = "date"

    # 3. Cumulative abnormal returns. CAR t-stat = CAR / (sigma * sqrt(days))
    rows = []
    for a, b in WINDOWS:
        w = ev[(ev["day"] >= a) & (ev["day"] <= b)]
        n = len(w)
        car = w["abnormal"].sum()
        t = car / (sigma * np.sqrt(n))
        rows.append({
            "window": f"[{a}, +{b}]" if b else "[0]",
            "start": w.index[0].date(), "end": w.index[-1].date(),
            "trading_days": n,
            "actual_return": (1 + w["BA"]).prod() - 1,
            "but_for_return": (1 + w["expected"]).prod() - 1,
            "CAR": car, "t_stat": t,
            "p_value": 2 * stats.t.sf(abs(t), dof),
            "abnormal_value_change_usd": w["abnormal_value_change_usd"].sum(),
        })
    car_tbl = pd.DataFrame(rows)

    # 4. Actual vs but-for price path, compounding forward from the January 5 close
    post = ev[ev["day"] >= 0]
    p0_date = px.index[px.index.get_loc(EVENT_DAY) - 1]
    p0 = px.loc[p0_date, "BA"]
    prices = pd.DataFrame({
        "actual": np.r_[p0, p0 * (1 + post["BA"]).cumprod()],
        "but_for": np.r_[p0, p0 * (1 + post["expected"]).cumprod()],
    }, index=[p0_date, *post.index])
    prices["gap_per_share"] = prices["but_for"] - prices["actual"]

    return dict(px=px, est=est, model=model, alpha=alpha, beta=beta, sigma=sigma,
                dof=dof, ev=ev, car_tbl=car_tbl, prices=prices, p0=p0, p0_date=p0_date)


def save_tables(r):
    # Round returns for readability, but keep p-values exact (tiny ones would round to zero)
    for df, name, idx in [(r["ev"], "daily_abnormal_returns.csv", True),
                          (r["car_tbl"], "cumulative_abnormal_returns.csv", False)]:
        df.round(6).assign(p_value=df["p_value"]).to_csv(OUT / name, index=idx)
    est, m = r["est"], r["model"]
    with open(OUT / "market_model_summary.txt", "w") as f:
        f.write(f"Estimation window: {est.index[0].date()} to {est.index[-1].date()} "
                f"({len(est)} trading days, ending {GAP} trading days before {EVENT_DAY.date()})\n")
        f.write(f"alpha = {r['alpha']:.6f}, beta = {r['beta']:.4f}, "
                f"R-squared = {m.rsquared:.3f}, residual SD = {r['sigma']:.4%}\n\n")
        f.write(str(m.summary()))


def key_results(r):
    """Headline numbers as formatted strings. The README and PDF quote these exactly."""
    d0 = r["car_tbl"].iloc[0]
    end = r["prices"].iloc[-1]
    return {
        "estimation_window": f"{r['est'].index[0]:%B %d, %Y} to {r['est'].index[-1]:%B %d, %Y}",
        "alpha": f"{r['alpha']:.6f}",
        "beta": f"{r['beta']:.4f}",
        "r_squared": f"{r['model'].rsquared:.3f}",
        "residual_sd": pct(r["sigma"]),
        "day0_actual_return": pct(d0["actual_return"]),
        "day0_but_for_return": pct(d0["but_for_return"]),
        "day0_abnormal_return": pct(d0["CAR"]),
        "day0_t_stat": f"{d0['t_stat']:.2f}",
        "day0_p_value": pval(d0["p_value"]),
        "day0_value_change": usd_bn(d0["abnormal_value_change_usd"]),
        "jan5_close": f"${r['p0']:.2f}",
        "path_end_date": f"{r['prices'].index[-1]:%B %d, %Y}",
        "path_end_actual": f"${end['actual']:.2f}",
        "path_end_but_for": f"${end['but_for']:.2f}",
        "path_end_gap_per_share": f"${end['gap_per_share']:.2f}",
    }


def chart_price(r):
    prices = r["prices"]
    end = prices.iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(prices.index, prices["but_for"], color=GRAY, lw=2.2, ls="--", label="But-for price (no incident)")
    ax.plot(prices.index, prices["actual"], color=PURPLE, lw=2.6, label="Actual price")
    ax.fill_between(prices.index, prices["actual"], prices["but_for"], color=RED, alpha=0.12, lw=0)
    ax.annotate(f"Gap: ${end['gap_per_share']:.2f} per share",
                xy=(prices.index[-1], (end["actual"] + end["but_for"]) / 2),
                xytext=(-8, 0), textcoords="offset points", ha="right", va="center",
                fontsize=10.5, color=RED, fontweight="bold")
    ax.annotate(f"Jan 5 close ${r['p0']:.2f}", xy=(prices.index[0], r["p0"]), xytext=(8, -16),
                textcoords="offset points", fontsize=9, color=INK)
    ax.set_title("Boeing (BA): actual vs. but-for share price after the January 5, 2024 door plug incident",
                 fontsize=11, loc="left", color=INK)
    ax.set_ylabel("Price per share (USD)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="lower left")
    fig.text(0.01, 0.01, "Source: Nasdaq.com daily closes. But-for path = Jan 5 close compounded by "
             "market model expected returns.", fontsize=7.5, color=GRAY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "actual_vs_but_for_price.png", dpi=200)
    plt.close(fig)


def chart_daily(r):
    ev = r["ev"]
    sig = ev["p_value"] < ALPHA_LEVEL
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(ev["day"], ev["abnormal"] * 100, color=np.where(sig, RED, GRAY), width=0.7)
    for d, ar, s in zip(ev["day"], ev["abnormal"] * 100, sig):
        if s:
            ax.text(d, ar + (0.4 if ar > 0 else -0.4), f"{ar:.1f}%", ha="center",
                    va="bottom" if ar > 0 else "top", fontsize=8.5, color=RED)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(-0.5, color=PURPLE, ls=":", lw=1.4)
    lo = (ev["abnormal"].min() * 100) * 1.25
    ax.set_ylim(lo, max(ev["abnormal"].max() * 100 * 1.6, 2))
    ax.text(-0.6, ax.get_ylim()[1] * 0.95, "Incident (Fri Jan 5,\nafter close)", color=PURPLE,
            fontsize=8.5, ha="right", va="top")
    ax.set_xticks(ev["day"])
    ax.set_title("Boeing daily abnormal return (actual minus but-for), day -5 to day +10",
                 fontsize=11, loc="left", color=INK)
    ax.set_xlabel("Trading days relative to Monday, January 8, 2024 (day 0)")
    ax.set_ylabel("Abnormal return (%)")
    ax.legend(handles=[Patch(color=RED, label="Significant (p < 0.05)"), Patch(color=GRAY, label="Not significant")],
              frameon=False, loc="lower right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "daily_abnormal_returns.png", dpi=200)
    plt.close(fig)


def findings_pdf(r, k):
    """One page memo for a non-technical reader, built from the computed results."""
    W, H = 8.5, 11
    fig = plt.figure(figsize=(W, H))
    left, width = 0.75, 7.0
    y = [H - 0.7]                          # current baseline, in inches from the bottom

    renderer = fig.canvas.get_renderer()

    def wrap(s, size, weight):
        """Greedy line wrap using the rendered text width, so lines never run past the margin."""
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}".strip()
            t = fig.text(0, 0, trial, fontsize=size, fontweight=weight)
            too_wide = t.get_window_extent(renderer).width / fig.dpi > width
            t.remove()
            if too_wide and cur:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + [cur]

    def text(s, size=9.5, weight="normal", color=INK, gap=0.06):
        for line in wrap(s, size, weight):
            fig.text(left / W, y[0] / H, line, fontsize=size, fontweight=weight, color=color, va="top")
            y[0] -= size / 72 * 1.35
        y[0] -= gap

    def heading(s):
        y[0] -= 0.06
        text(s.upper(), size=8.5, weight="bold", color=PURPLE, gap=0.02)

    text("MEMORANDUM", size=15, weight="bold", gap=0.04)
    text("From: Erica Mathias    |    Re: Boeing stock price reaction to the Alaska Airlines Flight 1282 "
         "door plug incident", size=8.5, color=GRAY, gap=0.06)
    fig.add_artist(plt.Line2D([left / W, (left + width) / W], [y[0] / H] * 2, color=PURPLE, lw=1.2))
    y[0] -= 0.12

    heading("Question")
    text("How much shareholder value did Boeing lose because of the January 5, 2024 Alaska Airlines "
         "door plug incident, separate from normal market movement?")

    heading("Answer")
    text(f"On Monday, January 8, 2024, the first trading day after the incident, Boeing stock returned "
         f"{k['day0_actual_return']} while the market model predicted {k['day0_but_for_return']}. The "
         f"difference, an abnormal return of {k['day0_abnormal_return']}, is statistically significant "
         f"(t = {k['day0_t_stat']}, p {k['day0_p_value']}). Applied to Boeing's market value, this is a "
         f"change of {k['day0_value_change']} in a single day. By {k['path_end_date']}, the actual price was "
         f"{k['path_end_actual']} against a but-for price of {k['path_end_but_for']}, a gap of "
         f"{k['path_end_gap_per_share']} per share.", gap=0.1)

    img = plt.imread(OUT / "actual_vs_but_for_price.png")
    ih = width * img.shape[0] / img.shape[1] * 0.86
    iw = width * 0.86
    ax = fig.add_axes([(left + (width - iw) / 2) / W, (y[0] - ih) / H, iw / W, ih / H])
    ax.imshow(img)
    ax.axis("off")
    y[0] -= ih + 0.12

    heading("Cumulative abnormal return by event window")
    cols = ["Window", "Dates", "Abnormal return", "t-stat", "p-value", "Change in market value"]
    xs = [0, 0.95, 2.6, 3.85, 4.75, 5.75]
    for x, c in zip(xs, cols):
        fig.text((left + x) / W, y[0] / H, c, fontsize=8.5, fontweight="bold", color=INK, va="top")
    y[0] -= 0.2
    for _, row in r["car_tbl"].iterrows():
        day = lambda d: f"{d:%b} {d.day}"
        dates = day(row["start"]) if row["start"] == row["end"] else f"{day(row['start'])} to {day(row['end'])}"
        vals = [row["window"], dates, pct(row["CAR"]), f"{row['t_stat']:.2f}",
                pval(row["p_value"]), usd_bn(row["abnormal_value_change_usd"])]
        for x, v in zip(xs, vals):
            fig.text((left + x) / W, y[0] / H, v, fontsize=8.5, color=INK, va="top")
        y[0] -= 0.18
    text("Day 0 is the headline result. Longer windows are shown as sensitivity checks and mix in later news.",
         size=8, color=GRAY, gap=0.06)

    heading("Method")
    text(f"I estimated how Boeing normally moves with the overall market by regressing its daily return on "
         f"the S&P 500 ETF (SPY) over 250 trading days ({k['estimation_window']}), ending 30 trading days "
         f"before the event so pre-event news does not distort the model (beta = {k['beta']}, "
         f"R-squared = {k['r_squared']}). That model gives a but-for return for each day after the incident: "
         f"what Boeing would have returned given the market's move if the incident had not happened. The "
         f"abnormal return is the actual return minus the but-for return, tested against the model's normal "
         f"daily noise ({k['residual_sd']}). The dollar figure multiplies each day's abnormal return by the "
         f"prior close and 610,135,205 shares outstanding (FY2023 Form 10-K).")

    heading("Limitations")
    for s in [
        "The FAA grounded 171 MAX 9 jets on Saturday, January 6, so day 0 reflects the incident and the "
        "grounding together. Later news (the FAA investigation and production oversight in the following "
        "days) overlaps the longer windows, so multi-day results mix several events.",
        "A single-factor market model. A fuller analysis could add an aerospace or industrials index.",
        "SPY closing prices are not dividend-adjusted. The effect is negligible over these windows.",
        "This is an educational analysis of public data, not a legal damages opinion. Shareholder damages "
        "in a real case depend on trading patterns, class periods, and legal theory.",
    ]:
        text("- " + s, size=8.5, gap=0.02)

    fig.savefig(OUT / "Findings_Summary.pdf")
    plt.close(fig)


def main():
    r = run_analysis()
    save_tables(r)
    k = key_results(r)
    with open(OUT / "key_results.txt", "w") as f:
        f.writelines(f"{name}: {v}\n" for name, v in k.items())
    chart_price(r)
    chart_daily(r)
    findings_pdf(r, k)

    pd.set_option("display.width", 160)
    print(open(OUT / "market_model_summary.txt").read().split("\n\n")[0], "\n")
    print(r["car_tbl"].to_string(index=False), "\n")
    print(r["ev"][["day", "BA", "SPY", "expected", "abnormal", "t_stat", "p_value"]].round(4).to_string(), "\n")
    print(open(OUT / "key_results.txt").read())


if __name__ == "__main__":
    main()
