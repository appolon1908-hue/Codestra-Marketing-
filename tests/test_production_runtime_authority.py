import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "runtime_authority", ROOT / "scripts" / "validate_production_runtime_authority.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def authority():
    return json.loads(MODULE.AUTHORITY.read_text())


def rejected(authority, mutation):
    candidate = copy.deepcopy(authority)
    mutation(candidate)
    with pytest.raises(ValueError):
        MODULE.validate(candidate)


def test_current_unverified_off_host_record_is_valid(authority):
    MODULE.validate(authority)


def test_cannot_claim_production_ready(authority):
    rejected(authority, lambda row: row.__setitem__("production_ready", True))


def test_cannot_authorize_deployment_or_writes(authority):
    rejected(authority, lambda row: row.__setitem__("deployment_authorized", True))
    rejected(authority, lambda row: row.__setitem__("production_writes_authorized", True))


def test_cannot_hide_unknown_live_safety_with_gate(authority):
    rejected(
        authority,
        lambda row: row["required_gates"].__setitem__(
            "live_advertising_readback_false", True
        ),
    )


def test_runtime_location_must_match_observed_ip(authority):
    rejected(authority, lambda row: row.__setitem__("runtime_location", "65.109.65.169"))


def test_source_capabilities_remain_fail_closed(authority):
    rejected(
        authority,
        lambda row: row["source_capabilities"].__setitem__(
            "live_advertising_default", True
        ),
    )
