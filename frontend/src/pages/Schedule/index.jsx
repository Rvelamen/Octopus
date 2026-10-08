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
} from 'lucide-react';
import dayjs from 'dayjs';
import WindowDots from '@components/layout/WindowDots';
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

function MonthView({ cursor, events, onSelectEvent, onCreateAt }) {
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
        const visible = dayEvents.slice(0, 3);
        const more = dayEvents.length - visible.length;

        return (
          <div
            key={day.format('YYYY-MM-DD')}
            className={`month-cell${isOutside ? ' outside-month' : ''}${isToday ? ' is-today' : ''}`}
            onClick={(e) => {
              if (e.target.classList.contains('month-event')) return;
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
                  className={`month-event${ev.all_day ? ' all-day' : ''}`}
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
                </div>
              ))}
              {more > 0 && (
                <div
                  className="month-more"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCreateAt(day, dayEvents);
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
                    className="timegrid-event"
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
                className="timegrid-event"
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

function EventModal({ event, defaultStart, onSave, onDelete, onClose }) {
  const { t } = useTranslation();
  const isEdit = !!event;
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
      <div className="event-modal pixel-border" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <WindowDots />
          <span className="modal-title">{isEdit ? t('schedule.modal.edit') : t('schedule.modal.new')}</span>
          <button className="dialog-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label>{t('schedule.modal.title')}</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="pixel-input"
              placeholder={t('schedule.modal.titlePlaceholder')}
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={form.all_day}
                onChange={(e) => setForm({ ...form, all_day: e.target.checked })}
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
            />
          </div>
          <div className="form-group">
            <label>{t('schedule.modal.end')}</label>
            <input
              type="datetime-local"
              className="pixel-input"
              value={form.end.format('YYYY-MM-DDTHH:mm')}
              onChange={(e) => setForm({ ...form, end: dayjs(e.target.value) })}
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
          <div>
            {isEdit && (
              <button className="pixel-button danger" onClick={() => onDelete(event.id)}>
                <Trash2 size={14} /> {t('schedule.modal.delete')}
              </button>
            )}
          </div>
          <div className="right">
            <button className="pixel-button secondary" onClick={onClose}>
              {t('schedule.modal.cancel')}
            </button>
            <button
              className="pixel-button"
              onClick={handleSave}
              disabled={!form.title.trim()}
            >
              {isEdit ? t('schedule.modal.save') : t('schedule.modal.create')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Chat Drawer ----------

function ChatDrawer({ sendWSMessage, subscribe, instanceId }) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (endRef.current) {
      endRef.current.scrollTop = endRef.current.scrollHeight;
    }
  }, [messages, pending]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || pending) return;
    setInput('');
    const now = Date.now();
    setMessages((m) => [...m, { role: 'user', text, time: now }]);
    setPending(true);
    try {
      await sendWSMessage(
        'chat',
        { content: text, subagent_name: 'schedule-assistant', instance_id: instanceId },
        5000
      );
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: t('schedule.drawer.sendFailed', { error: e.message || e }),
          time: Date.now(),
        },
      ]);
      setPending(false);
      return;
    }
    setTimeout(() => {
      setPending(false);
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: t('schedule.drawer.doneHint'), time: Date.now() },
      ]);
    }, 3000);
  }, [input, pending, sendWSMessage, t, instanceId]);

  return (
    <div className="chat-drawer">
      <div className="chat-drawer-header">
        <div className="chat-drawer-title">
          <MessageSquare size={13} />
          {t('schedule.drawer.title')}
        </div>
        <div className="chat-drawer-subtitle">{t('schedule.drawer.subtitle')}</div>
      </div>
      <div className="chat-drawer-messages" ref={endRef}>
        {messages.length === 0 && !pending && (
          <div className="chat-drawer-empty">
            <MessageSquare size={28} />
            <div>{t('schedule.drawer.empty')}</div>
            <div className="chat-drawer-empty-hint">
              {t('schedule.drawer.emptyHint')}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-drawer-message ${m.role}`}>
            <div className="chat-drawer-message-text">{m.text}</div>
            {m.time && (
              <span className="chat-drawer-message-time">
                {dayjs(m.time).format('HH:mm')}
              </span>
            )}
          </div>
        ))}
        {pending && (
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
          <Send size={14} />
        </button>
      </div>
    </div>
  );
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

  const [range] = useMemo(() => visibleRange(view, cursor), [view, cursor]);

  const fetchEvents = useCallback(async () => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const resp = await sendWSMessage('schedule_list_events', {
        start_at_ms: range[0].valueOf(),
        end_at_ms: range[1].valueOf(),
      }, 8000);
      if (resp?.data?.events) {
        setEvents(resp.data.events);
      } else {
        setEvents([]);
      }
    } catch (e) {
      console.error('Failed to fetch schedule events:', e);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, range]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Live refresh on any schedule mutation broadcast
  useEffect(() => {
    if (!subscribe) return;
    const types = [
      'schedule_event_created',
      'schedule_event_updated',
      'schedule_event_deleted',
      'schedule_events_changed',
    ];
    const unsubs = types.map((tp) => subscribe(tp, () => fetchEvents()));
    return () => unsubs.forEach((u) => u && u());
  }, [subscribe, fetchEvents]);

  const handleSave = useCallback(
    async (data) => {
      try {
        if (selected) {
          await sendWSMessage('schedule_update_event', {
            event_id: selected.id,
            ...data,
          });
        } else {
          await sendWSMessage('schedule_create_event', data);
        }
        setSelected(null);
        setCreateAt(null);
        fetchEvents();
      } catch (e) {
        console.error('Save event failed:', e);
        alert(t('schedule.drawer.saveFailed', { error: e.message || e }));
      }
    },
    [selected, sendWSMessage, fetchEvents, t]
  );

  const handleDelete = useCallback(
    async (eventId) => {
      if (!confirm(t('schedule.modal.deleteConfirm'))) return;
      try {
        await sendWSMessage('schedule_delete_event', { event_id: eventId });
        setSelected(null);
        fetchEvents();
      } catch (e) {
        console.error('Delete failed:', e);
      }
    },
    [sendWSMessage, fetchEvents, t]
  );

  const onCreateAt = (d) => {
    setSelected(null);
    setCreateAt(d);
  };

  const onSelectEvent = (ev) => {
    setCreateAt(null);
    setSelected(ev);
  };

  return (
    <div className="schedule-panel-container">
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
              onClick={() => fetchEvents()}
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

      {drawerOpen && (
        <ChatDrawer
          sendWSMessage={sendWSMessage}
          subscribe={subscribe}
          instanceId={chatInstanceIdRef.current}
        />
      )}

      {(selected || createAt) && (
        <EventModal
          event={selected}
          defaultStart={createAt}
          onSave={handleSave}
          onDelete={handleDelete}
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
