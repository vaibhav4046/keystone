"""Test session setup.

The decision-recording endpoints now fail CLOSED by default (no token + no explicit opt-in =>
403), so the test suite enables the explicit open-demo opt-in BEFORE backend.app is imported.
This keeps the existing approve/approve-mr tests exercising the real write path; the dedicated
fail-closed test (tests/test_api.py) monkeypatches this off to assert the 403 default.
"""
import os

os.environ.setdefault("KEYSTONE_OPEN_DEMO", "1")
