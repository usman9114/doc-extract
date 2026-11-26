"""Strict output schema. Change this one file to adapt to another document type."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = ""
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = Field(None, description="Line total as printed")

    @field_validator("description", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return "" if v is None else v


class Document(BaseModel):
    model_config = ConfigDict(extra="ignore")
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    date: Optional[str] = Field(None, description="ISO 8601, YYYY-MM-DD")
    invoice_number: Optional[str] = None
    currency: Optional[str] = Field(None, description="ISO 4217 code, e.g. USD, IDR")
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    discount: Optional[float] = None
    service_charge: Optional[float] = None
    total: Optional[float] = None
    line_items: list[LineItem] = Field(default_factory=list)


class Issue(BaseModel):
    field: str
    rule: str
    message: str


class Validation(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
    needs_review: bool = False
    confidence: float = 1.0

    @property
    def bad_fields(self) -> set[str]:
        return {i.field for i in self.issues}


class Result(BaseModel):
    document: Document
    validation: Validation
    mode: str
    model: str
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    attempts: int = 1
