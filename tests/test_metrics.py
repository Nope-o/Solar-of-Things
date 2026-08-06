from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "solar_of_things" / "metrics.py"
SPEC = importlib.util.spec_from_file_location("solar_of_things_metrics", MODULE_PATH)
metrics_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(metrics_module)
extract_device_metric_values = metrics_module.extract_device_metric_values
extract_history_metrics = metrics_module.extract_history_metrics


class MetricsParsingTests(unittest.TestCase):
    def test_extracts_live_generation_and_energy_metrics(self) -> None:
        device_meta = {
            "isOnline": True,
            "stateDict": "Normal",
            "loadPowerReadDirectly": {"value": 1.2},
            "todayPvGenerationReadDirectly": {"value": 3.4},
            "currentMonthPvGenerationReadDirectly": {"value": 65.6},
            "currentYearPvGenerationReadDirectly": {"value": 740.5},
            "totalPvGenerationReadDirectly": {"value": 754.8},
            "summaryProperty": {"totalGeneratedEnergy": 741.604},
        }

        values = extract_device_metric_values(device_meta)

        self.assertEqual(values["current_generation_power_kw"], 1.2)
        self.assertEqual(values["current_generation_power_w"], 1200.0)
        self.assertEqual(values["online"], True)
        self.assertEqual(values["device_state"], "Normal")
        self.assertEqual(values["today_pv_generated_kwh"], 3.4)
        self.assertEqual(values["monthly_pv_generated_kwh"], 65.6)
        self.assertEqual(values["yearly_pv_generated_kwh"], 740.5)
        self.assertEqual(values["total_pv_generated_kwh"], 754.8)
        self.assertEqual(values["total_generated_energy_kwh"], 741.604)

    def test_extracts_best_effort_live_power_fallbacks(self) -> None:
        device_meta = {
            "pvInputPowerReadDirectly": {
                "key": "generationPower",
                "unit": "kW",
                "value": 0.5,
            },
            "loadPowerReadDirectly": {
                "key": "loadPower",
                "unit": "kW",
                "value": 0.133,
            },
            "gridPowerReadDirectly": {
                "key": "gridPower",
                "unit": "kW",
                "value": 0.161,
            },
            "batteryVoltageReadDirectly": {"value": 27.2},
            "batterySocReadDirectly": {"value": 74},
        }

        values = extract_device_metric_values(device_meta)

        self.assertEqual(values["pv_input_power_w"], 500.0)
        self.assertEqual(values["load_power_w"], 133.0)
        self.assertEqual(values["grid_power_w"], 161.0)
        self.assertEqual(values["battery_voltage_v"], 27.2)
        self.assertEqual(values["battery_soc_percent"], 74.0)

    def test_extracts_monthly_and_yearly_load_estimates_from_history(self) -> None:
        today = datetime(2026, 8, 6)
        today_key = f"{today.year:04d}-{today.month:02d}-{today.day:02d}"
        payload = {
            "data": {
                "properties": [
                    {
                        "property": {"key": "pvGeneratedEnergy"},
                        "timePoints": [
                            {"time": "2026-07", "value": 100.0},
                            {"time": "2026-08", "value": 50.0},
                        ],
                    },
                    {
                        "property": {"key": "buyElectricityQuantity"},
                        "timePoints": [
                            {"time": "2026-07", "value": 20.0},
                            {"time": "2026-08", "value": 10.0},
                            {"time": today_key, "value": 3.0},
                        ],
                    },
                    {
                        "property": {"key": "sellElectricityQuantity"},
                        "timePoints": [
                            {"time": "2026-07", "value": 5.0},
                            {"time": "2026-08", "value": 2.0},
                            {"time": today_key, "value": 1.0},
                        ],
                    },
                ]
            }
        }

        with patch.object(metrics_module, "datetime") as datetime_mock:
            datetime_mock.now.return_value = today
            values = extract_history_metrics(payload, year=2026)

        self.assertEqual(values["daily_grid_import"], 3.0)
        self.assertEqual(values["daily_grid_export"], 1.0)
        self.assertEqual(values["daily_grid_net"], 2.0)
        self.assertEqual(values["monthly_pv_generated"], 50.0)
        self.assertEqual(values["monthly_grid_import"], 10.0)
        self.assertEqual(values["monthly_grid_export"], 2.0)
        self.assertEqual(values["monthly_grid_net"], 8.0)
        self.assertEqual(values["monthly_energy_sold"], 2.0)
        self.assertEqual(values["monthly_load_estimate"], 58.0)
        self.assertEqual(values["yearly_pv_generated"], 150.0)
        self.assertEqual(values["yearly_grid_import"], 33.0)
        self.assertEqual(values["yearly_grid_export"], 8.0)
        self.assertEqual(values["yearly_grid_net"], 25.0)
        self.assertEqual(values["yearly_energy_sold"], 8.0)
        self.assertEqual(values["yearly_load_estimate"], 175.0)


if __name__ == "__main__":
    unittest.main()
