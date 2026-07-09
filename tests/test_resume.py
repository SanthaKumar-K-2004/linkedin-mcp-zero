from unittest.mock import MagicMock, patch

import pytest

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.storage.db import Storage


@pytest.fixture
def mock_storage(tmp_path) -> Storage:
    settings = Settings(data_dir=str(tmp_path))
    storage = Storage(settings)
    return storage


def test_resume_path_validation_allowed_dirs(tmp_path, mock_storage) -> None:
    engine = ResumeEngine(mock_storage)

    # Create allowed file
    allowed_file = tmp_path / "resume.txt"
    allowed_file.write_text("John Doe\nSkills: Python, SQL")

    res = engine.analyze_resume(str(allowed_file))
    assert res["id"] > 0
    assert res["name"] == "John Doe"
    assert "Python" in res["skills"]


def test_resume_path_validation_disallowed_dirs(mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    with pytest.raises(ValueError) as excinfo:
        # File in root which is not allowed
        engine.analyze_resume("/etc/hosts")
    assert "is outside allowed directories" in str(excinfo.value)


def test_resume_not_found(tmp_path, mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    with pytest.raises(FileNotFoundError):
        engine.analyze_resume(str(tmp_path / "nonexistent.txt"))


def test_resume_docx_parsing(tmp_path, mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    docx_file = tmp_path / "resume.docx"

    # Mock docx Document and paragraph text
    with patch("linkedin_mcp_zero.engines.resume.Document") as MockDoc:
        mock_doc = MagicMock()
        p1 = MagicMock()
        p1.text = "Jane Doe"
        p2 = MagicMock()
        p2.text = "Skills: JavaScript, AWS"
        mock_doc.paragraphs = [p1, p2]
        MockDoc.return_value = mock_doc

        # Touch file to exist
        docx_file.touch()
        res = engine.analyze_resume(str(docx_file))
        assert res["name"] == "Jane Doe"
        assert "JavaScript" in res["skills"]


def test_resume_pdf_parsing(tmp_path, mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    pdf_file = tmp_path / "resume.pdf"
    pdf_file.touch()

    import sys

    mock_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Alice Cooper\nSkills: GCP, Docker"
    mock_doc.__enter__.return_value = [mock_page]
    mock_fitz.open.return_value = mock_doc

    sys.modules["fitz"] = mock_fitz
    try:
        res = engine.analyze_resume(str(pdf_file))
        assert res["name"] == "Alice Cooper"
        assert "GCP" in res["skills"]
    finally:
        del sys.modules["fitz"]


@pytest.mark.asyncio
async def test_resume_insights(mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    # Save a dummy resume in DB
    resume_id = mock_storage.save_resume(
        "/dummy/path",
        {
            "name": "Bob",
            "skills": ["Python", "AWS"],
        },
    )

    insights = await engine.get_resume_insights(resume_id)
    assert insights["id"] == resume_id
    assert "Docker" in insights["gap_skills"]
    assert "Python" in insights["strengths"]


@pytest.mark.asyncio
async def test_resume_insights_not_found(mock_storage) -> None:
    engine = ResumeEngine(mock_storage)
    insights = await engine.get_resume_insights(9999)
    assert "error" in insights
    assert insights["error"] == "resume_not_found"
