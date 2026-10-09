import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  X,
  Trash2,
  MessageSquare,
  Send,
  RefreshCw,
  RotateCcw,
  Ban,
} from 'lucide-react';
import dayjs from 'dayjs';
import WindowDots from '@components/layout/WindowDots';
import Toast from '@components/ui/Toast';
import './SchedulePanel.css';

const COLOR_SWATCHES = [
  '#4F8EF7',
  '#F76D6D',
  '#54C282',
  '#F7B84F',
  '#A26DD1',
  '#4FD4D1',
];

// ---------- Date helpers ----------

function startOfDay(d) {
  return d.startOf('day');
}

function endOfDay(d) {
  return d.endOf('day');
}

function startOfWeek(d) {
  return d.startOf('week');
}

function endOfWeek(d) {
  return d.endOf('week');
}

function startOfMonth(d) {
  return d.startOf('month').startOf('week');
}

function endOfMonth(d) {
  return d.endOf('month').endOf('week');
}

function visibleRange(view, cursor) {
  if (view === 'day') {
    return [startOfDay(cursor), endOfDay(cursor)];
  }
  if (view === 'week') {
    return [startOfWeek(cursor), endOfWeek(cursor)];
  }
  // month — include overflow weeks
  return [startOfMonth(cursor), endOfMonth(cursor)];
}

function shiftCursor(view, cursor, dir) {
  if (view === 'day') return cursor.add(dir, 'day');
  if (view === 'week') return cursor.add(dir, 'week');
  return cursor.add(dir, 'month');
}

function formatTime(ms) {
  return dayjs(ms).format('HH:mm');
}

function formatDate(d) {
  if (d.month() === dayjs().month() && d.year() === dayjs().year()) {
    return d.format('MMMM YYYY');
  }
  return d.format('MMM YYYY');
}

// ---------- Month View ----------

function MonthView({ cursor, events, onSelectEvent, onCreateAt, onShowMore }) {
  const { t } = useTranslation();
  const start = startOfMonth(cursor);
  const end = endOfMonth(cursor);
  const days = [];
  let d = start;
  while (d.isBefore(end) || d.isSame(end, 'day')) {
    days.push(d);
    d = d.add(1, 'day');
  }
  const today = dayjs();
  const weekdayKeys = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

  return (
    <div className="month-grid">
      {weekdayKeys.map((k) => (
        <div key={k} className="month-weekday-header">{t(`schedule.weekday.${k}`)}</div>
      ))}
      {days.map((day) => {
        const isOutside = day.month() !== cursor.month();
        const isToday = day.isSame(today, 'day');
        const dayStart = day.startOf('day').valueOf();
        const dayEnd = day.endOf('day').valueOf();
        const dayEvents = events
          .filter(
            (e) => e.start_at_ms < dayEnd && e.end_at_ms > dayStart
          )
          .sort((a, b) => a.start_at_ms - b.start_at_ms);
        const visible = dayEvents.slice(0, 4);
        const more = dayEvents.length - visible.length;

        return (
          <div
            key={day.format('YYYY-MM-DD')}
            className={`month-cell${isOutside ? ' outside-month' : ''}${isToday ? ' is-today' : ''}`}
            onClick={(e) => {
              if (e.target.classList.contains('month-event')) return;
              if (e.target.closest('.month-more')) return;
              onCreateAt(day);
            }}
          >
            <div className="month-day-header">
              {day.date() === 1 && (
                <span className="month-day-month">{day.format('MMMM')}</span>
              )}
              <span className="month-day-num">{day.date()}</span>
            </div>
            <div className="month-events">
              {visible.map((ev) => (
                <div
                  key={ev.id}
                  className={`month-event${ev.all_day ? ' all-day' : ''}${ev.cancelled ? ' cancelled' : ''}`}
                  style={{ borderLeftColor: ev.color }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectEvent(ev);
                  }}
                >
                  <span
                    className="month-event-color-dot"
                    style={{ background: ev.color }}
                  />
                  <span>{ev.all_day ? '' : formatTime(ev.start_at_ms) + ' '}{ev.title}</span>
                  {ev.cancelled && (
                    <span className="month-event-cancelled-tag">
                      {t('schedule.modal.cancelled', { defaultValue: '已取消' })}
                    </span>
                  )}
                </div>
              ))}
              {more > 0 && (
                <div
                  className="month-more"
                  onClick={(e) => {
                    e.stopPropagation();
                    onShowMore(day, dayEvents, e.currentTarget);
                  }}
                >
                  {t('schedule.more', { count: more })}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Day Events Popover ----------

function DayEventsPopover({ day, events, anchor, onSelectEvent, onCreateAt, onClose }) {
  const { t } = useTranslation();
  const popoverRef = useRef(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  // Position the popover near the anchor cell, clamped to the viewport so it
  // never overflows off-screen even when the cell is near an edge.
  useEffect(() => {
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    const popW = 280;
    const popH = 320;
    const margin = 8;
    let top = rect.bottom + margin;
    let left = rect.left;
    if (left + popW > window.innerWidth - margin) {
      left = Math.max(margin, window.innerWidth - popW - margin);
    }
    if (top + popH > window.innerHeight - margin) {
      // Flip above the anchor when there isn't room below.
      top = Math.max(margin, rect.top - popH - margin);
    }
    setPos({ top, left });
  }, [anchor]);

  // Click outside / Escape closes the popover
  useEffect(() => {
    const onDocClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target) && !anchor?.contains(e.target)) {
        onClose();
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [anchor, onClose]);

  if (!day || !events) return null;

  return (
    <div
      ref={popoverRef}
      className="day-events-popover pixel-border"
      style={{ top: `${pos.top}px`, left: `${pos.left}px` }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="day-events-popover-header">
        <span className="day-events-popover-title">
          {day.format('YYYY-MM-DD dddd')}
        </span>
        <button className="dialog-close" onClick={onClose} title={t('common.cancel', { defaultValue: 'Close' })}>
          <X size={14} />
        </button>
      </div>
      <div className="day-events-popover-list">
        {events.map((ev) => (
          <div
            key={ev.id}
            className={`day-events-popover-item${ev.cancelled ? ' cancelled' : ''}`}
            style={{ borderLeftColor: ev.color }}
            onClick={() => {
              onSelectEvent(ev);
              onClose();
            }}
          >
            <div className="day-events-popover-item-time">
              {ev.all_day ? t('schedule.modal.allDay', { defaultValue: 'All day' }) : `${formatTime(ev.start_at_ms)} – ${formatTime(ev.end_at_ms)}`}
            </div>
            <div className="day-events-popover-item-title">
              <span
                className="month-event-color-dot"
                style={{ background: ev.color }}
              />
              {ev.title}
              {ev.cancelled && (
                <span className="month-event-cancelled-tag">
                  {t('schedule.modal.cancelled', { defaultValue: '已取消' })}
                </span>
              )}
            </div>
            {ev.location && (
              <div className="day-events-popover-item-location">{ev.location}</div>
            )}
          </div>
        ))}
      </div>
      <div className="day-events-popover-footer">
        <button
          className="pixel-button"
          onClick={() => {
            onCreateAt(day);
            onClose();
          }}
        >
          <Plus size={12} /> {t('schedule.modal.new')}
        </button>
      </div>
    </div>
  );
}

// ---------- Week View ----------

function WeekView({ cursor, events, onSelectEvent, onCreateAt }) {
  const start = startOfWeek(cursor);
  const days = Array.from({ length: 7 }, (_, i) => start.add(i, 'day'));
  const today = dayjs();
  const hours = Array.from({ length: 18 }, (_, i) => i + 6); // 6:00 - 23:00

  return (
    <>
      <div className="weekday-headers">
        <div className="weekday-header-cell" />
        {days.map((d) => (
          <div
            key={d.format('YYYY-MM-DD')}
            className={`weekday-header-cell${d.isSame(today, 'day') ? ' is-today' : ''}`}
          >
            {d.format('ddd')} {d.date()}
          </div>
        ))}
      </div>
      <div className="timegrid">
        <div>
          {hours.map((h) => (
            <div key={h} className="timegrid-hour-label">
              {String(h).padStart(2, '0')}:00
            </div>
          ))}
        </div>
        {days.map((d) => {
          const colStart = d.startOf('day');
          const colEvents = events
            .filter(
              (e) => e.start_at_ms < colStart.add(1, 'day').valueOf() && e.end_at_ms > colStart.valueOf()
            )
            .filter((e) => !e.all_day);
          return (
            <div key={d.format('YYYY-MM-DD')} className="timegrid-col">
              {hours.map((h) => (
                <div
                  key={h}
                  className="timegrid-cell"
                  onClick={() => onCreateAt(colStart.hour(h).startOf('hour'))}
                />
              ))}
              {colEvents.map((ev) => {
                const start = dayjs(ev.start_at_ms);
                const end = dayjs(ev.end_at_ms);
                const dayStart = colStart.hour(6);
                const startMin = Math.max(0, start.diff(dayStart, 'minute'));
                const endMin = Math.min(18 * 60, end.diff(dayStart, 'minute'));
                const top = (startMin / 60) * 60; // px (60px per hour)
                const height = Math.max(20, ((endMin - startMin) / 60) * 60 - 2);
                return (
                  <div
                    key={ev.id}
                    className={`timegrid-event${ev.cancelled ? ' cancelled' : ''}`}
                    style={{
                      top: `${top}px`,
                      height: `${height}px`,
                      borderLeftColor: ev.color,
                    }}
                    onClick={() => onSelectEvent(ev)}
                  >
                    <div className="timegrid-event-title">{ev.title}</div>
                    <div className="timegrid-event-time">
                      {start.format('HH:mm')} – {end.format('HH:mm')}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </>
  );
}

// ---------- Day View ----------

function DayView({ cursor, events, onSelectEvent, onCreateAt }) {
  const today = dayjs();
  const hours = Array.from({ length: 18 }, (_, i) => i + 6);
  const colStart = cursor.startOf('day');
  const colEvents = events
    .filter(
      (e) => e.start_at_ms < colStart.add(1, 'day').valueOf() && e.end_at_ms > colStart.valueOf()
    )
    .filter((e) => !e.all_day);

  return (
    <>
      <div className="weekday-headers day-view">
        <div className="weekday-header-cell" />
        <div className={`weekday-header-cell${cursor.isSame(today, 'day') ? ' is-today' : ''}`}>
          {cursor.format('dddd, MMMM D')}
        </div>
      </div>
      <div className="timegrid day-view">
        <div>
          {hours.map((h) => (
            <div key={h} className="timegrid-hour-label">
              {String(h).padStart(2, '0')}:00
            </div>
          ))}
        </div>
        <div className="timegrid-col">
          {hours.map((h) => (
            <div
              key={h}
              className="timegrid-cell"
              onClick={() => onCreateAt(colStart.hour(h).startOf('hour'))}
            />
          ))}
          {colEvents.map((ev) => {
            const start = dayjs(ev.start_at_ms);
            const end = dayjs(ev.end_at_ms);
            const dayStart = colStart.hour(6);
            const startMin = Math.max(0, start.diff(dayStart, 'minute'));
            const endMin = Math.min(18 * 60, end.diff(dayStart, 'minute'));
            const top = (startMin / 60) * 60;
            const height = Math.max(20, ((endMin - startMin) / 60) * 60 - 2);
            return (
              <div
                key={ev.id}
                className={`timegrid-event${ev.cancelled ? ' cancelled' : ''}`}
                style={{
                  top: `${top}px`,
                  height: `${height}px`,
                  borderLeftColor: ev.color,
                }}
                onClick={() => onSelectEvent(ev)}
              >
                <div className="timegrid-event-title">{ev.title}</div>
                <div className="timegrid-event-time">
                  {start.format('HH:mm')} – {end.format('HH:mm')}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ---------- Event Modal ----------

function EventModal({ event, defaultStart, onSave, onDelete, onCancelEvent, onUncancelEvent, onClose }) {
  const { t } = useTranslation();
  const isEdit = !!event;
  const isCancelled = isEdit && event.cancelled;
  const [form, setForm] = useState(() => {
    if (event) {
      return {
        title: event.title,
        start: dayjs(event.start_at_ms),
        end: dayjs(event.end_at_ms),
        all_day: !!event.all_day,
        location: event.location || '',
        description: event.description || '',
        color: event.color || COLOR_SWATCHES[0],
      };
    }
    const start = defaultStart || dayjs();
    return {
      title: '',
      start,
      end: start.add(1, 'hour'),
      all_day: false,
      location: '',
      description: '',
      color: COLOR_SWATCHES[0],
    };
  });

  const handleSave = () => {
    if (!form.title.trim()) return;
    const startMs = form.start.valueOf();
    let endMs = form.end.valueOf();
    if (endMs <= startMs) endMs = startMs + 30 * 60 * 1000;
    onSave({
      title: form.title.trim(),
      start_at_ms: startMs,
      end_at_ms: endMs,
      all_day: form.all_day,
      location: form.location,
      description: form.description,
      color: form.color,
    });
  };

  return (
    <div className="event-modal-overlay" onClick={onClose}>
      <div className={`event-modal pixel-border${isCancelled ? ' is-cancelled' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <WindowDots />
          <span className="modal-title">
            {isCancelled && (
              <span className="modal-cancelled-badge">
                {t('schedule.modal.cancelled', { defaultValue: '已取消' })}
              </span>
            )}
            {isEdit ? t('schedule.modal.edit') : t('schedule.modal.new')}
          </span>
          <button className="dialog-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        {isCancelled && (
          <div className="modal-cancelled-banner">
            {t('schedule.modal.cancelledHint', {
              defaultValue: '此日程已标记为取消，可恢复或彻底删除',
            })}
          </div>
        )}
        <div className="modal-body">
          <div className="form-group">
            <label>{t('schedule.modal.title')}</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="pixel-input modal-input-title"
              placeholder={t('schedule.modal.titlePlaceholder')}
              autoFocus
              disabled={isCancelled}
            />
          </div>
          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={form.all_day}
                onChange={(e) => setForm({ ...form, all_day: e.target.checked })}
                disabled={isCancelled}
              />{' '}
              {t('schedule.modal.allDay')}
            </label>
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.start')}</label>
            <input
              type="datetime-local"
              className="pixel-input"
              value={form.start.format('YYYY-MM-DDTHH:mm')}
              onChange={(e) => setForm({ ...form, start: dayjs(e.target.value) })}
              disabled={isCancelled}
            />
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.end')}</label>
            <input
              type="datetime-local"
              className="pixel-input"
              value={form.end.format('YYYY-MM-DDTHH:mm')}
              onChange={(e) => setForm({ ...form, end: dayjs(e.target.value) })}
              disabled={isCancelled}
            />
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.location')}</label>
            <input
              type="text"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              className="pixel-input"
              placeholder={t('schedule.modal.locationPlaceholder')}
              disabled={isCancelled}
            />
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.description')}</label>
            <textarea
              className="pixel-textarea"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              placeholder={t('schedule.modal.descriptionPlaceholder')}
              disabled={isCancelled}
            />
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.color')}</label>
            <div className="color-swatches">
              {COLOR_SWATCHES.map((c) => (
                <div
                  key={c}
                  className={`color-swatch${form.color === c ? ' selected' : ''}`}
                  style={{ background: c }}
                  onClick={() => setForm({ ...form, color: c })}
                />
              ))}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          {isEdit && isCancelled && (
            <button
              className="pixel-button secondary"
              onClick={() => onUncancelEvent(event.id)}
            >
              <RotateCcw size={14} /> {t('schedule.modal.uncancel', { defaultValue: '恢复' })}
            </button>
          )}
          {isEdit && !isCancelled && (
            <button
              className="pixel-button secondary"
              onClick={() => onCancelEvent(event.id)}
            >
              <Ban size={14} /> {t('schedule.modal.cancelSchedule', { defaultValue: '取消日程' })}
            </button>
          )}
          {isEdit && (
            <button
              className="pixel-button danger modal-delete-btn"
              onClick={() => onDelete(event.id)}
              title={t('schedule.modal.deleteTitle', { defaultValue: '永久删除，此操作不可恢复' })}
            >
              <Trash2 size={14} /> {t('schedule.modal.delete')}
            </button>
          )}
          <button
            className="pixel-button primary"
            onClick={handleSave}
            disabled={!form.title.trim() || isCancelled}
          >
            {isEdit ? t('schedule.modal.save') : t('schedule.modal.create')}
          </button>
          <button className="pixel-button ghost" onClick={onClose}>
            {t('schedule.modal.cancel')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- Chat Drawer ----------

function ChatDrawer({ sendWSMessage, subscribe, instanceId, open }) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState(() => loadChatMessages(instanceId));
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  // Id of the assistant message currently being streamed into. We mutate that
  // message's text in place as `subagent_token` events arrive, then "finalize"
  // it after a quiet period (no tokens for ~1.5s) so the rest of the message
  // list is stable.
  const streamingIdRef = useRef(null);
  // Timer to detect end of stream — cleared/reset on every new token.
  const streamDoneTimerRef = useRef(null);
  // Set of assistant message ids already persisted to localStorage this turn.
  // We only mark the message "complete" (remove streaming flag) once.

  const storageKey = `octopus.schedule.chat.${instanceId}`;

  // Persist messages to localStorage so they survive page navigation, reloads,
  // and toggling the drawer. Silently no-ops if storage is unavailable.
  useEffect(() => {
    try {
      window.localStorage?.setItem(storageKey, JSON.stringify(messages));
    } catch (_) {
      // best-effort persistence
    }
  }, [messages, storageKey]);

  useEffect(() => {
    if (open && endRef.current) {
      endRef.current.scrollTop = endRef.current.scrollHeight;
    }
  }, [messages, pending, open]);

  // Subscribe to subagent streaming events when the drawer is alive. Filter by
  // session_instance_id so we only react to our own schedule-assistant session
  // (other panels may also be running subagents concurrently).
  useEffect(() => {
    if (!subscribe || !instanceId) return undefined;

    const finalizeStream = () => {
      streamingIdRef.current = null;
      streamDoneTimerRef.current = null;
      setPending(false);
    };

    const scheduleFinalize = () => {
      if (streamDoneTimerRef.current) clearTimeout(streamDoneTimerRef.current);
      streamDoneTimerRef.current = setTimeout(finalizeStream, 1500);
    };

    const handleSubagentToken = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null || Number(eventInstanceId) !== Number(instanceId)) return;
      const content = data?.content || '';
      if (!content) return;

      setMessages((prev) => {
        // If we have an in-flight streaming message, append to it.
        const streamingId = streamingIdRef.current;
        if (streamingId != null) {
          return prev.map((m) =>
            m.id === streamingId ? { ...m, text: m.text + content } : m
          );
        }
        // Otherwise create a new assistant message and start streaming into it.
        const newMsg = {
          id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: 'assistant',
          text: content,
          time: Date.now(),
          streaming: true,
        };
        streamingIdRef.current = newMsg.id;
        return [...prev, newMsg];
      });
      scheduleFinalize();
    };

    const handleSubagentToolCall = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null || Number(eventInstanceId) !== Number(instanceId)) return;

      // Flush any in-flight assistant text into its own finalized bubble
      // before showing the tool call, so the conversation reads top-to-bottom.
      if (streamingIdRef.current != null && streamDoneTimerRef.current) {
        clearTimeout(streamDoneTimerRef.current);
        finalizeStream();
      }

      const args = data?.arguments || data?.args;
      const argStr = args
        ? typeof args === 'string'
          ? args
          : JSON.stringify(args, null, 2)
        : '';
      const truncated = argStr.length > 240 ? `${argStr.slice(0, 240)}…` : argStr;
      setMessages((prev) => [
        ...prev,
        {
          id: `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: 'tool',
          text: `⚙ ${data?.tool || data?.name || 'tool'}${
            truncated ? `\n${truncated}` : ''
          }`,
          time: Date.now(),
        },
      ]);
    };

    const handleSubagentToolResult = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null || Number(eventInstanceId) !== Number(instanceId)) return;

      // Mark the most recent streaming assistant message as finalized (no
      // streaming flag) once a tool result lands — the LLM has moved on.
      if (streamingIdRef.current != null) {
        const finishedId = streamingIdRef.current;
        setMessages((prev) =>
          prev.map((m) => (m.id === finishedId ? { ...m, streaming: false } : m))
        );
        streamingIdRef.current = null;
        if (streamDoneTimerRef.current) clearTimeout(streamDoneTimerRef.current);
        streamDoneTimerRef.current = null;
      }

      const result = data?.result || '';
      const isError = !!data?.error;
      const truncated =
        result.length > 280 ? `${result.slice(0, 280)}…` : result;
      setMessages((prev) => [
        ...prev,
        {
          id: `tr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: isError ? 'tool' : 'tool',
          text: isError ? `✗ ${truncated}` : `✓ ${truncated}`,
          time: Date.now(),
        },
      ]);
      // Keep `pending` true — agent will continue to emit more tokens.
    };

    const handleError = (data) => {
      const reqId = data?.request_id;
      if (reqId == null) {
        // Generic error — surface it as an assistant message.
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            role: 'assistant',
            text: t('schedule.drawer.sendFailed', {
              error: data?.error || 'unknown error',
            }),
            time: Date.now(),
          },
        ]);
        if (streamDoneTimerRef.current) clearTimeout(streamDoneTimerRef.current);
        finalizeStream();
      }
    };

    const unsubs = [];
    if (subscribe) {
      unsubs.push(subscribe('subagent_token', handleSubagentToken));
      unsubs.push(subscribe('subagent_tool_call', handleSubagentToolCall));
      unsubs.push(subscribe('subagent_tool_result', handleSubagentToolResult));
      unsubs.push(subscribe('error', handleError));
    }

    return () => {
      if (streamDoneTimerRef.current) clearTimeout(streamDoneTimerRef.current);
      unsubs.forEach((u) => u && u());
    };
  }, [subscribe, instanceId, t]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || pending) return;
    setInput('');
    const now = Date.now();
    const userMsg = {
      id: `u-${now}-${Math.random().toString(36).slice(2, 8)}`,
      role: 'user',
      text,
      time: now,
    };
    setMessages((m) => [...m, userMsg]);
    setPending(true);
    try {
      await sendWSMessage(
        'chat',
        { content: text, subagent_name: 'schedule-assistant', instance_id: instanceId },
        5000
      );
      // Note: sendWSMessage returns when the server ACKs the request. The
      // actual assistant reply comes asynchronously via the subagent_token
      // subscription wired above. We do NOT auto-finalize here — the stream
      // debounce in the subscription effect will flip `pending=false`.
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: 'assistant',
          text: t('schedule.drawer.sendFailed', { error: e.message || e }),
          time: Date.now(),
        },
      ]);
      setPending(false);
    }
  }, [input, pending, sendWSMessage, t, instanceId]);

  const hasMessages = messages.length > 0;

  return (
    <div className={`chat-drawer${open ? '' : ' collapsed'}`}>
      <div className="chat-drawer-header">
        <div className="chat-drawer-title">
          <MessageSquare size={13} />
          {t('schedule.drawer.title')}
        </div>
        <div className="chat-drawer-subtitle">{t('schedule.drawer.subtitle')}</div>
      </div>
      <div className="chat-drawer-messages" ref={endRef}>
        {!hasMessages && !pending && (
          <div className="chat-drawer-empty">
            <MessageSquare size={28} />
            <div>{t('schedule.drawer.empty')}</div>
            <div className="chat-drawer-empty-hint">
              {t('schedule.drawer.emptyHint')}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`chat-drawer-message ${m.role}${m.streaming ? ' streaming' : ''}`}
          >
            <div className="chat-drawer-message-text">{m.text}</div>
            {m.time && (
              <span className="chat-drawer-message-time">
                {dayjs(m.time).format('HH:mm')}
              </span>
            )}
          </div>
        ))}
        {pending && !streamingIdRef.current && (
          <div className="chat-drawer-typing">
            <span /><span /><span />
          </div>
        )}
      </div>
      <div className="chat-drawer-input">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={t('schedule.drawer.placeholder')}
          rows={3}
        />
        <button onClick={send} disabled={!input.trim() || pending} title={t('schedule.drawer.send')}>
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

function loadChatMessages(instanceId) {
  if (!instanceId) return [];
  try {
    const raw = window.localStorage?.getItem(`octopus.schedule.chat.${instanceId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Migrate older entries (which lacked the per-message `id`) so React's
    // keyed list reconciliation stays stable across reloads.
    return parsed.map((m, i) => ({
      id: m.id || `migrated-${i}-${Math.random().toString(36).slice(2, 8)}`,
      role: m.role,
      text: m.text || '',
      time: m.time || 0,
      streaming: false,
    }));
  } catch (_) {
    return [];
  }
}

// ---------- Main Panel ----------

const SchedulePanel = ({ sendWSMessage, subscribe }) => {
  const { t } = useTranslation();
  const [view, setView] = useState('month');
  const [cursor, setCursor] = useState(() => dayjs());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [createAt, setCreateAt] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [toasts, setToasts] = useState([]);
  const [morePopover, setMorePopover] = useState(null);

  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Stable instance_id for the chat drawer so all messages in this Schedule
  // session accumulate into a single persistent conversation on the backend
  // (one subagent session keyed by (schedule-assistant, instance_id) instead
  // of a fresh subagent per message). Persisted in localStorage so the same
  // session survives page navigation and reloads.
  const chatInstanceIdRef = useRef(null);
  if (chatInstanceIdRef.current === null) {
    const STORAGE_KEY = 'octopus.schedule.chatInstanceId';
    let stored = null;
    try {
      stored = window.localStorage?.getItem(STORAGE_KEY) || null;
    } catch (_) {
      // localStorage may be unavailable (e.g. private mode); fall through.
    }
    if (stored) {
      const parsed = parseInt(stored, 10);
      chatInstanceIdRef.current = Number.isFinite(parsed) ? parsed : null;
    }
    if (chatInstanceIdRef.current === null) {
      // 32-bit positive int derived from a UUID; safe to use as session id.
      const fresh = (Date.now() ^ Math.floor(Math.random() * 0xffffffff)) >>> 0;
      chatInstanceIdRef.current = fresh;
      try {
        window.localStorage?.setItem(STORAGE_KEY, String(fresh));
      } catch (_) {
        // best-effort persistence
      }
    }
  }

  const range = useMemo(() => visibleRange(view, cursor), [view, cursor]);

  // Fetch events for the currently visible window. Returns the count loaded so
  // callers (refresh button, save handler, broadcast subscriber) can show a
  // user-facing toast on success/failure.
  const fetchEvents = useCallback(async ({ silent = false } = {}) => {
    if (!sendWSMessage) return { ok: false, count: 0 };
    setLoading(true);
    try {
      const [start, end] = range;
      const resp = await sendWSMessage(
        'schedule_list_events',
        { start_at_ms: start.valueOf(), end_at_ms: end.valueOf() },
        8000
      );
      const list = resp?.data?.events || [];
      setEvents(list);
      if (!silent) {
        addToast(
          t('schedule.toast.refreshed', {
            count: list.length,
            defaultValue: `Loaded ${list.length} event(s)`,
          }),
          'success'
        );
      }
      return { ok: true, count: list.length };
    } catch (e) {
      console.error('Failed to fetch schedule events:', e);
      addToast(
        t('schedule.toast.refreshFailed', {
          error: e.message || e,
          defaultValue: `Refresh failed: ${e.message || e}`,
        }),
        'error'
      );
      return { ok: false, count: 0 };
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, range, addToast, t]);

  useEffect(() => {
    // Initial load is silent — only user-initiated refreshes and CRUD show toasts.
    fetchEvents({ silent: true });
  }, [fetchEvents]);

  // Live refresh on any schedule mutation broadcast — silent (no toast) since
  // the user didn't initiate it explicitly. The local modal save/delete and the
  // manual refresh button still surface their own toasts.
  useEffect(() => {
    if (!subscribe) return;
    const types = [
      'schedule_event_created',
      'schedule_event_updated',
      'schedule_event_deleted',
      'schedule_events_changed',
    ];
    const unsubs = types.map((tp) => subscribe(tp, () => fetchEvents({ silent: true })));
    return () => unsubs.forEach((u) => u && u());
  }, [subscribe, fetchEvents]);

  // Manual refresh handler — always shows a toast (success or failure) so the
  // user gets explicit feedback.
  const handleManualRefresh = useCallback(async () => {
    await fetchEvents({ silent: false });
  }, [fetchEvents]);

  const handleSave = useCallback(
    async (data) => {
      try {
        if (selected) {
          await sendWSMessage('schedule_update_event', {
            event_id: selected.id,
            ...data,
          });
          addToast(t('schedule.toast.updated', { defaultValue: 'Event updated' }), 'success');
        } else {
          await sendWSMessage('schedule_create_event', data);
          addToast(t('schedule.toast.created', { defaultValue: 'Event created' }), 'success');
        }
        setSelected(null);
        setCreateAt(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Save event failed:', e);
        addToast(
          t('schedule.toast.saveFailed', {
            error: e.message || e,
            defaultValue: `Save failed: ${e.message || e}`,
          }),
          'error'
        );
      }
    },
    [selected, sendWSMessage, fetchEvents, addToast, t]
  );

  const handleDelete = useCallback(
    async (eventId) => {
      if (!confirm(t('schedule.modal.deleteConfirm'))) return;
      try {
        await sendWSMessage('schedule_delete_event', { event_id: eventId });
        addToast(t('schedule.toast.deleted', { defaultValue: 'Event deleted' }), 'success');
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Delete failed:', e);
        addToast(
          t('schedule.toast.deleteFailed', {
            error: e.message || e,
            defaultValue: `Delete failed: ${e.message || e}`,
          }),
          'error'
        );
      }
    },
    [sendWSMessage, fetchEvents, addToast, t]
  );

  const handleCancelEvent = useCallback(
    async (eventId) => {
      try {
        await sendWSMessage('schedule_cancel_event', { event_id: eventId });
        addToast(
          t('schedule.toast.cancelled', { defaultValue: 'Event marked as cancelled' }),
          'success'
        );
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Cancel event failed:', e);
        addToast(
          t('schedule.toast.cancelledFailed', {
            error: e.message || e,
            defaultValue: `Cancel failed: ${e.message || e}`,
          }),
          'error'
        );
      }
    },
    [sendWSMessage, fetchEvents, addToast, t]
  );

  const handleUncancelEvent = useCallback(
    async (eventId) => {
      try {
        await sendWSMessage('schedule_uncancel_event', { event_id: eventId });
        addToast(
          t('schedule.toast.uncancelled', { defaultValue: 'Event restored' }),
          'success'
        );
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Restore event failed:', e);
        addToast(
          t('schedule.toast.uncancelFailed', {
            error: e.message || e,
            defaultValue: `Restore failed: ${e.message || e}`,
          }),
          'error'
        );
      }
    },
    [sendWSMessage, fetchEvents, addToast, t]
  );

  const onCreateAt = (d) => {
    setSelected(null);
    setCreateAt(d);
  };

  const onSelectEvent = (ev) => {
    setCreateAt(null);
    setSelected(ev);
  };

  const handleShowMore = useCallback((day, dayEvents, anchor) => {
    setMorePopover({ day, events: dayEvents, anchor });
  }, []);

  const closeMorePopover = useCallback(() => {
    setMorePopover(null);
  }, []);

  return (
    <div className="schedule-panel-container">
      {/* Toast notifications (refresh success/failure, save/delete feedback) */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
      <div className="schedule-main">
        <div className="schedule-toolbar">
          <div className="toolbar-left">
            <WindowDots />
            <span className="toolbar-title">{t('title.schedule', { defaultValue: 'SCHEDULE' })}</span>
            <span className="event-count">({events.length})</span>
          </div>
          <div className="toolbar-right">
            <button
              className="nav-btn"
              onClick={() => setCursor(shiftCursor(view, cursor, -1))}
              title={t('schedule.previous')}
            >
              <ChevronLeft size={14} />
            </button>
            <button
              className="today-btn"
              onClick={() => setCursor(dayjs())}
            >
              {t('schedule.today')}
            </button>
            <button
              className="nav-btn"
              onClick={() => setCursor(shiftCursor(view, cursor, 1))}
              title={t('schedule.next')}
            >
              <ChevronRight size={14} />
            </button>
            <div className="view-switcher">
              {['day', 'week', 'month'].map((v) => (
                <button
                  key={v}
                  className={view === v ? 'active' : ''}
                  onClick={() => setView(v)}
                >
                  {t(`schedule.view${v[0].toUpperCase()}${v.slice(1)}`)}
                </button>
              ))}
            </div>
            <button
              className="pixel-button"
              onClick={() => onCreateAt(dayjs().minute(0).second(0).add(1, 'hour'))}
            >
              <Plus size={14} /> {t('schedule.newEvent')}
            </button>
            <button
              className={`nav-btn${loading ? ' refreshing' : ''}`}
              onClick={handleManualRefresh}
              disabled={loading}
              title={t('schedule.refresh', { defaultValue: 'Refresh' })}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
            <button
              className={`nav-btn${drawerOpen ? ' active' : ''}`}
              onClick={() => setDrawerOpen((v) => !v)}
              title={drawerOpen ? t('schedule.hideChat') : t('schedule.showChat')}
            >
              {drawerOpen ? <X size={14} /> : <MessageSquare size={14} />}
            </button>
          </div>
        </div>
        <div className="schedule-content">
          {loading && events.length === 0 ? (
            <div className="cron-loading">
              <div className="loading-spinner"></div>
              <span>{t('schedule.loading')}</span>
            </div>
          ) : view === 'month' ? (
            <MonthView
              cursor={cursor}
              events={events}
              onSelectEvent={onSelectEvent}
              onCreateAt={onCreateAt}
              onShowMore={handleShowMore}
            />
          ) : view === 'week' ? (
            <WeekView
              cursor={cursor}
              events={events}
              onSelectEvent={onSelectEvent}
              onCreateAt={onCreateAt}
            />
          ) : (
            <DayView
              cursor={cursor}
              events={events}
              onSelectEvent={onSelectEvent}
              onCreateAt={onCreateAt}
            />
          )}
        </div>
      </div>

      <ChatDrawer
        sendWSMessage={sendWSMessage}
        subscribe={subscribe}
        instanceId={chatInstanceIdRef.current}
        open={drawerOpen}
      />

      {morePopover && (
        <DayEventsPopover
          day={morePopover.day}
          events={morePopover.events}
          anchor={morePopover.anchor}
          onSelectEvent={onSelectEvent}
          onCreateAt={onCreateAt}
          onClose={closeMorePopover}
        />
      )}

      {(selected || createAt) && (
        <EventModal
          event={selected}
          defaultStart={createAt}
          onSave={handleSave}
          onDelete={handleDelete}
          onCancelEvent={handleCancelEvent}
          onUncancelEvent={handleUncancelEvent}
          onClose={() => {
            setSelected(null);
            setCreateAt(null);
          }}
        />
      )}
    </div>
  );
};

export default SchedulePanel;
