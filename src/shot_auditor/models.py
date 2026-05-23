from __future__ import annotations

from pydantic import BaseModel, computed_field, field_validator


class Shot(BaseModel):
    shotID: str
    period: int
    shotClockSeconds: float
    gameClockSeconds: float
    fg2Attempted: int
    fg2Made: int
    fg3Attempted: int
    fg3Made: int
    ftAttempted: int
    ftMade: int
    points: int

    @field_validator("period")
    @classmethod
    def period_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("period must be >= 1")
        return v


class ValidationResult(BaseModel):
    shot_id: str
    errors: list[str]

    @computed_field
    @property
    def is_faulty(self) -> bool:
        return len(self.errors) > 0
