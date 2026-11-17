"""Run every scenario and write tables + charts to ./outputs."""
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ev_tco import breakeven_km_per_day, levelised_cost, tornado
from ev_tco.scenarios import (BIKE_OPS, BIKE_OPTIONS, CAB_OPS, CAB_OPTIONS, CNG_CAB, CNG,
                              DEPOT_SOLAR, EV_CAB, SENSITIVITY_DRIVERS)

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
BUCKETS = ["capital", "energy", "maintenance", "insurance", "downtime"]
FLEET = 100


def table(options, ops, segment):
    rows = []
    for v, e in options:
        c = levelised_cost(v, e, ops)
        rows.append({"segment": segment, "option": f"{v.name} | {e.name}",
                     **{k: round(c[k], 2) for k in BUCKETS + ["total"]}})
    return pd.DataFrame(rows)


def stacked_bar(df, title, path):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    left = np.zeros(len(df))
    for b in BUCKETS:
        ax.barh(df["option"], df[b], left=left, label=b)
        left += df[b].to_numpy()
    for i, t in enumerate(df["total"]):
        ax.text(t + 0.1, i, f"Rs {t:.2f}/km", va="center", fontsize=9)
    ax.set_xlabel("Levelised cost (Rs per km)")
    ax.set_title(title)
    ax.invert_yaxis()
    ax.legend(ncol=5, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.32))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    cab = table(CAB_OPTIONS, CAB_OPS, "4W cab, 180 km/day")
    bike = table(BIKE_OPTIONS, BIKE_OPS, "2W, 100 km/day")
    pd.concat([cab, bike]).to_csv(OUT / "cost_per_km.csv", index=False)
    stacked_bar(cab, "Ride-hailing cab: cost per km by energy strategy", OUT / "cab_cost_per_km.png")
    stacked_bar(bike, "2-wheeler fleet: cost per km by energy strategy", OUT / "bike_cost_per_km.png")

    # Breakeven: when does an EV beat the cheapest ICE cab?
    ev, ice = (EV_CAB, DEPOT_SOLAR), (CNG_CAB, CNG)
    be = breakeven_km_per_day(ev, ice, CAB_OPS)
    kms = np.arange(40, 301, 10)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for v, e in CAB_OPTIONS:
        ax.plot(kms, [levelised_cost(v, e, replace(CAB_OPS, km_per_day=k))["total"] for k in kms],
                label=f"{v.name} | {e.name}")
    if be:
        ax.axvline(be, ls="--", c="grey")
        ax.text(be + 3, ax.get_ylim()[1] * 0.9, f"EV+solar beats CNG\nabove {be:.0f} km/day", fontsize=9)
    ax.set_xlabel("Daily km per vehicle")
    ax.set_ylabel("Rs per km")
    ax.set_title("Utilisation decides the winner")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "cab_breakeven.png", dpi=150)
    plt.close(fig)

    # Sensitivity
    tor = pd.DataFrame(tornado(ev, ice, CAB_OPS, SENSITIVITY_DRIVERS))
    tor.to_csv(OUT / "sensitivity.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    base = tor["base"].iloc[0]
    for i, r in tor.iterrows():
        ax.barh(r["driver"], r["high"] - base, left=base, color="tab:green")
        ax.barh(r["driver"], r["low"] - base, left=base, color="tab:red")
    ax.axvline(base, c="black")
    ax.invert_yaxis()
    ax.set_xlabel("EV saving vs CNG (Rs per km); green = driver +20%, red = driver -20%")
    ax.set_title("What moves the EV business case")
    fig.tight_layout()
    fig.savefig(OUT / "sensitivity_tornado.png", dpi=150)
    plt.close(fig)

    # Summary
    cng = cab.loc[cab.option.str.startswith("CNG"), "total"].item()
    best = cab.loc[cab.total.idxmin()]
    dc = cab.loc[cab.option.str.contains("Public DC"), "total"].item()
    saving_km = cng - best.total
    annual = saving_km * CAB_OPS.km_per_day * CAB_OPS.days_per_year * FLEET
    bike_best = bike.loc[bike.total.idxmin()]
    bike_petrol = bike.loc[bike.option.str.startswith("Petrol"), "total"].item()
    lines = [
        "# Results",
        "",
        cab.to_markdown(index=False), "",
        bike.to_markdown(index=False), "",
        f"- Cheapest cab option: **{best.option}** at Rs {best.total:.2f}/km "
        f"vs CNG at Rs {cng:.2f}/km ({saving_km / cng:.0%} lower).",
        f"- For a {FLEET}-cab fleet that is ~Rs {annual / 1e5:.0f} lakh saved per year.",
        f"- Relying on public DC fast charging costs Rs {dc:.2f}/km, "
        f"{(dc - best.total) / best.total:.0%} more than depot + solar.",
        f"- Breakeven: EV + solar beats CNG above **{be:.0f} km/day**." if be else "- No breakeven in range.",
        f"- 2W: cheapest is **{bike_best.option}** at Rs {bike_best.total:.2f}/km "
        f"vs petrol at Rs {bike_petrol:.2f}/km.",
        f"- Biggest swing factor: **{tor.driver.iloc[0]}** (+/-20% moves the saving by "
        f"Rs {tor.range.iloc[0]:.2f}/km).",
    ]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
