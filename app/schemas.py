"""Request and response models."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Status = Literal["applied", "interview", "offer", "rejected"]
STATUSES: tuple[str, ...] = ("applied", "interview", "offer", "rejected")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    created_at: str


class ApplicationIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    link: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=2000)
    status: Status = "applied"
    applied_on: date

    @field_validator("company", "role", "link", "location", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("applied_on")
    @classmethod
    def not_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("applied_on cannot be in the future")
        return value


class ApplicationOut(BaseModel):
    id: int
    company: str
    role: str
    link: str
    location: str
    notes: str
    status: Status
    applied_on: str
    created_at: str
    updated_at: str


class Stats(BaseModel):
    total: int
    applied: int
    interview: int
    offer: int
    rejected: int
    response_rate: float
    offer_rate: float
    last_7_days: int
