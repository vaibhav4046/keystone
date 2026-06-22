"""Test session setup.

The decision-recording endpoints now fail CLOSED by default (no token + no explicit opt-in =>
403), so the test suite enables the explicit open-demo opt-in BEFORE backend.app is imported.
This keeps the existing approve/approve-mr tests exercising the real write path; the dedicated
fail-closed test (tests/test_api.py) monkeypatches this off to assert the 403 default.
"""
import os

# Hard assignment (not setdefault): force the open-demo write path for the whole suite regardless
# of an ambient KEYSTONE_OPEN_DEMO=0 / stray token, so the approve/approve-mr/quorum tests always
# exercise the real write path. The dedicated fail-closed test monkeypatches these off per-test.
os.environ["KEYSTONE_OPEN_DEMO"] = "1"
os.environ.pop("KEYSTONE_APPROVE_TOKEN", None)
