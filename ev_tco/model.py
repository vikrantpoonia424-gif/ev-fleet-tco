"""First-principles total-cost-of-ownership (TCO) model for fleet vehicles.

Every cost is built up from physical and commercial drivers (price, energy
use per km, energy tariff, maintenance per km, downtime) and levelised to a
single comparable number: rupees per kilometre over the vehicle's life.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from scipy.optimize import brentq


@dataclass(frozen=True)
class Vehicle:
    name: str
    powertrain: str               # "Petrol", "CNG" or "EV"
    price: float                  # on-road price, Rs
    resale_pct: float             # resale value at end of life, share of price
    life_years: int
    energy_per_km: float          # litres, kg or kWh per km
    maintenance_per_km: float     # Rs per km
    insurance_per_year: float     # Rs per year
    subsidy: float = 0.0          # upfront subsidy, Rs
    battery_cost: float = 0.0     # mid-life battery replacement, Rs
    battery_year: Optional[int] = None


@dataclass(frozen=True)
class EnergyOption:
    name: str
    price_per_unit: float         # Rs per litre / kg / kWh
    downtime_min_per_day: float = 0.0   # refuelling / charging time lost in shift
    capex_per_vehicle: float = 0.0      # charger share or similar, Rs
    vehicle_price_delta: float = 0.0    # e.g. battery-as-a-service lowers price
    includes_battery: bool = False      # swap model: no battery replacement


@dataclass(frozen=True)
class Operations:
    km_per_day: float
    days_per_year: int = 330
    discount_rate: float = 0.10
    downtime_cost_per_min: float = 4.0  # gross earnings lost per idle minute


def blended_energy(name: str, grid: EnergyOption, solar_lcoe: float,
                   solar_share: float) -> EnergyOption:
    """Depot charging partly covered by rooftop solar (net-metered)."""
    price = (1 - solar_share) * grid.price_per_unit + solar_share * solar_lcoe
    return replace(grid, name=name, price_per_unit=price)


def levelised_cost(v: Vehicle, e: EnergyOption, ops: Operations) -> dict:
    """Return Rs/km by cost bucket, levelised over the vehicle life."""
    r = ops.discount_rate
    km_year = ops.km_per_day * ops.days_per_year
    disc = [(1 + r) ** -t for t in range(1, v.life_years + 1)]
    npv_km = km_year * sum(disc)

    capex = v.price + e.vehicle_price_delta - v.subsidy + e.capex_per_vehicle
    resale = (v.price + e.vehicle_price_delta) * v.resale_pct
    capital = capex - resale * disc[-1]
    if v.battery_year and v.battery_cost and not e.includes_battery:
        if v.battery_year <= v.life_years:
            capital += v.battery_cost * disc[v.battery_year - 1]

    annuity = sum(disc)
    buckets = {
        "capital": capital,
        "energy": km_year * v.energy_per_km * e.price_per_unit * annuity,
        "maintenance": km_year * v.maintenance_per_km * annuity,
        "insurance": v.insurance_per_year * annuity,
        "downtime": e.downtime_min_per_day * ops.days_per_year
        * ops.downtime_cost_per_min * annuity,
    }
    per_km = {k: val / npv_km for k, val in buckets.items()}
    per_km["total"] = sum(per_km.values())
    return per_km


def breakeven_km_per_day(a: tuple[Vehicle, EnergyOption],
                         b: tuple[Vehicle, EnergyOption], ops: Operations,
                         lo: float = 5, hi: float = 500) -> Optional[float]:
    """Daily km at which option `a` costs the same per km as option `b`."""
    def gap(km: float) -> float:
        o = replace(ops, km_per_day=km)
        return levelised_cost(*a, o)["total"] - levelised_cost(*b, o)["total"]

    g_lo, g_hi = gap(lo), gap(hi)
    if g_lo * g_hi > 0:
        return None
    return brentq(gap, lo, hi)


Mutator = Callable[[Vehicle, EnergyOption, Vehicle, EnergyOption, Operations, float],
                   tuple[Vehicle, EnergyOption, Vehicle, EnergyOption, Operations]]


def tornado(ev: tuple[Vehicle, EnergyOption], ice: tuple[Vehicle, EnergyOption],
            ops: Operations, drivers: dict[str, Mutator], swing: float = 0.2) -> list[dict]:
    """Sensitivity of the EV saving (Rs/km) to +/- `swing` in each driver."""
    base = levelised_cost(*ice, ops)["total"] - levelised_cost(*ev, ops)["total"]
    rows = []
    for label, mutate in drivers.items():
        out = []
        for f in (1 - swing, 1 + swing):
            ev_v, ev_e, ice_v, ice_e, o = mutate(*ev, *ice, ops, f)
            out.append(levelised_cost(ice_v, ice_e, o)["total"]
                       - levelised_cost(ev_v, ev_e, o)["total"])
        rows.append({"driver": label, "low": out[0], "high": out[1], "base": base,
                     "range": abs(out[1] - out[0])})
    return sorted(rows, key=lambda d: d["range"], reverse=True)
