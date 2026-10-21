"""
Interactive view of the Boeing event study. Pick any event window and see the
cumulative abnormal return, its significance, and the dollar impact.

Run: streamlit run app.py
"""
import numpy as np
import streamlit as st
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import event_study as es

st.set_page_config(page_title="Boeing Event Study", layout="centered")


@st.cache_resource
def analysis():
    return es.run_analysis()


r = analysis()
ev, sigma, dof = r["ev"], r["sigma"], r["dof"]

st.title("Boeing Event Study")
st.write("How much did Boeing's stock fall because of the January 5, 2024 Alaska Airlines Flight 1282 "
         "door plug incident, separate from normal market movement? Day 0 is Monday, January 8, 2024, "
         "the first trading day after the incident.")

a, b = st.slider("Event window (trading days relative to January 8, 2024)",
                 min_value=-es.PRE, max_value=es.POST, value=(0, 0))

# Same formulas as event_study.py: CAR t-stat = CAR / (sigma * sqrt(days))
w = ev[(ev["day"] >= a) & (ev["day"] <= b)]
n = len(w)
car = w["abnormal"].sum()
t = car / (sigma * np.sqrt(n))
p = 2 * stats.t.sf(abs(t), dof)
dollars = w["abnormal_value_change_usd"].sum()

day = lambda d: f"{d:%b} {d.day}"
label = f"[{a}]" if a == b else f"[{a}, {f'{b:+d}' if b else '0'}]"
dates = day(w.index[0]) if n == 1 else f"{day(w.index[0])} to {day(w.index[-1])}"
st.subheader(f"Window {label}: {dates}, {n} trading day{'s' if n > 1 else ''}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Abnormal return", es.pct(car))
c2.metric("t-stat", f"{t:.2f}")
c3.metric("p-value", es.pval(p))
c4.metric("Market value change", es.usd_bn(dollars).replace(" billion", "B"))
if p < es.ALPHA_LEVEL:
    st.write("Significant at the 5% level: a move this large is very unlikely to be normal day-to-day noise.")
else:
    st.write("Not significant at the 5% level: a move this size could be normal day-to-day noise.")
if b > 0 and a <= 0:
    st.caption("Day 0 is the headline result. Longer windows also pick up later news, including the FAA "
               "investigation and a January 16 analyst downgrade.")

# Daily abnormal returns, selected window shaded
sig = ev["p_value"] < es.ALPHA_LEVEL
fig, ax = plt.subplots(figsize=(9, 4))
ax.axvspan(a - 0.5, b + 0.5, color=es.PURPLE, alpha=0.08, lw=0)
ax.bar(ev["day"], ev["abnormal"] * 100, color=np.where(sig, es.RED, es.GRAY), width=0.7)
ax.axhline(0, color="black", lw=0.8)
ax.axvline(-0.5, color=es.PURPLE, ls=":", lw=1.4)
ax.set_xticks(ev["day"])
ax.set_xlabel("Trading days relative to Monday, January 8, 2024 (day 0)")
ax.set_ylabel("Abnormal return (%)")
ax.set_title("Daily abnormal return (actual minus but-for). Shaded area = selected window",
             fontsize=11, loc="left")
ax.legend(handles=[Patch(color=es.RED, label="Significant (p < 0.05)"),
                   Patch(color=es.GRAY, label="Not significant")], frameon=False, loc="lower right", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
st.pyplot(fig)

# Actual vs but-for price, from the January 5 close through the end of the window
if b >= 0:
    prices = r["prices"].loc[:w.index[-1]]
    end = prices.iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(prices.index, prices["but_for"], color=es.GRAY, lw=2.2, ls="--", label="But-for price (no incident)")
    ax.plot(prices.index, prices["actual"], color=es.PURPLE, lw=2.6, label="Actual price")
    ax.fill_between(prices.index, prices["actual"], prices["but_for"], color=es.RED, alpha=0.12, lw=0)
    ax.set_title(f"Actual vs. but-for price. Gap on {day(prices.index[-1])}: "
                 f"${end['gap_per_share']:.2f} per share", fontsize=11, loc="left")
    ax.set_ylabel("Price per share (USD)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xticks(prices.index)   # one tick per trading day, so short windows do not repeat dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    st.pyplot(fig)

st.subheader("Days in the window")
table = w[["day", "BA", "SPY", "expected", "abnormal", "t_stat", "p_value"]].copy()
table.index = [day(d) for d in table.index]
for col in ["BA", "SPY", "expected", "abnormal"]:
    table[col] = table[col].map(es.pct)
table["t_stat"] = table["t_stat"].map(lambda v: f"{v:.2f}")
table["p_value"] = table["p_value"].map(es.pval)
st.dataframe(table.rename(columns={"day": "Day", "BA": "Boeing return", "SPY": "Market (SPY)",
                                   "expected": "But-for return", "abnormal": "Abnormal return",
                                   "t_stat": "t-stat", "p_value": "p-value"}), width="stretch")

st.caption(f"Market model fit on {r['est'].index[0]:%B %d, %Y} to {r['est'].index[-1]:%B %d, %Y}: "
           f"beta = {r['beta']:.4f}, R-squared = {r['model'].rsquared:.3f}, residual SD = {es.pct(sigma)}. "
           f"Dollar impact uses {es.SHARES_OUT:,} shares outstanding. Educational analysis of public data, "
           "not a legal damages opinion.")
