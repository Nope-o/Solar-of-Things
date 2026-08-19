from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components"
DOMAIN_ROOT = PACKAGE_ROOT / "solar_of_things"

custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("custom_components", custom_components_pkg)

solar_pkg = types.ModuleType("custom_components.solar_of_things")
solar_pkg.__path__ = [str(DOMAIN_ROOT)]
sys.modules.setdefault("custom_components.solar_of_things", solar_pkg)

CONST_SPEC = importlib.util.spec_from_file_location(
    "custom_components.solar_of_things.const",
    DOMAIN_ROOT / "const.py",
)
const_module = importlib.util.module_from_spec(CONST_SPEC)
assert CONST_SPEC.loader is not None
sys.modules[CONST_SPEC.name] = const_module
CONST_SPEC.loader.exec_module(const_module)

API_SPEC = importlib.util.spec_from_file_location(
    "custom_components.solar_of_things.api",
    DOMAIN_ROOT / "api.py",
)
api_module = importlib.util.module_from_spec(API_SPEC)
assert API_SPEC.loader is not None
sys.modules[API_SPEC.name] = api_module
API_SPEC.loader.exec_module(api_module)

class ApiParsingTests(unittest.TestCase):
    def test_normalizes_settings_list(self) -> None:
        raw = [
            {"key": "outputSourcePrioritySetting", "value": 1},
            {"key": "batteryPowerLimitingSetting", "value": 0},
        ]
        normalized = api_module.SolarOfThingsAPI._normalize_settings(None, raw)

        self.assertEqual(normalized["outputSourcePrioritySetting"]["value"], 1)
        self.assertEqual(normalized["batteryPowerLimitingSetting"]["value"], 0)

    def test_normalizes_settings_dict_with_list_key(self) -> None:
        raw = {"list": [
            {"key": "outputSourcePrioritySetting", "value": 2},
        ]}
        normalized = api_module.SolarOfThingsAPI._normalize_settings(None, raw)

        self.assertEqual(normalized["outputSourcePrioritySetting"]["value"], 2)

    def test_normalizes_settings_dict_direct(self) -> None:
        raw = {
            "outputSourcePrioritySetting": {"key": "outputSourcePrioritySetting", "value": 1},
            "batteryPowerLimitingSetting": {"key": "batteryPowerLimitingSetting", "value": 1},
        }
        normalized = api_module.SolarOfThingsAPI._normalize_settings(None, raw)

        self.assertEqual(normalized["outputSourcePrioritySetting"]["value"], 1)
        self.assertEqual(normalized["batteryPowerLimitingSetting"]["value"], 1)

    def test_extracts_latest_non_null_field_values(self) -> None:
        payload = {
            "data": {
                "payload": {
                    "fields": {
                        "pvInputPower": [None, 2500.0, None],
                        "loadPower": [None, 0.133, None],
                    }
                }
            }
        }

        values = api_module._extract_latest_fields(
            payload,
            aliases={"loadPower": ("loadPower", True)},
        )

        self.assertEqual(values["pvInputPower"], 2500.0)
        self.assertEqual(values["loadPower"], 133.0)

    def test_fetch_latest_data_merges_alternative_live_keys(self) -> None:
        class FakeApi(api_module.SolarOfThingsAPI):
            def __init__(self) -> None:
                super().__init__(iot_token="test_token")

            def _now(self) -> datetime:
                return datetime(2026, 8, 6, 3, 5, tzinfo=timezone.utc)

            def _format_time(self, dt: datetime) -> str:
                return dt.isoformat()

            def fetch_energy_flow(self, device_id: str) -> dict:
                return {}

            def fetch_latest_state(self, device_id: str) -> dict:
                return {"batterySOC": 100.0}

            def _post(self, path: str, payload: dict, *, timeout: int = 30) -> dict:
                keys = payload["keys"]
                if "generationPower" in keys:
                    return {
                        "code": 0,
                        "data": {
                            "payload": {
                                "fields": {
                                    "generationPower": [None, 0.0],
                                    "loadPower": [None, 0.133],
                                    "powerGrid": [None, 0.161],
                                }
                            }
                        },
                    }

                return {
                    "code": 0,
                    "data": {
                        "payload": {
                            "fields": {
                                "pvInputPower": [None, None],
                                "acOutputActivePower": [None, None],
                                "batteryDischargeCurrent": [0.0, 0.0],
                                "batteryChargingCurrent": [0.0, 0.0],
                                "batteryVoltage": [27.2, 27.2],
                                "feedInPower": [None, None],
                                "batterySOC": [None, None],
                            }
                        }
                    },
                }

        values = FakeApi().fetch_latest_data("device-1")

        self.assertEqual(values["pvInputPower"], 0.0)
        self.assertEqual(values["loadPower"], 133.0)
        self.assertEqual(values["gridPower"], 161.0)
        self.assertEqual(values["batterySOC"], 100.0)
        self.assertEqual(values["batteryPower"], 0.0)

    def test_extracts_energy_flow_values(self) -> None:
        payload = {
            "data": {
                "pvPanelFlow": {
                    "value": {"unit": "kW", "value": 0.0},
                },
                "gridFlow": {
                    "flowDirection": 1,
                    "value": {"unit": "kW", "value": 0.163},
                },
                "batteryFlow": {
                    "value": {"unit": "V", "value": 27.2},
                },
                "loadFlow": {
                    "value": {"unit": "kW", "value": 0.143},
                },
                "deviceAttributeState": {
                    "fields": {
                        "batteryChargingCurrent": {"unit": "A", "value": 0},
                        "batteryDischargeCurrent": {"unit": "A", "value": 0},
                        "batteryCapacity": {"unit": "%", "value": 100},
                        "bmsCurrentSOC": {"unit": "%", "value": 0},
                        "pvTemperature": {"unit": "°C", "value": 28},
                        "inverterTemperature": {"unit": "°C", "value": 38},
                        "transformerTemperature": {"unit": "°C", "value": 32},
                    }
                },
            }
        }

        values = api_module._extract_energy_flow_values(payload)

        self.assertEqual(values["pvInputPower"], 0.0)
        self.assertEqual(values["gridPower"], 163.0)
        self.assertEqual(values["loadPower"], 143.0)
        self.assertEqual(values["acOutputActivePower"], 143.0)
        self.assertEqual(values["batteryVoltage"], 27.2)
        self.assertEqual(values["batteryChargingCurrent"], 0.0)
        self.assertEqual(values["batteryDischargeCurrent"], 0.0)
        self.assertEqual(values["batterySOC"], 100.0)
        self.assertEqual(values["pvTemperature"], 28.0)
        self.assertEqual(values["inverterTemperature"], 38.0)
        self.assertEqual(values["transformerTemperature"], 32.0)
