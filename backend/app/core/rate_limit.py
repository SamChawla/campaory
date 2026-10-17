"""In-memory token buckets and a global daily model cap (ADR-008).

One process, one instance: state resets on deploy. The clock is injectable for tests.
Who is limited is decided by `limit_subject`, a single dependency so signed-in users can be
keyed by user id later without touching the endpoints.
"""

import ipaddress
import math
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import OptionalUser

Clock = Callable[[], float]
HOUR = 3600.0
DAY = 86400.0
MINUTE = 60.0
GUEST_IP_FACTOR = 3
_CID = re.compile(r"[A-Za-z0-9-]{8,64}")


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int
    period: float
    key: str | None = None  # charge this bucket key instead of the caller's key

    @property
    def rate(self) -> float:
        return self.limit / self.period


@dataclass(frozen=True)
class LimitSubject:
    key: str
    kind: Literal["guest", "user"]
    ip: str | None = None


class RateLimited(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            429, "rate_limited", f"Try again in {_wait_text(retry_after)}.",
            retry_after_seconds=retry_after,
        )  # fmt: skip


def _wait_text(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second" + ("" if seconds == 1 else "s")
    minutes = math.ceil(seconds / 60)
    if minutes <= 120:
        return f"{minutes} minute" + ("" if minutes == 1 else "s")
    hours = math.ceil(minutes / 60)
    return f"{hours} hours"


@dataclass
class _Bucket:
    tokens: float
    updated: float
    rule: Rule

    def refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(float(self.rule.limit), self.tokens + elapsed * self.rule.rate)
        self.updated = now


class RateLimiter:
    def __init__(self, *, clock: Clock = time.time, max_keys: int = 50_000) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    def size(self) -> int:
        return len(self._buckets)

    def hit(self, key: str, rules: Sequence[Rule], cost: int = 1) -> None:
        """Take `cost` from every rule's bucket, or raise RateLimited and take nothing."""
        now = self._clock()
        buckets = [self._bucket(key, rule, now) for rule in rules]
        wait = max(
            ((cost - b.tokens) / b.rule.rate for b in buckets if b.tokens < cost), default=0.0
        )
        if wait > 0:
            raise RateLimited(max(1, math.ceil(wait - 1e-6)))
        for bucket in buckets:
            bucket.tokens -= cost

    def _bucket(self, key: str, rule: Rule, now: float) -> _Bucket:
        ident = (rule.key or key, rule.name)
        bucket = self._buckets.get(ident)
        if bucket is None or bucket.rule != rule:
            if len(self._buckets) >= self._max_keys:
                self._prune(now)
            bucket = self._buckets[ident] = _Bucket(float(rule.limit), now, rule)
        else:
            bucket.refill(now)
        return bucket

    def _prune(self, now: float) -> None:
        """Drop buckets that have refilled completely; they hold no information."""
        for ident, bucket in list(self._buckets.items()):
            bucket.refill(now)
            if bucket.tokens >= bucket.rule.limit:
                del self._buckets[ident]


class DailyCap:
    """Global count of model calls per UTC day."""

    def __init__(self, limit: int, *, clock: Clock = time.time) -> None:
        self._limit = limit
        self._clock = clock
        self._day = ""
        self._used = 0

    def _roll(self) -> None:
        day = datetime.fromtimestamp(self._clock(), UTC).date().isoformat()
        if day != self._day:
            self._day, self._used = day, 0

    def remaining(self) -> int:
        self._roll()
        return max(0, self._limit - self._used)

    def take(self) -> bool:
        self._roll()
        if self._used >= self._limit:
            return False
        self._used += 1
        return True


def model_rules(settings: Settings, subject: LimitSubject) -> list[Rule]:
    if subject.kind == "user":
        return [Rule("hour", settings.rate_user_per_hour, HOUR)]
    rules = [
        Rule("hour", settings.rate_guest_per_hour, HOUR),
        Rule("day", settings.rate_guest_per_day, DAY),
    ]
    if subject.ip:
        # A fresh cid cookie per request must not mean unlimited calls from one address.
        ip_key = f"guest-ip:{subject.ip}"
        rules += [
            Rule("hour", settings.rate_guest_per_hour * GUEST_IP_FACTOR, HOUR, ip_key),
            Rule("day", settings.rate_guest_per_day * GUEST_IP_FACTOR, DAY, ip_key),
        ]
    return rules


def request_rules(settings: Settings) -> list[Rule]:
    return [Rule("minute", settings.rate_ip_per_minute, MINUTE)]


def client_ip(request: Request) -> str:
    """First X-Forwarded-For value (set by Render's proxy) if it is an IP, else the peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        try:
            return str(ipaddress.ip_address(first))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


def guest_subject(request: Request) -> LimitSubject:
    """Guests are keyed by IP plus the `cid` cookie when it is valid."""
    ip = client_ip(request)
    key = f"guest:{ip}"
    cid = request.cookies.get("cid", "")
    if _CID.fullmatch(cid):
        key += f":{cid}"
    return LimitSubject(key, "guest", ip)


def limit_subject(request: Request, user: OptionalUser) -> LimitSubject:
    """Who a model call is charged to: the signed-in user, else the guest. One dependency."""
    if user is not None:
        return LimitSubject(f"user:{user.id}", "user")
    return guest_subject(request)
