"""Public result envelope and validation diagnostics."""
from enum import StrEnum
from datetime import datetime, timezone
import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class FrozenDict(dict):
    """A JSON-serializable dictionary whose keys cannot change after creation."""
    def _immutable(self, *args, **kwargs):
        raise TypeError("model collections are immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable


def _freeze(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite number')
    if isinstance(value, dict):
        return FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    @model_validator(mode="after")
    def freeze_collections(self):
        for name in type(self).model_fields:
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        return self

    def model_copy(self, *, update=None, deep=False):
        """Revalidate copies so supplied collections remain immutable."""
        values = {name: getattr(self, name) for name in type(self).model_fields}
        if update:
            values.update(update)
        return type(self).model_validate(values)


class Status(StrEnum):
    ok = "ok"
    partial = "partial"
    no_results = "no_results"
    not_collected = "not_collected"
    disabled = "disabled"
    unconfigured = "unconfigured"
    unsupported = "unsupported"
    unavailable = "unavailable"
    rate_limited = "rate_limited"
    invalid_input = "invalid_input"
    conflict = "conflict"
    unknown = "unknown"


class Issue(FrozenModel):
    code: str
    message_key: str
    safe_params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


T = TypeVar("T")


class Result(FrozenModel, Generic[T]):
    schema_version: str = "1.0"
    status: Status
    data: T | None
    issues: tuple[Issue, ...] = Field(default_factory=list)
    evidence: tuple["Evidence", ...] = Field(default_factory=list)
    context: "RequestContext"









class Permission(StrEnum):
    allowed = "allowed"
    denied = "denied"
    unknown = "unknown"


class Rights(FrozenModel):
    use: Permission = Permission.unknown
    retain: Permission = Permission.unknown
    cache: Permission = Permission.unknown
    display: Permission = Permission.unknown
    export: Permission = Permission.unknown
    redistribute: Permission = Permission.unknown
    attribution: str | None = None
    license_url: str | None = None
    source_url: str | None = None
    checked_at: datetime | None = None
    permitted_purpose: str | None = None

    def allows(self, action: str, purpose: str) -> bool:
        """Unknown permission or mismatched purpose does not grant use."""
        if action not in ('use', 'retain', 'cache', 'display', 'export', 'redistribute'):
            raise ValueError('unknown permission')
        return getattr(self, action) == Permission.allowed and bool(purpose) and self.permitted_purpose == purpose

    @field_validator("checked_at")
    @classmethod
    def utc_checked_at(cls, value):
        return utc(value) if value else None


class Quality(FrozenModel):
    precision: str | None = None
    coverage: str | None = None
    freshness: str | None = None
    source_reliability: str | None = None
    uncertainty: str | None = None
    verification: str | None = None


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone offset")
    return value.astimezone(timezone.utc)


class Evidence(FrozenModel):
    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    retrieved_at: datetime
    reference_period: str | None = None
    valid_period: str | None = None
    method_version: str = Field(min_length=1)
    rights: Rights
    quality: Quality

    @field_validator("retrieved_at")
    @classmethod
    def utc_retrieved_at(cls, value):
        return utc(value)



class RequestContext(FrozenModel):
    request_id: str = Field(min_length=1)
    location_versions: dict[str, int] = Field(default_factory=dict)
    effective_conditions: dict[str, str] = Field(default_factory=dict)
    profile_ref: str | None = None
    template_ref: str | None = None
    method_version: str = "manual-v1"
    scope_token: str | None = None



Result.model_rebuild()
