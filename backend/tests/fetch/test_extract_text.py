from pathlib import Path

from app.fetch.extract_text import extract_text

FIXTURE = Path(__file__).parent / "fixtures" / "event_page.html"


def test_extracts_readable_text_from_saved_page():
    page = extract_text(FIXTURE.read_text(encoding="utf-8"))

    lines = page.text.splitlines()
    assert lines[0] == "Riverside Open Source Hack Day 2026 | Events"
    assert "A free hack day for first-time open source contributors." in lines
    assert "Riverside Open Source Hack Day 2026" in lines
    assert "Saturday, 24 October 2026, 10:00 AM to 5:30 PM IST" in lines
    assert "Venue: Lakeview Co-working Hall, 14 Station Road, Indore" in lines
    assert "Mentors: Asha Verma (Python), Kabir Nair (JavaScript)" in lines
    assert "Judges: Meera Iyer" in lines
    assert (
        "Register at https://example.org/riverside-hackday/register — seats & snacks included."
        in lines
    )


def test_drops_scripts_styles_and_hidden_content():
    page = extract_text(FIXTURE.read_text(encoding="utf-8"))

    for hidden in ("SECRET_TRACKER", "font-family", "TEMPLATE_CONTENT", "SVG_LABEL", "enable"):
        assert hidden not in page.text


def test_counts_scripts_for_javascript_hint():
    page = extract_text(FIXTURE.read_text(encoding="utf-8"))

    assert page.script_count == 2
    assert page.title == "Riverside Open Source Hack Day 2026 | Events"


def test_link_href_is_kept_when_anchor_text_differs():
    page = extract_text('<p>Sign up <a href="https://ex.org/r">here</a></p>')

    assert page.text == "Sign up here (https://ex.org/r)"


def test_relative_and_script_links_are_not_added():
    page = extract_text('<p><a href="/r">here</a> <a href="javascript:x()">x</a></p>')

    assert page.text == "here x"


def test_empty_and_broken_html():
    assert extract_text("").text == ""
    assert extract_text("<div><p>Unclosed <b>bold").text == "Unclosed bold"


def test_collapses_blank_lines_and_spaces():
    page = extract_text("<div>  A   b </div><br><br><br><div>C</div>")

    assert page.text == "A b\nC"
