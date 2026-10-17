from datetime import UTC, datetime

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.core.rate_limit import (
    DailyCap,
    LimitSubject,
    RateLimited,
    RateLimiter,
    Rule,
    client_ip,
    limit_subject,
    model_rules,
    request_rules,
)

HOUR = 3600
DAY = 86400


class FakeClock:
    def __init__(self, start: float = datetime(2026, 10, 17, 10, tzinfo=UTC).timestamp()):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_allows_up_to_limit_then_raises_with_retry_after(clock):
    limiter = RateLimiter(clock=clock)
    rules = [Rule("hour", 10, HOUR)]

    for _ in range(10):
        limiter.hit("guest:a", rules)
    with pytest.raises(RateLimited) as exc:
        limiter.hit("guest:a", rules)

    assert exc.value.status == 429
    assert exc.value.code == "rate_limited"
    assert exc.value.retry_after_seconds == 360
    assert exc.value.message == "Try again in 6 minutes."


def test_tokens_refill_over_time(clock):
    limiter = RateLimiter(clock=clock)
    rules = [Rule("hour", 10, HOUR)]
    for _ in range(10):
        limiter.hit("k", rules)

    clock.advance(359)
    with pytest.raises(RateLimited) as exc:
        limiter.hit("k", rules)
    assert exc.value.retry_after_seconds == 1
    assert exc.value.message == "Try again in 1 second."

    clock.advance(1)
    limiter.hit("k", rules)


def test_keys_are_independent(clock):
    limiter = RateLimiter(clock=clock)
    rules = [Rule("hour", 1, HOUR)]

    limiter.hit("a", rules)
    limiter.hit("b", rules)
    with pytest.raises(RateLimited):
        limiter.hit("a", rules)


def test_day_rule_limits_after_hours_of_steady_use(clock):
    limiter = RateLimiter(clock=clock)
    rules = [Rule("hour", 10, HOUR), Rule("day", 30, DAY)]

    allowed = 0
    for _ in range(4 * 60):  # one attempt a minute for four hours
        try:
            limiter.hit("g", rules)
            allowed += 1
        except RateLimited:
            pass
        clock.advance(60)

    assert 30 <= allowed < 40


def test_failed_hit_consumes_nothing(clock):
    limiter = RateLimiter(clock=clock)
    limiter.hit("g", [Rule("day", 1, DAY)])

    with pytest.raises(RateLimited) as exc:
        limiter.hit("g", [Rule("hour", 5, HOUR), Rule("day", 1, DAY)])

    assert exc.value.retry_after_seconds == DAY
    for _ in range(5):
        limiter.hit("g", [Rule("hour", 5, HOUR)])


def test_retry_after_is_the_longest_wait(clock):
    limiter = RateLimiter(clock=clock)
    rules = [Rule("minute", 1, 60), Rule("hour", 1, HOUR)]
    limiter.hit("g", rules)

    with pytest.raises(RateLimited) as exc:
        limiter.hit("g", rules)

    assert exc.value.retry_after_seconds == HOUR
    assert exc.value.message == "Try again in 60 minutes."


def test_full_buckets_are_pruned_when_too_many_keys(clock):
    limiter = RateLimiter(clock=clock, max_keys=3)
    rules = [Rule("hour", 1, HOUR)]
    for key in "abc":
        limiter.hit(key, rules)
    clock.advance(HOUR)

    limiter.hit("d", rules)

    assert limiter.size() <= 3


def test_daily_cap_counts_and_resets_at_utc_midnight(clock):
    cap = DailyCap(2, clock=clock)

    assert cap.take() and cap.take()
    assert not cap.take()
    assert cap.remaining() == 0

    clock.now = datetime(2026, 10, 18, 0, 0, 1, tzinfo=UTC).timestamp()
    assert cap.remaining() == 2
    assert cap.take()


def test_zero_daily_cap_blocks_everything(clock):
    assert not DailyCap(0, clock=clock).take()


def test_model_rules_for_guest_and_user():
    settings = Settings(_env_file=None, rate_guest_per_hour=10, rate_guest_per_day=30)

    guest = model_rules(settings, LimitSubject("guest:1.2.3.4", "guest"))
    user = model_rules(settings, LimitSubject("user:42", "user"))

    assert [(r.limit, r.period) for r in guest] == [(10, HOUR), (30, DAY)]
    assert [(r.limit, r.period) for r in user] == [(40, HOUR)]


def test_request_rules_default_to_120_per_minute():
    rules = request_rules(Settings(_env_file=None))

    assert [(r.limit, r.period) for r in rules] == [(120, 60)]


def make_request(headers: dict[str, str] | None = None, client=("9.9.9.9", 1234)) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": client, "method": "GET"})


def test_client_ip_uses_first_forwarded_for_value():
    request = make_request({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})

    assert client_ip(request) == "203.0.113.7"


@pytest.mark.parametrize("value", ["not-an-ip", "", "999.1.1.1", "<script>"])
def test_invalid_forwarded_for_falls_back_to_peer(value):
    assert client_ip(make_request({"X-Forwarded-For": value})) == "9.9.9.9"


def test_missing_client_is_unknown():
    assert client_ip(make_request(client=None)) == "unknown"


def test_guest_subject_combines_ip_and_cid_cookie():
    request = make_request({"Cookie": "cid=3f2a9c1e-77aa-4b1d-9c55-0a1b2c3d4e5f"})

    subject = limit_subject(request)

    assert subject == LimitSubject("guest:9.9.9.9:3f2a9c1e-77aa-4b1d-9c55-0a1b2c3d4e5f", "guest")


@pytest.mark.parametrize("cid", ["", "x" * 100, "bad value!", "a;b"])
def test_invalid_cid_is_ignored(cid):
    request = make_request({"Cookie": f"cid={cid}"})

    assert limit_subject(request).key == "guest:9.9.9.9"
