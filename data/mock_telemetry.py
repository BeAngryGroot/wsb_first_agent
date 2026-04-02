# =============================================================================
# data/mock_telemetry.py
# =============================================================================
# Purpose: Provides live telemetry data for network alarms by reading from
# local JSON file 'data/mock_telemetry.json'.
#
# Architecture:
#   - On first call, reads the JSON file and caches all records in memory.
#   - Subsequent calls use the cached dict — no additional file reads.
#   - get_telemetry_for_alarm() is the only public interface, consumed by
#     src/tools.py via the @tool decorator.
#
# In production, replace this with a real NMS API call:
#   response = requests.get(f"https://your-nms/api/alarms/{alarm_id}", ...)
#   return response.json()
#
# To add new alarm scenarios:
#   1. Add a new item to data/mock_telemetry.json
#   2. No need to run seed script - data is loaded directly from JSON
#   3. Add the corresponding ALARM_SCENARIOS entry in main.py
# =============================================================================

import json
import os


# ---------------------------------------------------------------------------
# Module-level cache — loaded once per process lifecycle.
# ---------------------------------------------------------------------------
_telemetry_cache: dict | None = None


def _load_telemetry_from_json() -> dict:
    """
    Reads the mock_telemetry.json file and returns all alarm scenarios as a
    dict keyed by alarm_id.

    Returns:
        Dict mapping alarm_id (str) -> telemetry metrics (dict).
    """
    global _telemetry_cache

    if _telemetry_cache is not None:
        return _telemetry_cache

    print(f"   [Telemetry] Loading alarm data from local JSON file...")
    try:
        json_path = os.path.join(os.path.dirname(__file__), "mock_telemetry.json")
        with open(json_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        # Build cache dict: {alarm_id: telemetry_metrics}
        _telemetry_cache = {}
        for item in items:
            alarm_id = item.get("alarm_id")
            telemetry = item.get("telemetry", {})
            if alarm_id:
                _telemetry_cache[alarm_id] = telemetry

        print(f"   [Telemetry] Loaded {len(_telemetry_cache)} alarm scenarios from JSON.")
        return _telemetry_cache

    except Exception as e:
        print(f"   [Telemetry] ERROR loading telemetry from JSON: {e}")
        raise


# Kept for backward compatibility with main.py imports
MOCK_NETWORK_TELEMETRY: dict = {}


def get_telemetry_for_alarm(alarm_id: str) -> dict:
    """
    Retrieves live telemetry data for a given alarm ID from local JSON file.

    Args:
        alarm_id: The unique identifier of the network alarm (e.g., 'ALARM-001').

    Returns:
        A dictionary of live network vitals, or an error dict if not found.
    """
    telemetry = _load_telemetry_from_json()

    if alarm_id in telemetry:
        return telemetry[alarm_id]
    else:
        return {
            "error": f"No telemetry found for alarm_id: {alarm_id}",
            "available_alarms": list(telemetry.keys()),
        }
