"""Pydantic models for Layer 1 parser output.

Single source of truth for the JSON shape described in docs/data_flow.md
(Stage 1 — Parser Output). All downstream layers import from here.
"""

from datetime import datetime
from typing import Union

from pydantic import BaseModel


class RowFlags(BaseModel):
    existing_equipment: bool = False
    not_in_total: bool = False
    optional: bool = False
    math_error: bool = False


class ParsedRow(BaseModel):
    row_index: int
    description: str
    unit: str
    quantity: float
    unit_price: Union[float, str]  # str when e.g. "ציוד קיים"
    total_price: Union[float, str]  # str when e.g. "לא לסיכום"
    manufacturer_model: str
    mkt_raw: str
    notes: str
    flags: RowFlags


class ParsedSheet(BaseModel):
    sheet_name: str
    rows: list[ParsedRow]
    sheet_total: float


class FileMeta(BaseModel):
    contractor_id: str
    file_name: str
    project_id: str
    parsed_at: datetime


class ParsedFile(BaseModel):
    meta: FileMeta
    sheets: list[ParsedSheet]
