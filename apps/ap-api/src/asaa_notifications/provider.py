"""Notification delivery adapter contract and an in-memory mock. No real channel (email/SMS/chat) is configured."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Callable

from asaa_identity.provider import PermanentProviderError, TransientProviderError  # same error taxonomy


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, channel: str, recipient_subject: str, subject: str, body: str, message_id: str) -> None:
        """Deliver one message. `message_id` lets the provider de-duplicate retries. Raise TransientProviderError to retry,
        PermanentProviderError to dead-letter."""


class InMemoryNotificationProvider(NotificationProvider):
    def __init__(self):
        self.sent: list[dict] = []
        self._faults: deque = deque()

    def fail_next(self, count: int = 1, kind: str = "transient"):
        self._faults.extend([kind] * count)

    def send(self, channel, recipient_subject, subject, body, message_id):
        if self._faults:
            kind = self._faults.popleft()
            raise (TransientProviderError if kind == "transient" else PermanentProviderError)(f"injected {kind} failure")
        if any(m["message_id"] == message_id for m in self.sent):
            return  # provider-side de-duplication of retried sends
        self.sent.append({"channel": channel, "to": recipient_subject, "subject": subject, "body": body, "message_id": message_id})


_FACTORIES: dict[str, Callable[[], NotificationProvider]] = {}
_INSTANCES: dict[str, NotificationProvider] = {}


def register_notification_provider(name: str, factory: Callable[[], NotificationProvider]) -> None:
    _FACTORIES[name] = factory
    _INSTANCES.pop(name, None)


def resolve_notification_provider(name: str) -> NotificationProvider | None:
    if name not in _FACTORIES:
        return None
    return _INSTANCES.setdefault(name, _FACTORIES[name]()) if name not in _INSTANCES else _INSTANCES[name]
