from __future__ import annotations

from datetime import datetime
from typing import Any


def _extract_numeric(container: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(container, dict):
        return None
    value = container.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_month_value(values_by_month: dict[str, float], month_key: str) -> float | None:
    if not values_by_month:
        return None
    if month_key in values_by_month:
        return values_by_month[month_key]
    if month_key[-2:] in {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"}:
        return values_by_month.get(month_key[-2:])
    return None


def extract_history_metrics(history_payload: dict[str, Any] | None, *, year: int | None = None) -> dict[str, Any]:
    """Parse station-level monthly history for generation, buy, sell, and load estimates."""
    if not isinstance(history_payload, dict):
        return {}

    now = datetime.now()
    target_year = year or now.year
    current_month_key = f"{target_year}-{now.month:02d}"

    data = history_payload.get("data") or {}
    properties = data.get("properties") or []
    property_map: dict[str, dict[str, float]] = {}

    for entry in properties if isinstance(properties, list) else []:
        property_meta = entry.get("property") or {}
        key = property_meta.get("key") or property_meta.get("name") or ""
        if not key:
            continue
        values_by_month: dict[str, float] = {}
        for point in entry.get("timePoints") or []:
            if not isinstance(point, dict):
                continue
            time_value = point.get("time")
            if not isinstance(time_value, str):
                continue
            numeric_value = point.get("value")
            try:
                values_by_month[time_value] = float(numeric_value)
            except (TypeError, ValueError):
                continue
        property_map[key] = values_by_month

    generation_values = property_map.get("pvGeneratedEnergy") or {}
    bought_values = property_map.get("buyElectricityQuantity") or {}
    sold_values = property_map.get("sellElectricityQuantity") or {}

    monthly_generation = _get_month_value(generation_values, current_month_key)
    monthly_buy = _get_month_value(bought_values, current_month_key)
    monthly_sell = _get_month_value(sold_values, current_month_key)

    yearly_generation = sum(
        value for key, value in generation_values.items() if str(key).startswith(str(target_year))
    )
    yearly_buy = sum(
        value for key, value in bought_values.items() if str(key).startswith(str(target_year))
    )
    yearly_sell = sum(
        value for key, value in sold_values.items() if str(key).startswith(str(target_year))
    )

    monthly_load = None
    if monthly_generation is not None or monthly_buy is not None or monthly_sell is not None:
        monthly_load = (monthly_generation or 0.0) + (monthly_buy or 0.0) - (monthly_sell or 0.0)

    yearly_load = None
    if yearly_generation is not None or yearly_buy is not None or yearly_sell is not None:
        yearly_load = yearly_generation + yearly_buy - yearly_sell

    return {
        "monthly_pv_generated": monthly_generation,
        "monthly_grid_import": monthly_buy,
        "monthly_energy_sold": monthly_sell,
        "monthly_load_estimate": monthly_load,
        "yearly_pv_generated": yearly_generation,
        "yearly_grid_import": yearly_buy,
        "yearly_energy_sold": yearly_sell,
        "yearly_load_estimate": yearly_load,
    }


def extract_device_metric_values(device_meta: dict[str, Any] | None) -> dict[str, Any]:
    """Extract values that are available from the device-list payload."""
    if not isinstance(device_meta, dict):
        return {}

    metrics: dict[str, Any] = {}

    power_kw = None

    power_payload = device_meta.get("loadPowerReadDirectly")
    if isinstance(power_payload, dict):
        power_kw = _extract_numeric(power_payload, "value")

    if power_kw is None:
        power_kw = _extract_numeric(device_meta, "producingPower")

    if power_kw is None:
        power_kw = _extract_numeric(device_meta, "nonNullableProducingPower")

    if power_kw is not None:
        metrics["current_generation_power_kw"] = power_kw
        metrics["current_generation_power_w"] = power_kw * 1000.0

    metrics["today_pv_generated_kwh"] = _extract_numeric(
        device_meta.get("todayPvGenerationReadDirectly"),
        "value",
    )
    metrics["monthly_pv_generated_kwh"] = _extract_numeric(
        device_meta.get("currentMonthPvGenerationReadDirectly"),
        "value",
    )
    metrics["yearly_pv_generated_kwh"] = _extract_numeric(
        device_meta.get("currentYearPvGenerationReadDirectly"),
        "value",
    )
    metrics["total_pv_generated_kwh"] = _extract_numeric(
        device_meta.get("totalPvGenerationReadDirectly"),
        "value",
    )

    summary_payload = device_meta.get("summaryProperty")
    if isinstance(summary_payload, dict):
        total_generated = summary_payload.get("totalGeneratedEnergy")
        try:
            metrics["total_generated_energy_kwh"] = float(total_generated)
        except (TypeError, ValueError):
            metrics["total_generated_energy_kwh"] = None

    metrics["online"] = bool(device_meta.get("isOnline"))
    metrics["device_state"] = device_meta.get("stateDict") or device_meta.get("state")

    return metrics
