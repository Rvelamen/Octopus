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
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
                      {t('schedule.modal.cancelled')}
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
        <button className="dialog-close" onClick={onClose} title={t('window.close')}>
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
              {ev.all_day ? t('schedule.modal.allDay') : `${formatTime(ev.start_at_ms)} – ${formatTime(ev.end_at_ms)}`}
            </div>
            <div className="day-events-popover-item-title">
              <span
                className="month-event-color-dot"
                style={{ background: ev.color }}
              />
              {ev.title}
              {ev.cancelled && (
                <span className="month-event-cancelled-tag">
                  {t('schedule.modal.cancelled')}
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
                {t('schedule.modal.cancelled')}
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
            {t('schedule.modal.cancelledHint')}
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
              <RotateCcw size={14} /> {t('schedule.modal.uncancel')}
            </button>
          )}
          {isEdit && !isCancelled && (
            <button
              className="pixel-button secondary"
              onClick={() => onCancelEvent(event.id)}
            >
              <Ban size={14} /> {t('schedule.modal.cancelSchedule')}
            </button>
          )}
          {isEdit && (
            <button
              className="pixel-button danger modal-delete-btn"
              onClick={() => onDelete(event.id)}
              title={t('schedule.modal.deleteTitle')}
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

  // Group consecutive tool-role messages into a single collapsible block so
  // the user sees a compact "调用了 N 个工具" summary instead of a wall of
  // args/result bubbles for every tool invocation.
  const groupedMessages = useMemo(() => {
    const out = [];
    let i = 0;
    while (i < messages.length) {
      const m = messages[i];
      if (m.role !== 'tool') {
        out.push(m);
        i += 1;
        continue;
      }
      const toolMsgs = [];
      while (i < messages.length && messages[i].role === 'tool') {
        toolMsgs.push(messages[i]);
        i += 1;
      }
      // Pair up each call ("⚙ name\nargs") with the following result ("✓ …" / "✗ …").
      const calls = [];
      for (let j = 0; j < toolMsgs.length; j += 1) {
        const tm = toolMsgs[j];
        const text = tm.text || '';
        if (text.startsWith('⚙ ')) {
          const firstLineEnd = text.indexOf('\n');
          const head = firstLineEnd === -1 ? text : text.slice(0, firstLineEnd);
          const args = firstLineEnd === -1 ? '' : text.slice(firstLineEnd + 1);
          const name = head.replace(/^⚙\s+/, '').trim() || 'tool';
          const next = toolMsgs[j + 1];
          let status = 'pending';
          let result = '';
          if (next && (next.text || '').startsWith('✓ ')) {
            status = 'ok';
            result = next.text.slice(2);
            j += 1;
          } else if (next && (next.text || '').startsWith('✗ ')) {
            status = 'error';
            result = next.text.slice(2);
            j += 1;
          }
          calls.push({ id: tm.id, name, args, status, result, time: tm.time });
        } else if (text.startsWith('✓ ') || text.startsWith('✗ ')) {
          // Stray result without a matching call — surface as its own line.
          calls.push({
            id: tm.id,
            name: '?',
            args: '',
            status: text.startsWith('✓ ') ? 'ok' : 'error',
            result: text.slice(2),
            time: tm.time,
          });
        }
      }
      out.push({
        type: 'tool-group',
        id: `tg-${toolMsgs[0].id}`,
        calls,
        time: toolMsgs[0].time,
      });
    }
    return out;
  }, [messages]);

  // Track which tool groups the user has expanded. Default to all collapsed.
  const [expandedToolGroups, setExpandedToolGroups] = useState(() => new Set());
  const toggleToolGroup = useCallback((id) => {
    setExpandedToolGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

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

  // Defense in depth: if no message is currently being streamed into but a
  // message still has the `streaming` flag set, clear it. This catches any
  // race where the streaming ref was reset before finalizeStream ran (e.g.
  // a tool result landed, then a synthesized-fallback token created a new
  // streaming message that never got finalized because no further tokens
  // arrived). The early `prev`-identity return keeps this loop-stable.
  useEffect(() => {
    if (streamingIdRef.current != null) return;
    setMessages((prev) => {
      if (!prev.some((m) => m.streaming)) return prev;
      return prev.map((m) => (m.streaming ? { ...m, streaming: false } : m));
    });
  }, [messages]);

  // Subscribe to subagent streaming events when the drawer is alive. Filter by
  // session_instance_id so we only react to our own schedule-assistant session
  // (other panels may also be running subagents concurrently).
  useEffect(() => {
    if (!subscribe || !instanceId) return undefined;

    // Hard safety net: if the stream stalls for too long (e.g. WS drop mid-
    // response, or the LLM loop ended without a final token), finalize so
    // the drawer doesn't sit on a blinking cursor. The normal finalize
    // path is the 1.5s debounce below; this is the "give up" timer that
    // also clears the streaming ref so a future turn starts fresh.
    let stuckTimer = null;
    const armStuckTimer = () => {
      if (stuckTimer) clearTimeout(stuckTimer);
      stuckTimer = setTimeout(() => {
        if (streamingIdRef.current != null) {
          // eslint-disable-next-line no-console
          console.warn('[schedule-drawer] stream stuck > 30s, finalizing');
        }
        streamingIdRef.current = null;
        finalizeStream();
      }, 30000);
    };

    const finalizeStream = () => {
      // Mark the in-flight message as finalized (drop the cursor, re-enable
      // the send button) but DO NOT null the ref. The ref represents the
      // current assistant message of the current turn — nulling it between
      // slow tokens or across tool boundaries was creating one bubble per
      // chunk. The ref is now reset at the next send() call (turn boundary)
      // or by the 30s hard stuck timer below.
      const finishedId = streamingIdRef.current;
      if (finishedId != null) {
        setMessages((prev) =>
          prev.map((m) => (m.id === finishedId ? { ...m, streaming: false } : m))
        );
      }
      streamDoneTimerRef.current = null;
      if (stuckTimer) {
        clearTimeout(stuckTimer);
        stuckTimer = null;
      }
      setPending(false);
    };

    const scheduleFinalize = () => {
      if (streamDoneTimerRef.current) clearTimeout(streamDoneTimerRef.current);
      streamDoneTimerRef.current = setTimeout(finalizeStream, 1500);
      armStuckTimer();
    };

    const handleSubagentToken = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null || Number(eventInstanceId) !== Number(instanceId)) return;
      const content = data?.content || '';
      if (!content) return;

      setMessages((prev) => {
        // If we have an in-flight streaming message, append to it. Re-mark
        // it streaming so the blinking cursor reappears for the new chunk.
        const streamingId = streamingIdRef.current;
        if (streamingId != null) {
          return prev.map((m) =>
            m.id === streamingId
              ? { ...m, text: m.text + content, streaming: true }
              : m
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

      // Pause the in-flight assistant text mid-turn (drop the cursor while
      // tools execute) but DO NOT null the ref — the LLM's post-tool reply
      // should continue into the same message, not open a new one. Clear
      // the quiet timer so a slow LLM doesn't accidentally finalize-and-
      // null the ref between tool call and post-tool tokens.
      if (streamingIdRef.current != null) {
        const finishedId = streamingIdRef.current;
        setMessages((prev) =>
          prev.map((m) => (m.id === finishedId ? { ...m, streaming: false } : m))
        );
        if (streamDoneTimerRef.current) {
          clearTimeout(streamDoneTimerRef.current);
          streamDoneTimerRef.current = null;
        }
        setPending(false);
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
      // streaming flag) once a tool result lands — the LLM has moved on to
      // either more tool calls or the final reply. Keep the ref set so any
      // subsequent subagent_token appends to the same message rather than
      // opening a new bubble per chunk.
      if (streamingIdRef.current != null) {
        const finishedId = streamingIdRef.current;
        setMessages((prev) =>
          prev.map((m) => (m.id === finishedId ? { ...m, streaming: false } : m))
        );
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
    // Turn boundary: any in-flight stream from the previous turn is done.
    // The next subagent_token should open a new assistant message instead of
    // appending to a stale one.
    streamingIdRef.current = null;
    if (streamDoneTimerRef.current) {
      clearTimeout(streamDoneTimerRef.current);
      streamDoneTimerRef.current = null;
    }
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

  const handleClear = useCallback(() => {
    if (!hasMessages) return;
    const ok = window.confirm(t('schedule.drawer.clearConfirm'));
    if (!ok) return;
    // Cancel any in-flight stream so a mid-flight token doesn't sneak back
    // into the freshly-emptied drawer.
    streamingIdRef.current = null;
    if (streamDoneTimerRef.current) {
      clearTimeout(streamDoneTimerRef.current);
      streamDoneTimerRef.current = null;
    }
    setPending(false);
    setMessages([]);
    try {
      window.localStorage?.removeItem(storageKey);
    } catch (_) {
      // best-effort
    }
  }, [hasMessages, t, storageKey]);

  return (
    <div className={`chat-drawer${open ? '' : ' collapsed'}`}>
      <div className="chat-drawer-header">
        <div className="chat-drawer-title-row">
          <div className="chat-drawer-title">
            <MessageSquare size={13} />
            {t('schedule.drawer.title')}
          </div>
          {hasMessages && (
            <button
              type="button"
              className="chat-drawer-clear-btn"
              onClick={handleClear}
              title={t('schedule.drawer.clear')}
              aria-label={t('schedule.drawer.clear')}
            >
              <Trash2 size={12} />
            </button>
          )}
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
        {groupedMessages.map((m) => {
          if (m.type === 'tool-group') {
            const isExpanded = expandedToolGroups.has(m.id);
            const errorCount = m.calls.filter((c) => c.status === 'error').length;
            const okCount = m.calls.filter((c) => c.status === 'ok').length;
            const summaryText = t('schedule.drawer.toolCalls', {
              count: m.calls.length,
            });
            return (
              <div
                key={m.id}
                className={`chat-drawer-message tool-group${
                  isExpanded ? ' expanded' : ''
                }`}
              >
                <button
                  type="button"
                  className="chat-drawer-tool-toggle"
                  onClick={() => toggleToolGroup(m.id)}
                  aria-expanded={isExpanded}
                >
                  <span className="chat-drawer-tool-chevron" aria-hidden="true">
                    {isExpanded ? '▾' : '▸'}
                  </span>
                  <span className="chat-drawer-tool-summary">{summaryText}</span>
                  {errorCount > 0 && (
                    <span className="chat-drawer-tool-badge error">
                      ✗ {errorCount}
                    </span>
                  )}
                  {errorCount === 0 && okCount > 0 && (
                    <span className="chat-drawer-tool-badge ok">✓</span>
                  )}
                  <span className="chat-drawer-tool-toggle-label">
                    {isExpanded
                      ? t('schedule.drawer.hideDetails')
                      : t('schedule.drawer.showDetails')}
                  </span>
                </button>
                {isExpanded && (
                  <div className="chat-drawer-tool-details">
                    {m.calls.map((c) => (
                      <div
                        key={c.id}
                        className={`chat-drawer-tool-item ${c.status}`}
                      >
                        <div className="chat-drawer-tool-item-head">
                          <span className="chat-drawer-tool-name">{c.name}</span>
                          <span className={`chat-drawer-tool-status ${c.status}`}>
                            {c.status === 'ok'
                              ? t('schedule.drawer.toolStatusOk')
                              : c.status === 'error'
                                ? t('schedule.drawer.toolStatusError')
                                : t('schedule.drawer.toolStatusPending')}
                          </span>
                        </div>
                        {c.args && (
                          <pre className="chat-drawer-tool-args">{c.args}</pre>
                        )}
                        {c.result && (
                          <pre className="chat-drawer-tool-result">{c.result}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {m.time && (
                  <span className="chat-drawer-message-time">
                    {dayjs(m.time).format('HH:mm')}
                  </span>
                )}
              </div>
            );
          }
          return (
            <div
              key={m.id}
              className={`chat-drawer-message ${m.role}${
                m.streaming ? ' streaming' : ''
              }`}
            >
              <div className="chat-drawer-message-text">
                {m.role === 'assistant' ? (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Open links in a new tab so the user doesn't lose
                      // chat context when they click one.
                      a: ({ node, ...props }) => (
                        <a {...props} target="_blank" rel="noopener noreferrer" />
                      ),
                    }}
                  >
                    {m.text || ''}
                  </ReactMarkdown>
                ) : (
                  m.text
                )}
              </div>
              {m.time && (
                <span className="chat-drawer-message-time">
                  {dayjs(m.time).format('HH:mm')}
                </span>
              )}
            </div>
          );
        })}
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
          rows={1}
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

// 30-day retention matches the server's RECYCLE_BIN_RETENTION_MS constant.
const RECYCLE_BIN_RETENTION_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

function RecycleBinModal({
  open,
  events,
  loading,
  selected,
  onToggleOne,
  onSelectAll,
  onClearSelection,
  onClose,
  onRefresh,
  onRestoreOne,
  onRestoreSelected,
  onHardDeleteOne,
  onHardDeleteSelected,
}) {
  const { t } = useTranslation();

  // Bucket events by deletion day so the user gets a clear "what did I delete
  // when" structure. We key by the local-day string of `deleted_at_ms` and
  // sort each bucket by deletion time (newest first).
  // NOTE: this hook MUST run before the early return below — React's Rules
  // of Hooks require every render to call hooks in the same order. Calling
  // useMemo conditionally (after `if (!open) return null`) crashes the
  // renderer with "Rendered fewer hooks than expected", which is exactly
  // what was happening when the modal opened.
  const groups = useMemo(() => {
    const map = new Map();
    const todayStart = dayjs().startOf('day');
    for (const ev of events) {
      const ts = ev.deleted_at_ms || ev.deleted_at || 0;
      const dayKey = dayjs(ts).format('YYYY-MM-DD');
      if (!map.has(dayKey)) map.set(dayKey, []);
      map.get(dayKey).push({ ...ev, _sortTs: ts });
    }
    // Sort groups newest first; within each group, newest deletion first.
    const sorted = Array.from(map.entries())
      .sort((a, b) => (a[0] < b[0] ? 1 : -1))
      .map(([key, items]) => ({
        key,
        items: items.sort((a, b) => b._sortTs - a._sortTs),
      }));
    return { groups: sorted, todayStart };
  }, [events]);

  if (!open) return null;

  const allSelected =
    events.length > 0 && selected.size === events.length;

  return (
    <div className="recycle-bin-overlay" role="dialog" aria-modal="true">
      <div className="recycle-bin-modal">
        <header className="recycle-bin-header">
          <div className="recycle-bin-title-block">
            <h2 className="recycle-bin-title">
              <Trash2 size={18} />
              {t('schedule.recycleBin.title')}
            </h2>
            <p className="recycle-bin-subtitle">
              {t('schedule.recycleBin.subtitle')}
            </p>
            <p className="recycle-bin-hint">
              {t('schedule.recycleBin.autoPurge')}
            </p>
          </div>
          <div className="recycle-bin-header-actions">
            <button
              type="button"
              className="recycle-bin-icon-btn"
              onClick={onRefresh}
              disabled={loading}
              title={t('schedule.recycleBin.refresh')}
              aria-label={t('schedule.recycleBin.refresh')}
            >
              <RefreshCw
                size={16}
                className={loading ? 'recycle-bin-spin' : ''}
              />
            </button>
            <button
              type="button"
              className="recycle-bin-icon-btn"
              onClick={onClose}
              title={t('schedule.recycleBin.close')}
              aria-label={t('schedule.recycleBin.close')}
            >
              <X size={16} />
            </button>
          </div>
        </header>

        <div className="recycle-bin-toolbar">
          <label className="recycle-bin-select-all">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) =>
                e.target.checked ? onSelectAll() : onClearSelection()
              }
              disabled={events.length === 0}
            />
            <span>
              {allSelected
                ? t('schedule.recycleBin.clearSelection')
                : t('schedule.recycleBin.selectAll')}
            </span>
          </label>
          <span className="recycle-bin-selected-count">
            {t('schedule.recycleBin.selectedCount', { count: selected.size })}
          </span>
        </div>

        <div className="recycle-bin-body">
          {loading && events.length === 0 ? (
            <div className="recycle-bin-state">
              {t('schedule.recycleBin.loading')}
            </div>
          ) : events.length === 0 ? (
            <div className="recycle-bin-state recycle-bin-empty">
              <Trash2 size={32} />
              <p>{t('schedule.recycleBin.empty')}</p>
            </div>
          ) : (
            groups.groups.map((group) => {
              const dayLabel = formatBinDayLabel(group.key, groups.todayStart, t);
              return (
                <section
                  className="recycle-bin-day-group"
                  key={group.key}
                >
                  <h3 className="recycle-bin-day-header">
                    <span className="recycle-bin-day-label">{dayLabel}</span>
                    <span className="recycle-bin-day-count">
                      {group.items.length}
                    </span>
                  </h3>
                  <ul className="recycle-bin-list">
                    {group.items.map((ev) => {
                      const ts = ev.deleted_at_ms || ev.deleted_at || 0;
                      const remaining = computeDaysRemaining(ts);
                      const expired = remaining <= 0;
                      const isSelected = selected.has(ev.id);
                      return (
                        <li
                          key={ev.id}
                          className={
                            'recycle-bin-item' +
                            (isSelected ? ' is-selected' : '') +
                            (expired ? ' is-expired' : '')
                          }
                        >
                          <label className="recycle-bin-item-check">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => onToggleOne(ev.id)}
                            />
                          </label>
                          <div className="recycle-bin-item-body">
                            <div
                              className="recycle-bin-item-title"
                              title={ev.title}
                            >
                              {ev.title}
                            </div>
                            <div className="recycle-bin-item-meta">
                              <span className="recycle-bin-item-time">
                                {formatTimeRange(ev)}
                              </span>
                              {ev.location ? (
                                <span className="recycle-bin-item-location">
                                  {ev.location}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <div
                            className={
                              'recycle-bin-item-remaining' +
                              (expired ? ' is-expired' : '')
                            }
                            title={dayjs(ts).format('YYYY-MM-DD HH:mm')}
                          >
                            {expired
                              ? t('schedule.recycleBin.expired')
                              : t('schedule.recycleBin.daysRemaining', {
                                  count: remaining,
                                })}
                          </div>
                          <div className="recycle-bin-item-actions">
                            <button
                              type="button"
                              className="recycle-bin-action restore"
                              onClick={() => onRestoreOne(ev)}
                              disabled={expired}
                              title={t('schedule.recycleBin.restoreOne')}
                            >
                              <RotateCcw size={14} />
                              <span>
                                {t('schedule.recycleBin.restoreOne')}
                              </span>
                            </button>
                            <button
                              type="button"
                              className="recycle-bin-action delete"
                              onClick={() => onHardDeleteOne(ev)}
                              title={t('schedule.recycleBin.deleteOne')}
                            >
                              <Trash2 size={14} />
                              <span>
                                {t('schedule.recycleBin.deleteOne')}
                              </span>
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })
          )}
        </div>

        <footer className="recycle-bin-footer">
          <button
            type="button"
            className="recycle-bin-btn secondary"
            onClick={onClose}
          >
            {t('schedule.recycleBin.close')}
          </button>
          <div className="recycle-bin-footer-actions">
            <button
              type="button"
              className="recycle-bin-btn danger"
              disabled={selected.size === 0}
              onClick={onHardDeleteSelected}
            >
              <Trash2 size={14} />
              {t('schedule.recycleBin.deleteForeverSelected')}
            </button>
            <button
              type="button"
              className="recycle-bin-btn primary"
              disabled={selected.size === 0}
              onClick={onRestoreSelected}
            >
              <RotateCcw size={14} />
              {t('schedule.recycleBin.restoreSelected')}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function formatTimeRange(ev) {
  const start = ev.start_at_ms || ev.start_at;
  const end = ev.end_at_ms || ev.end_at;
  if (!start) return '';
  const s = dayjs(start);
  const e = end ? dayjs(end) : null;
  if (!e) return s.format('MM-DD HH:mm');
  // Same day → "MM-DD HH:mm–HH:mm"; spans midnight → both full stamps.
  if (s.isSame(e, 'day')) {
    return `${s.format('MM-DD HH:mm')} – ${e.format('HH:mm')}`;
  }
  return `${s.format('MM-DD HH:mm')} – ${e.format('MM-DD HH:mm')}`;
}

function computeDaysRemaining(deletedTs) {
  if (!deletedTs) return 0;
  const deleted = dayjs(deletedTs);
  const expiry = deleted.add(RECYCLE_BIN_RETENTION_DAYS, 'day');
  const today = dayjs().startOf('day');
  const diffDays = expiry.startOf('day').diff(today, 'day');
  return Math.max(0, diffDays);
}

function formatBinDayLabel(key, todayStart, t) {
  const day = dayjs(key);
  const todayKey = todayStart.format('YYYY-MM-DD');
  const yesterdayKey = todayStart
    .subtract(1, 'day')
    .format('YYYY-MM-DD');
  if (key === todayKey) return t('schedule.recycleBin.today');
  if (key === yesterdayKey) return t('schedule.recycleBin.yesterday');
  const diff = todayStart.startOf('day').diff(day.startOf('day'), 'day');
  if (diff > 0 && diff <= 7) {
    return t('schedule.recycleBin.daysAgo', { count: diff });
  }
  return day.format('YYYY-MM-DD (ddd)');
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
  // Recycle bin state — separate from the live event list so the bin modal
  // can show soft-deleted rows without polluting the main calendar view.
  const [binOpen, setBinOpen] = useState(false);
  const [binEvents, setBinEvents] = useState([]);
  const [binLoading, setBinLoading] = useState(false);
  const [binSelected, setBinSelected] = useState(() => new Set());
  const [binCount, setBinCount] = useState(0);

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
          addToast(t('schedule.toast.updated'), 'success');
        } else {
          await sendWSMessage('schedule_create_event', data);
          addToast(t('schedule.toast.created'), 'success');
        }
        setSelected(null);
        setCreateAt(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Save event failed:', e);
        addToast(
          t('schedule.toast.saveFailed', {
            error: e.message || e,
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
        addToast(t('schedule.toast.deleted'), 'success');
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Delete failed:', e);
        addToast(
          t('schedule.toast.deleteFailed', {
            error: e.message || e,
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
          t('schedule.toast.cancelled'),
          'success'
        );
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Cancel event failed:', e);
        addToast(
          t('schedule.toast.cancelledFailed', {
            error: e.message || e,
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
          t('schedule.toast.uncancelled'),
          'success'
        );
        setSelected(null);
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Restore event failed:', e);
        addToast(
          t('schedule.toast.uncancelFailed', {
            error: e.message || e,
          }),
          'error'
        );
      }
    },
    [sendWSMessage, fetchEvents, addToast, t]
  );

  // ---------- Recycle bin handlers ----------
  // Count-only fetch used to drive the trash-button badge. Cheap because the
  // server returns the full bin list and we just read .length — but we still
  // keep the result around so opening the modal is instant.
  const refreshBin = useCallback(
    async ({ silent = false } = {}) => {
      if (!sendWSMessage) return { ok: false, count: 0 };
      setBinLoading(true);
      try {
        const resp = await sendWSMessage(
          'schedule_list_recycle_bin',
          {},
          8000
        );
        const list = resp?.data?.events || [];
        setBinEvents(list);
        setBinCount(list.length);
        // Drop any selected ids that no longer exist (e.g. they got restored
        // from another tab while the modal was open).
        setBinSelected((prev) => {
          if (prev.size === 0) return prev;
          const live = new Set(list.map((e) => e.id));
          const next = new Set();
          for (const id of prev) if (live.has(id)) next.add(id);
          return next;
        });
        if (!silent) {
          addToast(
            t('schedule.toast.refreshed', {
              count: list.length,
            }),
            'success'
          );
        }
        return { ok: true, count: list.length };
      } catch (e) {
        console.error('Failed to fetch recycle bin:', e);
        if (!silent) {
          addToast(
            t('schedule.recycleBin.loadFailed', { error: e.message || e }),
            'error'
          );
        }
        return { ok: false, count: 0 };
      } finally {
        setBinLoading(false);
      }
    },
    [sendWSMessage, addToast, t]
  );

  // Lightweight background poll for the badge — runs on mount + every 60s so
  // the trash-count stays fresh even when the modal hasn't been opened. Skips
  // when the WS isn't ready.
  useEffect(() => {
    if (!sendWSMessage) return undefined;
    refreshBin({ silent: true });
    const id = window.setInterval(() => refreshBin({ silent: true }), 60000);
    return () => window.clearInterval(id);
  }, [sendWSMessage, refreshBin]);

  // Also refresh the badge when the WS broadcasts a schedule change so a
  // delete from another tab surfaces immediately.
  useEffect(() => {
    if (!subscribe) return undefined;
    const types = [
      'schedule_event_deleted',
      'schedule_event_restored',
      'schedule_events_restored',
      'schedule_events_changed',
    ];
    const unsubs = types.map((tp) => subscribe(tp, () => refreshBin({ silent: true })));
    return () => unsubs.forEach((u) => u && u());
  }, [subscribe, refreshBin]);

  const openRecycleBin = useCallback(() => {
    setBinOpen(true);
    setBinSelected(new Set());
    refreshBin({ silent: true });
  }, [refreshBin]);

  const closeRecycleBin = useCallback(() => {
    setBinOpen(false);
  }, []);

  const toggleBinSelected = useCallback((id) => {
    setBinSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllBin = useCallback(() => {
    setBinSelected(new Set(binEvents.map((e) => e.id)));
  }, [binEvents]);

  const clearBinSelection = useCallback(() => {
    setBinSelected(new Set());
  }, []);

  const handleRestoreOne = useCallback(
    async (ev) => {
      if (
        !window.confirm(
          t('schedule.recycleBin.confirmRestore', { title: ev.title })
        )
      )
        return;
      try {
        await sendWSMessage('schedule_restore_event', { event_id: ev.id });
        addToast(
          t('schedule.recycleBin.restored', { title: ev.title }),
          'success'
        );
        // Drop the restored row from the local bin list and remove it from
        // any current multi-select; refresh the badge.
        setBinEvents((prev) => prev.filter((e) => e.id !== ev.id));
        setBinSelected((prev) => {
          if (!prev.has(ev.id)) return prev;
          const next = new Set(prev);
          next.delete(ev.id);
          return next;
        });
        setBinCount((c) => Math.max(0, c - 1));
        // Refresh the live calendar (the event is now active again).
        fetchEvents({ silent: true });
      } catch (e) {
        console.error('Restore event failed:', e);
        addToast(
          t('schedule.recycleBin.restoreFailed', { error: e.message || e }),
          'error'
        );
      }
    },
    [sendWSMessage, addToast, t, fetchEvents]
  );

  const handleRestoreSelected = useCallback(async () => {
    const ids = Array.from(binSelected);
    if (ids.length === 0) {
      addToast(t('schedule.recycleBin.noItemsSelected'), 'info');
      return;
    }
    if (
      !window.confirm(
        t('schedule.recycleBin.confirmBatchRestore', { count: ids.length })
      )
    )
      return;
    try {
      const resp = await sendWSMessage('schedule_batch_restore_events', {
        event_ids: ids,
      });
      const restoredCount = resp?.data?.restored_count ?? ids.length;
      addToast(
        t('schedule.recycleBin.restoredCount', { count: restoredCount }),
        'success'
      );
      setBinSelected(new Set());
      refreshBin({ silent: true });
      fetchEvents({ silent: true });
    } catch (e) {
      console.error('Batch restore failed:', e);
      addToast(
        t('schedule.recycleBin.batchRestoreFailed', { error: e.message || e }),
        'error'
      );
    }
  }, [binSelected, sendWSMessage, addToast, t, refreshBin, fetchEvents]);

  const handleHardDeleteOne = useCallback(
    async (ev) => {
      if (
        !window.confirm(
          t('schedule.recycleBin.confirmDeleteOne', { title: ev.title })
        )
      )
        return;
      try {
        await sendWSMessage('schedule_hard_delete_event', { event_id: ev.id });
        addToast(t('schedule.recycleBin.deletedForever'), 'success');
        setBinEvents((prev) => prev.filter((e) => e.id !== ev.id));
        setBinSelected((prev) => {
          if (!prev.has(ev.id)) return prev;
          const next = new Set(prev);
          next.delete(ev.id);
          return next;
        });
        setBinCount((c) => Math.max(0, c - 1));
      } catch (e) {
        console.error('Hard delete failed:', e);
        addToast(
          t('schedule.recycleBin.hardDeleteFailed', { error: e.message || e }),
          'error'
        );
      }
    },
    [sendWSMessage, addToast, t]
  );

  const handleHardDeleteSelected = useCallback(async () => {
    const ids = Array.from(binSelected);
    if (ids.length === 0) {
      addToast(t('schedule.recycleBin.noItemsSelected'), 'info');
      return;
    }
    if (
      !window.confirm(
        t('schedule.recycleBin.confirmDeleteSelected', { count: ids.length })
      )
    )
      return;
    // Issue one hard-delete per id. The server treats each as a hard remove;
    // we just call them in parallel for speed and update the local state in
    // one pass at the end.
    const settled = await Promise.allSettled(
      ids.map((id) =>
        sendWSMessage('schedule_hard_delete_event', { event_id: id })
      )
    );
    const okIds = ids.filter(
      (_, i) => settled[i].status === 'fulfilled'
    );
    const failCount = settled.length - okIds.length;
    setBinEvents((prev) => prev.filter((e) => !okIds.includes(e.id)));
    setBinCount((c) => Math.max(0, c - okIds.length));
    setBinSelected(new Set());
    if (okIds.length > 0) {
      addToast(
        t('schedule.recycleBin.deletedForever') +
          (failCount > 0 ? ` (${failCount} failed)` : ''),
        failCount > 0 ? 'info' : 'success'
      );
    }
    if (failCount > 0) {
      addToast(
        t('schedule.recycleBin.hardDeleteFailed', {
          error: `${failCount} item(s) failed`,
        }),
        'error'
      );
    }
  }, [binSelected, sendWSMessage, addToast, t]);

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
            <span className="toolbar-title">{t('title.schedule')}</span>
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
              className="new-event-btn"
              onClick={() => onCreateAt(dayjs().minute(0).second(0).add(1, 'hour'))}
              title={t('schedule.newEvent')}
              aria-label={t('schedule.newEvent')}
            >
              <Plus size={14} />
            </button>
            <button
              className="trash-btn"
              onClick={openRecycleBin}
              title={t('schedule.recycleBin.open')}
              aria-label={t('schedule.recycleBin.open')}
            >
              <Trash2 size={14} />
              {binCount > 0 && <span className="trash-btn-badge">{binCount}</span>}
            </button>
            <button
              className={`refresh-btn${loading ? ' refreshing' : ''}`}
              onClick={handleManualRefresh}
              disabled={loading}
              title={t('schedule.refresh')}
              aria-label={t('schedule.refresh')}
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

      <RecycleBinModal
        open={binOpen}
        events={binEvents}
        loading={binLoading}
        selected={binSelected}
        onToggleOne={toggleBinSelected}
        onSelectAll={selectAllBin}
        onClearSelection={clearBinSelection}
        onClose={closeRecycleBin}
        onRefresh={() => refreshBin()}
        onRestoreOne={handleRestoreOne}
        onRestoreSelected={handleRestoreSelected}
        onHardDeleteOne={handleHardDeleteOne}
        onHardDeleteSelected={handleHardDeleteSelected}
      />
    </div>
  );
};

export default SchedulePanel;
