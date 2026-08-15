"""Markdown block AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InlineRun:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    url: str | None = None


@dataclass
class Block:
    type: str
    text: str = ""
    region: list[str] = field(default_factory=list)
    ordered: bool = False
    list_number: int | None = None
    list_level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    image_alt: str = ""
    image_path: str = ""
    code_lang: str = ""
    anchor: str = ""
    line_no: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "region": list(self.region),
        }
        if self.text:
            data["text"] = self.text
        if self.type == "list":
            data["ordered"] = self.ordered
            data["list_level"] = self.list_level
            if self.list_number is not None:
                data["list_number"] = self.list_number
        if self.rows:
            data["rows"] = self.rows
        if self.image_path:
            data["image_alt"] = self.image_alt
            data["image_path"] = self.image_path
        if self.code_lang:
            data["code_lang"] = self.code_lang
        if self.anchor:
            data["anchor"] = self.anchor
        if self.line_no is not None:
            data["line_no"] = self.line_no
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        return cls(
            type=data["type"],
            text=data.get("text", ""),
            region=list(data.get("region", [])),
            ordered=bool(data.get("ordered", False)),
            list_number=data.get("list_number"),
            list_level=int(data.get("list_level", 0)),
            rows=[list(row) for row in data.get("rows", [])],
            image_alt=data.get("image_alt", ""),
            image_path=data.get("image_path", ""),
            code_lang=data.get("code_lang", ""),
            anchor=data.get("anchor", ""),
            line_no=data.get("line_no"),
        )
