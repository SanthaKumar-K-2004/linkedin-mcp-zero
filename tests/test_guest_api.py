from linkedin_mcp_zero.scraping.guest_api import (
    extract_job_id,
    parse_job_detail,
    parse_search_results,
)

SEARCH_HTML = """
<div class="base-card">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/senior-python-dev-3900000012?x=1"></a>
  <h3 class="base-search-card__title"> Senior Python Developer </h3>
  <h4 class="base-search-card__subtitle"> Example Co </h4>
  <span class="job-search-card__location"> New York, United States </span>
  <time datetime="2026-06-10"></time>
</div>
"""


DETAIL_HTML = """
<script type="application/ld+json">
{
  "@context":"https://schema.org",
  "@type":"JobPosting",
  "title":"Senior Python Developer",
  "hiringOrganization":{"@type":"Organization","name":"Example Co"},
  "jobLocation":{
    "@type":"Place",
    "address":{
      "addressLocality":"New York",
      "addressRegion":"NY",
      "addressCountry":"United States"
    }
  },
  "datePosted":"2026-06-10",
  "employmentType":"FULL_TIME",
  "baseSalary":{"@type":"MonetaryAmount","currency":"USD","value":{"@type":"QuantitativeValue","minValue":150000,"maxValue":200000,"unitText":"YEAR"}},
  "description":"Build APIs with Python, FastAPI, SQL, Docker, and Kubernetes."
}
</script>
"""


def test_extract_job_id_from_url() -> None:
    assert (
        extract_job_id("https://www.linkedin.com/jobs/view/senior-python-dev-3900000012")
        == "3900000012"
    )
    assert extract_job_id("3900000012") == "3900000012"


def test_parse_search_results_compressed() -> None:
    result = parse_search_results(SEARCH_HTML)
    assert result == [
        {
            "id": "3900000012",
            "t": "Senior Python Developer",
            "co": "Example Co",
            "loc": "NY, US",
            "url": "https://www.linkedin.com/jobs/view/senior-python-dev-3900000012",
            "age": "4d",
        }
    ]


def test_parse_job_detail_schema() -> None:
    result = parse_job_detail(DETAIL_HTML, "3900000012")
    assert result["t"] == "Senior Python Developer"
    assert result["co"] == "Example Co"
    assert result["sal"] == "$150K-200K/yr"
    assert result["type"] == "FT"
    assert "Python" in result["skills"]
    assert "Kubernetes" in result["skills"]
