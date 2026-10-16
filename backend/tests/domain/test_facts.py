from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.facts import (
    CRITICAL_KEYS,
    DateValue,
    extract_tokens,
    generation_blockers,
    is_critical,
    normalize_text,
    normalize_url,
    parse_amount,
    parse_date,
    parse_time,
)
from app.domain.schemas import Fact


def fact(key, value, status="confirmed", **extra) -> Fact:
    return Fact(id=uuid4(), key=key, value=value, status=status, critical=is_critical(key), **extra)


def gate_facts(**overrides):
    values = {
        "event_name": "Riverside Hack Day",
        "start_date": "2026-10-24",
        "timezone": "Asia/Kolkata",
        "audience": "Students",
        "registration_url": "https://example.org/register",
    }
    values.update(overrides)
    return [fact(k, v) for k, v in values.items() if v is not None]


# ---- critical set and BR01 gate ----------------------------------------------------------


def test_critical_set_matches_lld():
    assert {"event_name", "start_date", "timezone", "event_mode", "audience", "language"} <= (
        CRITICAL_KEYS
    )
    assert not is_critical("speakers")
    assert not is_critical("end_date")


def test_gate_open_when_all_confirmed():
    assert generation_blockers(gate_facts(), "en") == []


@pytest.mark.parametrize("missing", ["event_name", "start_date", "timezone", "audience"])
def test_gate_reports_each_missing_key(missing):
    assert generation_blockers(gate_facts(**{missing: None}), "en") == [missing]


def test_gate_reports_exactly_the_missing_keys_in_order():
    facts = gate_facts(audience=None, event_name=None)

    assert generation_blockers(facts, "en") == ["event_name", "audience"]


def test_needs_review_fact_does_not_count():
    facts = gate_facts()
    facts[3] = fact("audience", "Students", status="needs_review")

    assert generation_blockers(facts, "en") == ["audience"]


def test_empty_value_does_not_count():
    assert generation_blockers(gate_facts(audience="  "), "en") == ["audience"]


def test_language_needed_when_not_chosen():
    assert generation_blockers(gate_facts(), None) == ["language"]
    assert generation_blockers(gate_facts() + [fact("language", "en")], None) == []


def test_invalid_start_date_blocks():
    assert generation_blockers(gate_facts(start_date="next Saturday"), "en") == ["start_date"]


def test_invalid_timezone_blocks():
    assert generation_blockers(gate_facts(timezone="India time"), "en") == ["timezone"]


def test_registration_url_needed_unless_not_applicable():
    facts = gate_facts(registration_url=None)
    assert generation_blockers(facts, "en") == ["registration_url"]

    facts.append(fact("registration_url", "", not_applicable=True))
    assert generation_blockers(facts, "en") == []


def test_registration_url_must_be_a_url():
    assert generation_blockers(gate_facts(registration_url="ask Asha"), "en") == [
        "registration_url"
    ]


# ---- normalisers --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-24", DateValue(10, 24, 2026)),
        ("24 Oct", DateValue(10, 24, None)),
        ("24 October 2026", DateValue(10, 24, 2026)),
        ("24th October 2026", DateValue(10, 24, 2026)),
        ("24th of October", DateValue(10, 24, None)),
        ("Oct 24", DateValue(10, 24, None)),
        ("October 24, 2026", DateValue(10, 24, 2026)),
        ("Oct. 24th", DateValue(10, 24, None)),
        ("Saturday, 24 October 2026", DateValue(10, 24, 2026)),
        ("Sat 24 Oct", DateValue(10, 24, None)),
        ("24/10/2026", DateValue(10, 24, 2026)),
        ("24-10-2026", DateValue(10, 24, 2026)),
        ("24.10.2026", DateValue(10, 24, 2026)),
        ("1 Nov", DateValue(11, 1, None)),
        ("Sept 3", DateValue(9, 3, None)),
        ("3rd Dec 2026", DateValue(12, 3, 2026)),
        ("22nd Oct, 2026", DateValue(10, 22, 2026)),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "soon", "32 Oct", "2026-13-01", "Octopus 5", "31/02/x"])
def test_parse_date_rejects(raw):
    assert parse_date(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10:00", (10, 0)),
        ("17:30", (17, 30)),
        ("09:05", (9, 5)),
        ("10 AM", (10, 0)),
        ("10am", (10, 0)),
        ("10.30 pm", (22, 30)),
        ("5:30 PM", (17, 30)),
        ("12 pm", (12, 0)),
        ("12:15 am", (0, 15)),
        ("7 p.m.", (19, 0)),
        ("10:00 AM", (10, 0)),
    ],
)
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


@pytest.mark.parametrize("raw", ["", "25:00", "noonish", "13 pm", "10"])
def test_parse_time_rejects(raw):
    assert parse_time(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("₹499", ("INR", Decimal("499"))),
        ("INR 499", ("INR", Decimal("499"))),
        ("Rs. 1,499", ("INR", Decimal("1499"))),
        ("Rs 250", ("INR", Decimal("250"))),
        ("$20", ("USD", Decimal("20"))),
        ("USD 20.50", ("USD", Decimal("20.50"))),
        ("€15", ("EUR", Decimal("15"))),
        ("499 rupees", ("INR", Decimal("499"))),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://Example.org/register/", "example.org/register"),
        ("http://example.org/register", "example.org/register"),
        ("https://www.example.org/register", "example.org/register"),
        ("example.org/register", "example.org/register"),
        (
            "https://example.org/r?utm_source=x&id=5&utm_medium=y",
            "example.org/r?id=5",
        ),
        ("https://example.org/Path/Case", "example.org/Path/Case"),
        ("https://example.org/register.", "example.org/register"),
        ("not a url", None),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_normalize_text_collapses_and_casefolds():
    assert normalize_text("  Riverside  HACK\n Day ") == "riverside hack day"
    assert normalize_text("ﬁle") == "file"


# ---- token extraction ----------------------------------------------------------------------


def kinds(text):
    return [(t.kind, t.raw) for t in extract_tokens(text)]


def test_extract_tokens_mixed_post():
    text = (
        "Join us on Sat 24 Oct, 10:00 AM to 5:30 PM at @lakeviewhub. Entry ₹0. "
        "Only 80 seats! Register: https://example.org/riverside-hackday/register."
    )

    assert kinds(text) == [
        ("date", "Sat 24 Oct"),
        ("time", "10:00 AM"),
        ("time", "5:30 PM"),
        ("handle", "@lakeviewhub"),
        ("amount", "₹0"),
        ("count", "80 seats"),
        ("url", "https://example.org/riverside-hackday/register"),
    ]


def test_dates_are_not_reread_as_times():
    assert kinds("on 24.10.2026") == [("date", "24.10.2026")]


def test_email_is_not_a_handle_or_url():
    assert kinds("write to team@example.org") == []


def test_en_dash_time_range():
    assert kinds("10:00–17:30") == [("time", "10:00"), ("time", "17:30")]


def test_relative_words():
    assert kinds("See you tomorrow, this Saturday or next week") == [
        ("relative", "tomorrow"),
        ("relative", "this Saturday"),
        ("relative", "next week"),
    ]


def test_bare_domain_found():
    assert kinds("details at riverside.dev today") == [
        ("url", "riverside.dev"),
        ("relative", "today"),
    ]


def test_token_spans_point_into_text():
    text = "Doors open 10 am sharp"
    (token,) = extract_tokens(text)

    assert text[token.span[0] : token.span[1]] == "10 am"
