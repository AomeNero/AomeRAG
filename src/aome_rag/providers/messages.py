"""中立内部消息 & 内容块模型（与具体 Provider 解耦）。"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

BlockType = Literal["text", "tool_use", "tool_result"]


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str  # provider-assigned; echoed in the matching ToolResultBlock
    name: str  # skill name
    arguments: dict[str, Any] = {}


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str  # skill.handle() returns str
    is_error: bool = False  # 解析失败时置 True，模型据此自我修正


Block = Annotated[Union[TextBlock, ToolUseBlock, ToolResultBlock], Field(discriminator="type")]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    blocks: list[Block] = []

    def as_text(self) -> str:
        return "".join(b.text for b in self.blocks if isinstance(b, TextBlock))

    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.blocks if isinstance(b, ToolUseBlock)]

    def tool_results(self) -> list[ToolResultBlock]:
        return [b for b in self.blocks if isinstance(b, ToolResultBlock)]

    @classmethod
    def text(cls, role: str, text: str) -> Message:
        return cls(role=role, blocks=[TextBlock(text=text)])  # type: ignore[arg-type]
