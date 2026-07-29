"""Live smoke tests against LinkedIn's guest jobs API.

These are excluded from normal runs — they hit the real network and can be
rate-limited or geo-blocked. Run them deliberately with:

    LINKEDIN_MCP_LIVE=1 uv run pytest tests/test_live_guest_api.py -q
"""

from __future__ import annotations

import os

import pytest

from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient
from linkedin_mcp_zero.utils.errors import UpstreamError

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("LINKEDIN_MCP_LIVE") != "1",
        reason="live guest-API tests need LINKEDIN_MCP_LIVE=1 and network access",
    ),
]


async def _live_client() -> GuestAPIClient:
    client = GuestAPIClient(timeout=20)
    return client


async def test_live_search_jobs_smoke() -> None:
    client = await _live_client()
    try:
        jobs = await client.search_jobs("python developer", "remote", limit=5)
    except UpstreamError as exc:  # treat geo-blocks/throttling as a skip
        pytest.skip(f"guest API unreachable/blocked from this network: {exc}")
    assert jobs, "expected at least one job from the live guest API"
    first = jobs[0]
    for key in ("id", "t", "co"):
        assert key in first, f"missing key {key!r} in {first!r}"
    assert str(first["id"]).isdigit()


async def test_live_job_details_smoke() -> None:
    client = await _live_client()
    try:
        jobs = await client.search_jobs("engineer", limit=3)
    except UpstreamError as exc:
        pytest.skip(f"guest API unreachable/blocked from this network: {exc}")
    if not jobs:
        pytest.skip("no jobs returned to derive a job id")
    job_id = str(jobs[0]["id"])
    try:
        detail = await client.get_job_details(job_id)
    except UpstreamError as exc:
        pytest.skip(f"job details blocked from this network: {exc}")
    assert detail["id"] == job_id
    assert detail.get("t")


async def test_live_company_typeahead_smoke() -> None:
    client = await _live_client()
    try:
        company_id = await client.resolve_company_id("microsoft")
    except UpstreamError as exc:
        pytest.skip(f"typeahead blocked from this network: {exc}")
    if company_id is None:
        pytest.skip("typeahead endpoint returned no parsable hits from this network")
    assert company_id.isdigit()
