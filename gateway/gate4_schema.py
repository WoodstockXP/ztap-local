"""
Gate 4: Schema Conformance Validation.

Given that Gate 2 already authorized the action in principle, Gate 4 asks
a different question: are the specific arguments the agent generated
well-formed and safe? Cedar's decision does not inspect argument content,
so this gate covers three things per action: argument type validation,
regex string restriction (blocking injection-style characters), and
numerical bounds checking.
"""

import re
from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError, field_validator

_UNSAFE_STRING_PATTERN = re.compile(r"[;'\"]|(--)|(\.\./)")


class Gate4Denied(Exception):
    pass


class UpdateRecordArgs(BaseModel):
    record_id: str
    amount: float

    @field_validator("record_id")
    @classmethod
    def no_injection_chars(cls, v: str) -> str:
        if _UNSAFE_STRING_PATTERN.search(v):
            raise ValueError("record_id contains disallowed characters")
        return v

    @field_validator("amount")
    @classmethod
    def sane_bounds(cls, v: float) -> float:
        if v < 0 or v > 10_000:
            raise ValueError("amount out of allowed bounds (0-10000)")
        return v


class ReadRecordArgs(BaseModel):
    record_id: str

    @field_validator("record_id")
    @classmethod
    def no_injection_chars(cls, v: str) -> str:
        if _UNSAFE_STRING_PATTERN.search(v):
            raise ValueError("record_id contains disallowed characters")
        return v


ACTION_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "updateRecord": UpdateRecordArgs,
    "readRecord": ReadRecordArgs,
}


def evaluate_gate4(action: str, args: Dict[str, Any]) -> BaseModel:
    schema = ACTION_SCHEMAS.get(action)
    if schema is None:
        raise Gate4Denied(f"No schema registered for action '{action}'")
    try:
        return schema(**args)
    except ValidationError as exc:
        raise Gate4Denied(str(exc)) from exc