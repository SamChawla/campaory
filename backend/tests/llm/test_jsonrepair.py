import pytest

from app.llm.jsonrepair import JSONExtractionError, extract_json_object


def test_plain_object():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_strips_json_code_fence():
    text = '```json\n{"facts": [{"key": "event_name"}]}\n```'

    assert extract_json_object(text) == {"facts": [{"key": "event_name"}]}


def test_strips_bare_code_fence():
    assert extract_json_object('```\n{"a": 2}\n```') == {"a": 2}


def test_tolerates_prose_before_and_after():
    text = 'Here is the JSON you asked for:\n{"a": {"b": [1, 2]}}\nLet me know if you need more.'

    assert extract_json_object(text) == {"a": {"b": [1, 2]}}


def test_removes_trailing_commas():
    text = '{"a": [1, 2, ], "b": {"c": 3,},}'

    assert extract_json_object(text) == {"a": [1, 2], "b": {"c": 3}}


def test_braces_and_commas_inside_strings_are_kept():
    text = '{"text": "Use {curly}, and ,} inside", "n": 1}'

    assert extract_json_object(text) == {"text": "Use {curly}, and ,} inside", "n": 1}


def test_escaped_quotes_inside_strings():
    text = '{"text": "She said \\"hi\\", then left}"}'

    assert extract_json_object(text) == {"text": 'She said "hi", then left}'}


def test_takes_first_object_when_several():
    assert extract_json_object('{"a": 1} and then {"b": 2}') == {"a": 1}


def test_fence_with_prose_outside():
    text = 'Sure!\n```json\n{"posts": []}\n```\nDone.'

    assert extract_json_object(text) == {"posts": []}


@pytest.mark.parametrize("text", ["", "no json here", "[1, 2, 3]", '{"a": 1', '{"a": tru}'])
def test_unrecoverable_text_raises(text):
    with pytest.raises(JSONExtractionError):
        extract_json_object(text)
