from __future__ import annotations

import json
import unittest
from pathlib import Path

from custom_components.solar_of_things.api import _extract_energy_flow_values, _extract_latest_fields
from custom_components.solar_of_things.metrics import extract_device_metric_values, extract_history_metrics


class LiveCapturesValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.captures_dir = Path(__file__).resolve().parents[2] / "solar-of-things-next" / "captures"

    def test_parses_real_devices_json_capture(self) -> None:
        file_path = self.captures_dir / "devices.json"
        if not file_path.exists():
            self.skipTest(f"Capture file missing: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        devices = (payload.get("data") or {}).get("list") or []
        self.assertGreater(len(devices), 0)

        device_meta = devices[0]
        metrics = extract_device_metric_values(device_meta)

        self.assertTrue(metrics.get("online"))
        self.assertEqual(metrics.get("device_state"), "Normal")
        self.assertIsNotNone(metrics.get("monthly_pv_generated_kwh"))
        self.assertIsNotNone(metrics.get("yearly_pv_generated_kwh"))
        self.assertIsNotNone(metrics.get("total_pv_generated_kwh"))

    def test_parses_real_history_json_capture(self) -> None:
        file_path = self.captures_dir / "history.json"
        if not file_path.exists():
            self.skipTest(f"Capture file missing: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        metrics = extract_history_metrics(payload, year=2026)
        self.assertIn("monthly_pv_generated", metrics)
        self.assertIn("monthly_grid_import", metrics)
        self.assertIn("monthly_grid_export", metrics)
        self.assertIn("monthly_grid_net", metrics)

    def test_parses_real_realtime_json_capture(self) -> None:
        file_path = self.captures_dir / "realtime.json"
        if not file_path.exists():
            self.skipTest(f"Capture file missing: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        fields = _extract_latest_fields(payload)
        self.assertIn("batteryVoltage", fields)
        self.assertEqual(fields["batteryVoltage"], 27.2)


if __name__ == "__main__":
    unittest.main()
