"""Shared types for MCP Relay Server."""

from dataclasses import dataclass

MAX_READ_LIMIT = 200


@dataclass
class Message:
    id: str
    channel: str
    sender: str
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "channel": self.channel,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class ChannelInfo:
    name: str
    message_count: int
    last_activity: str | None
