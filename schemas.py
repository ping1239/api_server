from __future__ import annotations

import json
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ReferenceResultConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["reference_result"]
    reference_case: Literal["dogbone"]
    client_job_id: str | None = Field(default=None, max_length=200)

    @field_validator("client_job_id")
    @classmethod
    def non_blank_client_job_id(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("client_job_id must not be blank")
        return value


def parse_reference_config(raw_config: str) -> ReferenceResultConfig:
    try:
        decoded = json.loads(raw_config)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="config_json is not valid JSON") from exc

    if not isinstance(decoded, dict):
        raise HTTPException(status_code=422, detail="config_json must decode to an object")

    try:
        return ReferenceResultConfig.model_validate(decoded)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_context=False, include_url=False),
        ) from exc
