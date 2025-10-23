from datetime import datetime
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    id: str
    timestamp: datetime
    author: str
    content: str
    media_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Topic(BaseModel):
    id: str
    title: str
    messages: list[Message]
    summary: str | None = None
    relevance_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)


class Post(BaseModel):
    date: str
    title: str
    content: str
    topics: list[Topic]
    metadata: dict[str, Any] = Field(default_factory=dict)
    media: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    author: str
    slug: str
    message_count: int = 0
    topics: list[str] = Field(default_factory=list)
    summary: str | None = None
    activity: dict[str, Any] = Field(default_factory=dict)
