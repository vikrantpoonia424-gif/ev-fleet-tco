"""Illustrative 2026 India assumptions. Edit these to match real quotes."""
from dataclasses import replace

from .model import EnergyOption, Operations, Vehicle, blended_energy

# ---------- 4-wheeler ride-hailing cab ----------
CAB_OPS = Operations(km_per_day=180, downtime_cost_per_min=4.0)

PETROL_CAB = Vehicle("Petrol sedan", "Petrol", price=750_000, resale_pct=0.30,
                     life_years=5, energy_per_km=1 / 15, maintenance_per_km=1.0,
                     insurance_per_year=35_000)
CNG_CAB = Vehicle("CNG sedan", "CNG", price=850_000, resale_pct=0.30,
                  life_years=5, energy_per_km=1 / 25, maintenance_per_km=1.2,
                  insurance_per_year=35_000)
EV_CAB = Vehicle("EV sedan", "EV", price=1_350_000, resale_pct=0.25,
                 life_years=5, energy_per_km=0.14, maintenance_per_km=0.5,
                 insurance_per_year=45_000)

PETROL = EnergyOption("Petrol pump", 105, downtime_min_per_day=5)
CNG = EnergyOption("CNG station", 90, downtime_min_per_day=20)
DEPOT_AC = EnergyOption("Depot AC (overnight)", 9, capex_per_vehicle=40_000)
PUBLIC_DC = EnergyOption("Public DC fast", 22, downtime_min_per_day=45)
DEPOT_SOLAR = blended_energy("Depot AC + 40% rooftop solar", DEPOT_AC,
                             solar_lcoe=3.5, solar_share=0.40)

CAB_OPTIONS = [
    (PETROL_CAB, PETROL), (CNG_CAB, CNG),
    (EV_CAB, PUBLIC_DC), (EV_CAB, DEPOT_AC), (EV_CAB, DEPOT_SOLAR),
]

# ---------- 2-wheeler delivery / bike-taxi ----------
BIKE_OPS = Operations(km_per_day=100, downtime_cost_per_min=2.0)

PETROL_2W = Vehicle("Petrol 2W", "Petrol", price=90_000, resale_pct=0.25,
                    life_years=4, energy_per_km=1 / 50, maintenance_per_km=0.6,
                    insurance_per_year=2_500)
EV_2W = Vehicle("EV 2W", "EV", price=120_000, subsidy=10_000, resale_pct=0.20,
                life_years=4, energy_per_km=0.03, maintenance_per_km=0.25,
                insurance_per_year=3_000, battery_cost=35_000, battery_year=3)

PETROL_2W_FUEL = EnergyOption("Petrol pump", 105, downtime_min_per_day=5)
HOME_CHARGE = EnergyOption("Home / depot charging", 8, capex_per_vehicle=3_000)
SWAP = EnergyOption("Battery swapping", 60, downtime_min_per_day=4,
                    vehicle_price_delta=-45_000, includes_battery=True)

BIKE_OPTIONS = [(PETROL_2W, PETROL_2W_FUEL), (EV_2W, HOME_CHARGE), (EV_2W, SWAP)]


# ---------- sensitivity drivers (EV option vs ICE option) ----------
def _scale_ev_energy(ev_v, ev_e, ice_v, ice_e, o, f):
    return ev_v, replace(ev_e, price_per_unit=ev_e.price_per_unit * f), ice_v, ice_e, o


def _scale_fuel(ev_v, ev_e, ice_v, ice_e, o, f):
    return ev_v, ev_e, ice_v, replace(ice_e, price_per_unit=ice_e.price_per_unit * f), o


def _scale_ev_price(ev_v, ev_e, ice_v, ice_e, o, f):
    return replace(ev_v, price=ev_v.price * f), ev_e, ice_v, ice_e, o


def _scale_km(ev_v, ev_e, ice_v, ice_e, o, f):
    return ev_v, ev_e, ice_v, ice_e, replace(o, km_per_day=o.km_per_day * f)


def _scale_rate(ev_v, ev_e, ice_v, ice_e, o, f):
    return ev_v, ev_e, ice_v, ice_e, replace(o, discount_rate=o.discount_rate * f)


def _scale_resale(ev_v, ev_e, ice_v, ice_e, o, f):
    return replace(ev_v, resale_pct=ev_v.resale_pct * f), ev_e, ice_v, ice_e, o


SENSITIVITY_DRIVERS = {
    "EV purchase price": _scale_ev_price,
    "Daily km driven": _scale_km,
    "ICE fuel price": _scale_fuel,
    "EV energy tariff": _scale_ev_energy,
    "EV resale value": _scale_resale,
    "Cost of capital": _scale_rate,
}
