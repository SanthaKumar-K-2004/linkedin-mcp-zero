import pytest

from linkedin_mcp_zero.scraping.guest_api import parse_job_detail, parse_search_results
from linkedin_mcp_zero.server.app import create_app

SAMPLE_DUPLICATE_HTML = """
<ul class="jobs-search__results-list">
  <li>
    <div class="base-card relative w-full base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:111111">
      <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/python-developer-111111">
        <span class="sr-only">Python Developer</span>
      </a>
      <h3 class="base-search-card__title">Python Developer</h3>
      <h4 class="base-search-card__subtitle">Tata Consultancy Services</h4>
      <span class="job-search-card__location">Chennai, Tamil Nadu, India</span>
      <span class="job-posting-benefits__text">Actively Hiring</span>
      <span class="job-search-card__salary-info">₹6,00,000 - ₹9,00,000</span>
      <time datetime="2026-10-25">5 days ago</time>
    </div>
  </li>
  <li>
    <div class="base-card relative w-full base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:222222">
      <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/backend-developer-222222">
        <span class="sr-only">Backend Developer</span>
      </a>
      <h3 class="base-search-card__title">Backend Developer</h3>
      <h4 class="base-search-card__subtitle">Zoho Corporation</h4>
      <span class="job-search-card__location">Chennai, Tamil Nadu, India</span>
      <time datetime="2026-10-28">2 days ago</time>
    </div>
  </li>
</ul>
"""

SAMPLE_JOB_DETAIL_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Senior Python Engineer",
        "description": "Looking for Python, FastAPI, Docker, and PostgreSQL experts.",
        "hiringOrganization": {
          "@type": "Organization",
          "name": "Zoho"
        },
        "jobLocation": {
          "@type": "Place",
          "address": {
            "addressLocality": "Chennai",
            "addressRegion": "Tamil Nadu",
            "addressCountry": "India"
          }
        },
        "datePosted": "2026-10-20"
      }
    </script>
  </head>
  <body>
    <div class="num-applicants__caption">Over 150 applicants</div>
  </body>
</html>
"""


def test_parse_search_results_deduplication() -> None:
    # Verify no duplicates are returned even if multiple CSS selectors match the same card
    results = parse_search_results(SAMPLE_DUPLICATE_HTML)
    assert len(results) == 2, f"Expected 2 unique jobs, got {len(results)}"
    ids = [r["id"] for r in results]
    assert ids == ["111111", "222222"]


def test_parse_search_results_rich_fields() -> None:
    results = parse_search_results(SAMPLE_DUPLICATE_HTML)
    job1 = results[0]
    assert job1["id"] == "111111"
    assert job1["t"] == "Python Developer"
    assert job1["co"] == "Tata Consultancy Services"
    assert job1["loc"] == "Chennai, Tamil Nadu, IN"
    assert job1["posted"] == "2026-10-25"
    assert job1["benefits"] == "Actively Hiring"
    assert "₹6,00,000" in str(job1["sal"])


def test_parse_job_detail_applicants() -> None:
    detail = parse_job_detail(SAMPLE_JOB_DETAIL_HTML, "111111")
    assert detail["id"] == "111111"
    assert detail["t"] == "Senior Python Engineer"
    assert detail["co"] == "Zoho"
    assert detail["applicants"] == "Over 150 applicants"
    assert detail["posted"] == "2026-10-20"


@pytest.mark.asyncio
async def test_tool_parameter_descriptions() -> None:
    app = create_app()
    tools = await app.list_tools()
    tools_by_name = {t.name: t for t in tools}

    # 1. Check search_jobs parameter descriptions
    assert "search_jobs" in tools_by_name
    sj = tools_by_name["search_jobs"]
    props = sj.parameters.get("properties", {})
    assert "kw" in props
    assert len(props["kw"].get("description", "")) > 10, "kw parameter must have a meaningful description"
    assert "loc" in props
    assert len(props["loc"].get("description", "")) > 10, "loc parameter must have a meaningful description"

    # 2. Check get_job_details parameter descriptions
    assert "get_job_details" in tools_by_name
    gjd = tools_by_name["get_job_details"]
    gjd_props = gjd.parameters.get("properties", {})
    assert "id" in gjd_props
    assert "LinkedIn numerical job ID" in gjd_props["id"].get("description", "")

    # 3. Check tailor_resume parameter descriptions
    assert "tailor_resume" in tools_by_name
    tr = tools_by_name["tailor_resume"]
    tr_props = tr.parameters.get("properties", {})
    assert "path" in tr_props
    assert len(tr_props["path"].get("description", "")) > 10
