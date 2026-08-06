from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


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

    def test_extracts_monthly_and_yearly_load_estimates_from_history(self) -> None:
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
                        ],
                    },
                    {
                        "property": {"key": "sellElectricityQuantity"},
                        "timePoints": [
                            {"time": "2026-07", "value": 5.0},
                            {"time": "2026-08", "value": 2.0},
                        ],
                    },
                ]
            }
        }

        values = extract_history_metrics(payload, year=2026)

        self.assertEqual(values["monthly_pv_generated"], 50.0)
        self.assertEqual(values["monthly_grid_import"], 10.0)
        self.assertEqual(values["monthly_energy_sold"], 2.0)
        self.assertEqual(values["monthly_load_estimate"], 58.0)
        self.assertEqual(values["yearly_pv_generated"], 150.0)
        self.assertEqual(values["yearly_grid_import"], 30.0)
        self.assertEqual(values["yearly_energy_sold"], 7.0)
        self.assertEqual(values["yearly_load_estimate"], 173.0)


if __name__ == "__main__":
    unittest.main()
