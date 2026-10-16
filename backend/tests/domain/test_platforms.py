import pytest

from app.domain.platforms import LIMITS, validate


def codes(result, level=None):
    return [i.code for i in result.issues if level is None or i.level == level]


def test_x_exactly_280_passes():
    result = validate("x", "a" * 280)

    assert result.ok
    assert (result.length, result.limit) == (280, 280)


def test_x_281_fails():
    result = validate("x", "a" * 281)

    assert not result.ok
    assert codes(result, "error") == ["too_long"]


def test_x_counts_each_url_as_23():
    url = "https://example.org/a/very/long/path/that/is/much/longer/than/twenty/three"
    result = validate("x", f"Register {url} now")

    assert result.length == len("Register ") + 23 + len(" now")


def test_x_counts_bare_domain_as_23():
    assert validate("x", "see riverside.dev").length == len("see ") + 23


def test_x_link_counting_can_rescue_long_text():
    text = "a" * 250 + " https://example.org/" + "p" * 60
    assert validate("x", text).ok


def test_linkedin_boundaries():
    assert validate("linkedin", "a" * 1300).issues == []
    assert codes(validate("linkedin", "a" * 1301)) == ["long_for_readability"]
    assert validate("linkedin", "a" * 1301).ok
    assert validate("linkedin", "a" * 3000).ok
    assert not validate("linkedin", "a" * 3001).ok


def test_instagram_30_hashtags_pass_31_fail():
    tags30 = " ".join(f"#t{i}" for i in range(30))
    tags31 = " ".join(f"#t{i}" for i in range(31))

    assert validate("instagram", tags30).ok
    assert validate("instagram", tags30).hashtags == 30
    assert codes(validate("instagram", tags31), "error") == ["too_many_hashtags"]


def test_instagram_2200_boundary():
    assert validate("instagram", "a" * 2200).ok
    assert not validate("instagram", "a" * 2201).ok


def test_instagram_url_warns_link_in_bio():
    result = validate("instagram", "Register at https://example.org/r")

    assert result.ok
    assert codes(result, "warning") == ["link_not_clickable"]
    assert "Link in bio" in result.issues[0].message


def test_whatsapp_warns_over_700_errors_over_4096():
    assert validate("whatsapp", "a" * 700).issues == []
    over = validate("whatsapp", "a" * 701)
    assert over.ok and codes(over, "warning") == ["long_for_whatsapp"]
    assert not validate("whatsapp", "a" * 4097).ok


@pytest.mark.parametrize("platform", list(LIMITS))
def test_empty_text_is_an_error(platform):
    assert codes(validate(platform, "   "), "error") == ["empty"]


def test_hashtag_inside_url_not_counted():
    assert validate("linkedin", "https://example.org/#section #real").hashtags == 1
