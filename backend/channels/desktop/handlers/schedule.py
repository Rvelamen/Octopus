"""Schedule (Calendar) event handlers for Desktop channel."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.schemas import (
    ScheduleCancelEventRequest,
    ScheduleCreateEventRequest,
    ScheduleDeleteEventRequest,
    ScheduleGetEventRequest,
    ScheduleListEventsRequest,
    ScheduleSearchEventsRequest,
    ScheduleUncancelEventRequest,
    ScheduleUpdateEventRequest,
)
from backend.core.events.bus import MessageBus


def _event_to_dict(ev) -> dict:
    d = ev.to_dict()
    try:
        from datetime import datetime

        d["start_iso"] = datetime.fromtimestamp(ev.start_at_ms / 1000).strftime(
            "%Y-%m-%d %H:%M"
        )
        d["end_iso"] = datetime.fromtimestamp(ev.end_at_ms / 1000).strftime(
            "%Y-%m-%d %H:%M"
        )
    except Exception:
        pass
    return d


class _ScheduleHandlerBase(MessageHandler):
    """Shared helpers for schedule handlers."""

    def __init__(self, bus: MessageBus, schedule_service=None):
        super().__init__(bus)
        self.schedule_service = schedule_service

    async def _send_error(
        self, websocket: WebSocket, request_id: str | None, error: str
    ) -> None:
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.ERROR,
                request_id=request_id,
                data={"error": error},
            ),
        )

    def _require_service(self) -> bool:
        return self.schedule_service is not None


class ScheduleListEventsHandler(_ScheduleHandlerBase):
    """Handle schedule_list_events requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            start_at_ms = int(message.data.get("start_at_ms", 0))
            end_at_ms = int(message.data.get("end_at_ms", 0))
            if end_at_ms <= start_at_ms:
                await self._send_error(
                    websocket, message.request_id, "end_at_ms must be > start_at_ms"
                )
                return
            events = self.schedule_service.list_events(start_at_ms, end_at_ms)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENTS,
                    request_id=message.request_id,
                    data={"events": [_event_to_dict(e) for e in events]},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to list schedule events: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleListEventsRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if validated.end_at_ms <= validated.start_at_ms:
                await self._send_error(
                    websocket, message.request_id, "end_at_ms must be > start_at_ms"
                )
                return
            events = self.schedule_service.list_events(
                validated.start_at_ms, validated.end_at_ms
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENTS,
                    request_id=message.request_id,
                    data={"events": [_event_to_dict(e) for e in events]},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to list schedule events: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleCreateEventHandler(_ScheduleHandlerBase):
    """Handle schedule_create_event requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            ev = self.schedule_service.create_event(
                title=message.data.get("title", ""),
                start_at_ms=int(message.data.get("start_at_ms", 0)),
                end_at_ms=int(message.data.get("end_at_ms", 0)),
                all_day=bool(message.data.get("all_day", False)),
                location=message.data.get("location", "") or "",
                description=message.data.get("description", "") or "",
                color=message.data.get("color", "#4F8EF7") or "#4F8EF7",
            )
            await self.schedule_service.publish_change("created", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_CREATED,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except ValueError as e:
            await self._send_error(websocket, message.request_id, str(e))
        except Exception as e:
            logger.error(f"Failed to create schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleCreateEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            ev = self.schedule_service.create_event(
                title=validated.title,
                start_at_ms=validated.start_at_ms,
                end_at_ms=validated.end_at_ms,
                all_day=validated.all_day,
                location=validated.location,
                description=validated.description,
                color=validated.color or "#4F8EF7",
            )
            await self.schedule_service.publish_change("created", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_CREATED,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except ValueError as e:
            await self._send_error(websocket, message.request_id, str(e))
        except Exception as e:
            logger.error(f"Failed to create schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleUpdateEventHandler(_ScheduleHandlerBase):
    """Handle schedule_update_event requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            event_id = int(message.data.get("event_id", 0))
            if not event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.update_event(
                event_id=event_id,
                title=message.data.get("title"),
                start_at_ms=message.data.get("start_at_ms"),
                end_at_ms=message.data.get("end_at_ms"),
                all_day=message.data.get("all_day"),
                location=message.data.get("location"),
                description=message.data.get("description"),
                color=message.data.get("color"),
            )
            if ev is None:
                await self._send_error(
                    websocket, message.request_id, f"Event {event_id} not found"
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_UPDATED,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except ValueError as e:
            await self._send_error(websocket, message.request_id, str(e))
        except Exception as e:
            logger.error(f"Failed to update schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleUpdateEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if not validated.event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.update_event(
                event_id=validated.event_id,
                title=validated.title,
                start_at_ms=validated.start_at_ms,
                end_at_ms=validated.end_at_ms,
                all_day=validated.all_day,
                location=validated.location,
                description=validated.description,
                color=validated.color,
            )
            if ev is None:
                await self._send_error(
                    websocket,
                    message.request_id,
                    f"Event {validated.event_id} not found",
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_UPDATED,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except ValueError as e:
            await self._send_error(websocket, message.request_id, str(e))
        except Exception as e:
            logger.error(f"Failed to update schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleDeleteEventHandler(_ScheduleHandlerBase):
    """Handle schedule_delete_event requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            event_id = int(message.data.get("event_id", 0))
            if not event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ok = self.schedule_service.delete_event(event_id)
            if ok:
                await self.schedule_service.publish_change("deleted", event_id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_DELETED,
                    request_id=message.request_id,
                    data={"success": ok, "event_id": event_id},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleDeleteEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if not validated.event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ok = self.schedule_service.delete_event(validated.event_id)
            if ok:
                await self.schedule_service.publish_change("deleted", validated.event_id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT_DELETED,
                    request_id=message.request_id,
                    data={"success": ok, "event_id": validated.event_id},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleSearchEventsHandler(_ScheduleHandlerBase):
    """Handle schedule_search_events requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            query = message.data.get("query", "")
            start = message.data.get("start_at_ms")
            end = message.data.get("end_at_ms")
            if (start is None) != (end is None):
                await self._send_error(
                    websocket,
                    message.request_id,
                    "Provide both start_at_ms and end_at_ms, or neither",
                )
                return
            events = self.schedule_service.search_events(
                query=query, start_ms=start, end_ms=end
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENTS,
                    request_id=message.request_id,
                    data={"events": [_event_to_dict(e) for e in events]},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to search schedule events: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleSearchEventsRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            events = self.schedule_service.search_events(
                query=validated.query,
                start_ms=validated.start_at_ms,
                end_ms=validated.end_at_ms,
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENTS,
                    request_id=message.request_id,
                    data={"events": [_event_to_dict(e) for e in events]},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to search schedule events: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleGetEventHandler(_ScheduleHandlerBase):
    """Handle schedule_get_event requests (fetch one event by id)."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            event_id = int(message.data.get("event_id", 0))
            if not event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.get_event(event_id)
            if ev is None:
                await self._send_error(
                    websocket, message.request_id, f"Event {event_id} not found"
                )
                return
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleGetEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if not validated.event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.get_event(validated.event_id)
            if ev is None:
                await self._send_error(
                    websocket,
                    message.request_id,
                    f"Event {validated.event_id} not found",
                )
                return
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to get schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleCancelEventHandler(_ScheduleHandlerBase):
    """Handle schedule_cancel_event requests (reversible cancellation)."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            event_id = int(message.data.get("event_id", 0))
            if not event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.cancel_event(event_id)
            if ev is None:
                await self._send_error(
                    websocket, message.request_id, f"Event {event_id} not found"
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to cancel schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleCancelEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if not validated.event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.cancel_event(validated.event_id)
            if ev is None:
                await self._send_error(
                    websocket,
                    message.request_id,
                    f"Event {validated.event_id} not found",
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to cancel schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class ScheduleUncancelEventHandler(_ScheduleHandlerBase):
    """Handle schedule_uncancel_event requests (restore a cancelled event)."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            event_id = int(message.data.get("event_id", 0))
            if not event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.uncancel_event(event_id)
            if ev is None:
                await self._send_error(
                    websocket, message.request_id, f"Event {event_id} not found"
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to restore schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def handle_validated(
        self,
        websocket: WebSocket,
        message: WSMessage,
        validated: ScheduleUncancelEventRequest,
    ) -> None:
        try:
            if not self._require_service():
                await self._send_error(
                    websocket, message.request_id, "Schedule service not available"
                )
                return
            if not validated.event_id:
                await self._send_error(
                    websocket, message.request_id, "event_id is required"
                )
                return
            ev = self.schedule_service.uncancel_event(validated.event_id)
            if ev is None:
                await self._send_error(
                    websocket,
                    message.request_id,
                    f"Event {validated.event_id} not found",
                )
                return
            await self.schedule_service.publish_change("updated", ev.id)
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.SCHEDULE_EVENT,
                    request_id=message.request_id,
                    data={"success": True, "event": _event_to_dict(ev)},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to restore schedule event: {e}")
            await self._send_error(websocket, message.request_id, str(e))
