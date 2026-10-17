from datetime import date

import pytest

from app.domain.guard import check, find_placeholders, is_blocking
from app.domain.planning import propose_plan
from app.domain.platforms import validate
from app.domain.schemas import PLATFORM_ORDER
from app.llm.base import LLMProvider, call_validated
from app.llm.jsonrepair import extract_json_object
from app.llm.mock import MockProvider, extract_facts
from app.llm.prompts import extract_prompt, generate_prompt, redraft_prompt, revise_prompt
from app.llm.schemas import ExtractOutput, GenerateOutput, RewrittenPost


@pytest.fixture
def mock() -> MockProvider:
    return MockProvider()


def test_mock_satisfies_protocol(mock):
    assert isinstance(mock, LLMProvider)
    assert mock.name == "mock"


def test_extract_finds_sample_facts_with_exact_snippets(sample_text):
    facts = {f["key"]: f for f in extract_facts(sample_text)}

    assert facts["event_name"]["value"] == "Riverside Open Source Hack Day 2026"
    assert facts["start_date"]["value"] == "2026-10-24"
    assert facts["start_time"]["value"] == "10:00"
    assert facts["end_time"]["value"] == "17:30"
    assert facts["timezone"]["value"] == "Asia/Kolkata"
    assert facts["venue"]["value"] == "Lakeview Co-working Hall"
    assert facts["address"]["value"] == "14 Station Road, Indore"
    assert facts["city"]["value"] == "Indore"
    assert facts["event_mode"]["value"] == "offline"
    assert facts["registration_url"]["value"] == "https://example.org/riverside-hackday/register"
    assert facts["registration_deadline"]["value"] == "2026-10-22"
    assert facts["capacity"]["value"] == "80"
    assert facts["audience"]["value"].startswith("students and early-career developers")
    assert facts["mentors"]["value"] == [
        {"name": "Asha Verma", "role": "Python"},
        {"name": "Kabir Nair", "role": "JavaScript"},
    ]
    assert facts["judges"]["value"] == [{"name": "Meera Iyer", "role": ""}]
    assert facts["partners"]["value"] == [
        {"name": "Lakeview Co-working", "role": "", "handle": "@lakeviewhub"}
    ]
    assert facts["hashtags"]["value"] == ["#RiversideHack", "#Hacktoberfest"]
    for f in facts.values():
        assert f["source_snippet"] in sample_text, f["key"]


def test_extract_ignores_text_without_facts():
    assert extract_facts("Nothing to see here at all, just words and more words.") == []


async def test_extract_through_call_validated(mock, sample_text):
    result = await call_validated(mock, extract_prompt(sample_text), ExtractOutput)

    assert result.provider == "mock"
    assert result.prompt_version == "extract.v1"
    assert any(f.key == "event_name" for f in result.data.facts)


async def test_output_is_deterministic(mock, sample_text):
    prompt = extract_prompt(sample_text)

    first = await mock.complete(system=prompt.system, prompt=prompt.user)
    second = await mock.complete(system=prompt.system, prompt=prompt.user)

    assert first.text == second.text


async def test_unknown_task_returns_empty_object(mock):
    done = await mock.complete(system="s", prompt="no task marker")

    assert extract_json_object(done.text) == {}


def _plan_items(sample_facts):
    items = propose_plan(
        sample_facts, list(PLATFORM_ORDER), today=date(2026, 10, 1), timezone="Asia/Kolkata"
    )
    return [
        {"title": i.title, "purpose": i.purpose, "stage": i.stage, "fact_keys": i.fact_keys}
        for i in items
    ]


async def test_every_mock_post_for_the_sample_passes_guard_and_validators(mock, sample_facts):
    items = _plan_items(sample_facts)
    assert len(items) >= 8

    for item in items:
        prompt = generate_prompt(
            sample_facts, item, list(PLATFORM_ORDER), tone="friendly", language="en"
        )
        result = await call_validated(mock, prompt, GenerateOutput)

        assert [p.platform for p in result.data.posts] == list(PLATFORM_ORDER)
        for post in result.data.posts:
            flags = check(post.text, sample_facts)
            label = f"{item['title']} / {post.platform}"
            assert not is_blocking(flags, find_placeholders(post.text)), (label, flags)
            validation = validate(post.platform, post.text)
            assert validation.ok, (label, validation)
            assert not [i for i in validation.issues if i.level == "warning"], (label, validation)
            assert "event_name" in post.facts_used
            assert set(post.facts_used) <= {f.key for f in sample_facts}


async def test_instagram_uses_link_in_bio_and_visual_line(mock, sample_facts):
    item = _plan_items(sample_facts)[0]
    prompt = generate_prompt(sample_facts, item, ["instagram"], tone="", language="en")

    post = (await call_validated(mock, prompt, GenerateOutput)).data.posts[0]

    assert "Link in bio" in post.text
    assert "https://" not in post.text
    assert "\n---\n" in post.text


async def test_generate_uses_only_facts_in_prompt(mock, sample_facts):
    minimal = [f for f in sample_facts if f.key in ("event_name", "start_date", "timezone")]
    item = {"title": "Event announcement", "purpose": "", "stage": "pre", "fact_keys": []}
    prompt = generate_prompt(minimal, item, ["linkedin"], tone="", language="en")

    post = (await call_validated(mock, prompt, GenerateOutput)).data.posts[0]

    assert "Lakeview" not in post.text
    assert "example.org" not in post.text
    assert not is_blocking(check(post.text, minimal), find_placeholders(post.text))


async def _first_post(mock, sample_facts, platform="linkedin"):
    item = _plan_items(sample_facts)[0]
    prompt = generate_prompt(sample_facts, item, [platform], tone="", language="en")
    return (await call_validated(mock, prompt, GenerateOutput)).data.posts[0].text


async def test_revise_make_shorter_shortens_and_keeps_facts(mock, sample_facts):
    text = await _first_post(mock, sample_facts)
    prompt = revise_prompt(sample_facts, "linkedin", text, "make_shorter")

    revised = (await call_validated(mock, prompt, RewrittenPost)).data

    assert len(revised.text) < len(text)
    assert not is_blocking(check(revised.text, sample_facts), [])


@pytest.mark.parametrize("instruction", ["make_longer", "warmer", "more_formal"])
async def test_other_revisions_change_text_and_pass_guard(mock, sample_facts, instruction):
    text = await _first_post(mock, sample_facts)
    prompt = revise_prompt(sample_facts, "linkedin", text, instruction)

    revised = (await call_validated(mock, prompt, RewrittenPost)).data

    assert revised.text != text
    assert not is_blocking(check(revised.text, sample_facts), [])
    assert validate("linkedin", revised.text).ok


async def test_redraft_replaces_changed_time(mock, sample_facts):
    text = await _first_post(mock, sample_facts)
    assert "10:00 AM" in text
    new_facts = [
        f.model_copy(update={"value": "09:30"}) if f.key == "start_time" else f
        for f in sample_facts
    ]
    change = {"key": "start_time", "old": "10:00", "new": "09:30"}

    redrafted = (
        await call_validated(
            mock, redraft_prompt(new_facts, "linkedin", text, change), RewrittenPost
        )
    ).data

    assert "9:30 AM" in redrafted.text
    assert "10:00 AM" not in redrafted.text
    assert not is_blocking(check(redrafted.text, new_facts), [])


async def test_redraft_replaces_changed_date(mock, sample_facts):
    text = await _first_post(mock, sample_facts, "x")
    new_facts = [
        f.model_copy(update={"value": "2026-10-25"}) if f.key == "start_date" else f
        for f in sample_facts
    ]
    change = {"key": "start_date", "old": "2026-10-24", "new": "2026-10-25"}

    redrafted = (
        await call_validated(mock, redraft_prompt(new_facts, "x", text, change), RewrittenPost)
    ).data

    assert redrafted.text != text
    assert not is_blocking(check(redrafted.text, new_facts), [])
