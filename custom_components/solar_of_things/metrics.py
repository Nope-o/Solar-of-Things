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


def _extract_read_direct_metric(
    device_meta: dict[str, Any],
    field_names: tuple[str, ...],
    *,
    expected_keys: set[str] | None = None,
    top_level_keys: tuple[str, ...] = (),
) -> float | None:
    """Extract a numeric value from readDirectly payloads or top-level fallbacks."""
    for field_name in field_names:
        payload = device_meta.get(field_name)
        if not isinstance(payload, dict):
            continue

        nested_key = str(payload.get("key") or "")
        if expected_keys and nested_key and nested_key not in expected_keys:
            continue

        value = _extract_numeric(payload, "value")
        if value is None:
            continue

        if payload.get("unit") == "kW":
            value *= 1000.0
        return value

    for key in top_level_keys:
        value = _extract_numeric(device_meta, key)
        if value is not None:
            return value

    return None


def _get_month_value(values_by_month: dict[str, float], month_key: str) -> float | None:
    if not values_by_month:
        return None
    if month_key in values_by_month:
        return values_by_month[month_key]
    if month_key[-2:] in {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"}:
        return values_by_month.get(month_key[-2:])
    return None


def _get_time_value(values_by_time: dict[str, float], time_key: str) -> float | None:
    if not values_by_time:
        return None
    if time_key in values_by_time:
        return values_by_time[time_key]
    return None


def extract_history_metrics(history_payload: dict[str, Any] | None, *, year: int | None = None) -> dict[str, Any]:
    """Parse station-level monthly history for generation, buy, sell, and load estimates."""
    if not isinstance(history_payload, dict):
        return {}

    now = datetime.now()
    target_year = year or now.year
    current_month_key = f"{target_year}-{now.month:02d}"
    current_day_key = f"{target_year}-{now.month:02d}-{now.day:02d}"

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
    daily_buy = _get_time_value(bought_values, current_day_key)
    daily_sell = _get_time_value(sold_values, current_day_key)

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

    daily_grid_net = None
    if daily_buy is not None or daily_sell is not None:
        daily_grid_net = (daily_buy or 0.0) - (daily_sell or 0.0)

    monthly_grid_net = None
    if monthly_buy is not None or monthly_sell is not None:
        monthly_grid_net = (monthly_buy or 0.0) - (monthly_sell or 0.0)

    yearly_grid_net = None
    if yearly_buy is not None or yearly_sell is not None:
        yearly_grid_net = yearly_buy - yearly_sell

    return {
        "daily_grid_import": daily_buy,
        "daily_grid_export": daily_sell,
        "daily_grid_net": daily_grid_net,
        "monthly_pv_generated": monthly_generation,
        "monthly_grid_import": monthly_buy,
        "monthly_grid_export": monthly_sell,
        "monthly_grid_net": monthly_grid_net,
        "monthly_energy_sold": monthly_sell,
        "monthly_load_estimate": monthly_load,
        "yearly_pv_generated": yearly_generation,
        "yearly_grid_import": yearly_buy,
        "yearly_grid_export": yearly_sell,
        "yearly_grid_net": yearly_grid_net,
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

    metrics["pv_input_power_w"] = _extract_read_direct_metric(
        device_meta,
        (
            "pvInputPowerReadDirectly",
            "generationPowerReadDirectly",
            "loadPowerReadDirectly",
        ),
        expected_keys={"pvInputPower", "generationPower"},
    )
    if metrics["pv_input_power_w"] is None:
        metrics["pv_input_power_w"] = metrics.get("current_generation_power_w")

    metrics["load_power_w"] = _extract_read_direct_metric(
        device_meta,
        ("loadPowerReadDirectly", "homeLoadPowerReadDirectly"),
        expected_keys={"loadPower", "homeLoadPower", "loadActivePower"},
        top_level_keys=("loadPower",),
    )

    metrics["grid_power_w"] = _extract_read_direct_metric(
        device_meta,
        ("gridPowerReadDirectly", "powerGridReadDirectly"),
        expected_keys={"gridPower", "powerGrid"},
        top_level_keys=("gridPower", "powerGrid"),
    )

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

    # Battery probes (best-effort): some devices expose battery SOC or voltage
    # in readDirectly properties or in top-level keys; try common names.
    metrics["battery_soc_percent"] = None
    battery_soc_candidates = (
        device_meta.get("batterySocReadDirectly"),
        device_meta.get("batterySOC"),
        device_meta.get("batteryStateOfCharge"),
    )
    for cand in battery_soc_candidates:
        if isinstance(cand, dict):
            soc = _extract_numeric(cand, "value")
            if soc is not None:
                metrics["battery_soc_percent"] = soc
                break
        else:
            v = _extract_numeric(device_meta, "batterySOC")
            if v is not None:
                metrics["battery_soc_percent"] = v
                break

    # Battery voltage: prefer readDirectly properties, fallback to top-level keys
    metrics["battery_voltage_v"] = None
    bv = _extract_numeric(device_meta.get("batteryVoltageReadDirectly"), "value")
    if bv is None:
        bv = _extract_numeric(device_meta, "batteryVoltage")
    if bv is not None:
        metrics["battery_voltage_v"] = bv

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
