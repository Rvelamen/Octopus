import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Bot, Check, ChevronLeft, Flower2, Hammer, Hand, LayoutGrid, Loader2, MapPin, Minus, Move, Plus, RotateCw, Save, Search, Send, Settings2, Sparkles, Sprout, X } from 'lucide-react';
import { Checkbox, Input, Modal, Pagination, message } from 'antd';
import LibrarySceneCanvas from './LibrarySceneCanvas';
import useLibraryScene from './useLibraryScene';
import { useWebSocket } from '../../../../contexts/WebSocketContext';
import { useLibraryChat } from '../hooks/useLibraryChat';
import { AREA_COLORS, SHELF_PAGE_SIZE } from './librarySceneState.mjs';
import './LibraryScene.css';

// Match `[book-123]` markers that the library-thinker emits when citing a book.
const BOOK_REF_PATTERN = /\[book-(\d+)\]/g;

function extractBookIds(content) {
  if (!content) return [];
  const ids = new Set();
  for (const match of content.matchAll(BOOK_REF_PATTERN)) {
    const id = Number(match[1]);
    if (Number.isFinite(id)) ids.add(id);
  }
  return Array.from(ids);
}

// Split a message body into text + inline book-ref pills so the marker
// itself disappears from the prose and is replaced by a tappable chip.
function renderTextWithBookRefs(content) {
  if (!content) return null;
  const parts = [];
  let lastIndex = 0;
  let key = 0;
  for (const match of content.matchAll(BOOK_REF_PATTERN)) {
    const start = match.index ?? 0;
    if (start > lastIndex) parts.push(content.slice(lastIndex, start));
    parts.push(
      <span key={`ref-${key++}`} className="library-scene-thinker-ref">
        <BookOpen size={11} />book-{match[1]}
      </span>,
    );
    lastIndex = start + match[0].length;
  }
  if (lastIndex < content.length) parts.push(content.slice(lastIndex));
  return parts;
}

function ThinkerBookRefs({ ids, libraryWS, onJump }) {
  const [items, setItems] = useState({});
  const [failed, setFailed] = useState(() => new Set());

  useEffect(() => {
    if (!ids.length) return undefined;
    let cancelled = false;
    const missing = ids.filter((id) => !(id in items) && !failed.has(id));
    if (!missing.length) return undefined;
    Promise.all(
      missing.map(async (id) => {
        try {
          const response = await libraryWS.getItem(id);
          return [id, response?.data?.item || null];
        } catch {
          return [id, null];
        }
      }),
    ).then((entries) => {
      if (cancelled) return;
      setItems((prev) => {
        const next = { ...prev };
        const nextFailed = new Set(failed);
        for (const [id, item] of entries) {
          if (item) next[id] = item;
          else nextFailed.add(id);
        }
        if (nextFailed.size !== failed.size || [...nextFailed].some((id) => !failed.has(id))) {
          setFailed(nextFailed);
        }
        return next;
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join(',')]);

  const cards = ids.map((id) => items[id]).filter(Boolean);
  if (!cards.length) return null;

  return (
    <ul className="library-scene-thinker-refs" aria-label="相关书籍">
      {cards.map((book) => {
        const canJump = Boolean(book.collection_id);
        return (
          <li key={book.id}>
            <button
              type="button"
              className="library-scene-thinker-ref-card"
              disabled={!canJump}
              onClick={() => canJump && onJump(book)}
              title={canJump ? '跳到这本书所在的书架' : '这本书尚未分配到书架'}
            >
              <span
                className="library-scene-thinker-ref-card-cover"
                style={{ background: AREA_COLORS[(book.id || 0) % AREA_COLORS.length] }}
              >
                <BookOpen size={16} />
              </span>
              <span className="library-scene-thinker-ref-card-text">
                <strong>{book.title || '未命名书籍'}</strong>
                <small>{book.authors?.join('、') || '作者未知'}</small>
              </span>
              <span className="library-scene-thinker-ref-card-go" aria-hidden>
                <MapPin size={13} />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function BookCover({ book }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="library-scene-book-cover" style={{ '--book-color': AREA_COLORS[book.id % AREA_COLORS.length] }}>
      <span className="library-scene-cover-title">{book.title || '未命名书籍'}</span>
      <BookOpen size={20} />
      {book.thumbnail_path && !failed && <img src={`/workspace/${book.thumbnail_path}`} alt="" onError={() => setFailed(true)} />}
    </span>
  );
}

function PlaceBooksModal({ area, libraryWS, onClose, onPlaced }) {
  const { listItems, addToCollection } = libraryWS;
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      listItems({ query: query || undefined, limit: 12, offset: (page - 1) * 12 }).then((response) => {
        if (cancelled) return;
        setItems(response.data.items || []);
        setTotal(response.data.pagination?.total || 0);
      }).catch((err) => { if (!cancelled) setError(err.message); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, query ? 200 : 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [listItems, page, query]);

  const place = async () => {
    setPlacing(true);
    const remaining = new Set(selected);
    try {
      for (const id of selected) {
        await addToCollection(id, area.id);
        remaining.delete(id);
      }
      message.success(`已将 ${selected.size} 本书移动到「${area.name}」`);
      onClose();
    } catch (err) {
      setSelected(remaining);
      setError(`部分书籍尚未移动，可重试：${err.message}`);
    } finally {
      await onPlaced();
      setPlacing(false);
    }
  };

  return (
    <Modal title={`为「${area.name}」放置书籍`} open onCancel={() => { if (!placing) onClose(); }} onOk={place}
      okText={`移动 ${selected.size} 本到此区域`} cancelText="取消" width={660} confirmLoading={placing}
      okButtonProps={{ disabled: !selected.size || loading }} maskClosable={!placing} closable={!placing}>
      <p className="library-scene-modal-note">这里使用已有图书馆资料。放置后，书籍会从原分类移动到这个区域。</p>
      <Input.Search aria-label="搜索要放置的书籍" placeholder="按书名、作者搜索" value={query} disabled={placing}
        onChange={(event) => { setQuery(event.target.value); setPage(1); }} />
      {error && <p role="alert" className="library-scene-error">{error}</p>}
      <div className="library-scene-picker" aria-busy={loading}>
        {loading ? <div className="library-scene-empty"><Loader2 className="library-scene-spin" />正在寻找书籍…</div> : items.map((book) => (
          <Checkbox key={book.id} disabled={placing} checked={selected.has(book.id)} onChange={(event) => {
            setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(book.id); else next.delete(book.id); return next; });
          }}>
            <span className="library-scene-picker-book"><BookCover book={book} /><span><strong>{book.title || '未命名书籍'}</strong><small>{book.authors?.join('、') || '作者未知'}</small></span></span>
          </Checkbox>
        ))}
        {!loading && !items.length && <div className="library-scene-empty">没有找到书籍。请先通过图书馆的“导入”添加资料。</div>}
      </div>
      <Pagination size="small" current={page} total={total} pageSize={12} onChange={setPage} showSizeChanger={false} disabled={placing} />
    </Modal>
  );
}

export default function LibraryScene({ collections, libraryWS, sendWSMessage, onCollectionsChanged }) {
  const { subscribe, unsubscribe } = useWebSocket();
  const state = useLibraryScene({ collections, libraryWS, sendWSMessage });
  // The Thinker in the Forest — bind new sessions to the dedicated
  // `library-thinker` subagent so its system prompt (book-finder + 读后感
  // writer) is in effect from the first turn.
  const thinkerChat = useLibraryChat({
    sendMessage: sendWSMessage,
    subscribe,
    unsubscribe,
    scope: { type: 'global' },
    agentConfigName: 'library-thinker',
  });
  const rendererRef = useRef(null);
  const stageRef = useRef(null);
  const [editing, setEditing] = useState(false);
  // 镜头操作模式:false = 拖动旋转(默认);true = 拖动平移
  const [panMode, setPanMode] = useState(false);
  const [hover, setHover] = useState(null);
  const [sceneError, setSceneError] = useState('');
  const [regionEditor, setRegionEditor] = useState(null);
  const [regionSaving, setRegionSaving] = useState(false);
  const [placingArea, setPlacingArea] = useState(null);
  const [readingId, setReadingId] = useState(null);
  // ── 思考者石像聊天 ──
  const [thinkerOpen, setThinkerOpen] = useState(false);
  const [thinkerInput, setThinkerInput] = useState('');
  const [quickQuery, setQuickQuery] = useState('');
  const [quickResults, setQuickResults] = useState([]);
  const [quickLoading, setQuickLoading] = useState(false);
  const readLock = useRef(false);
  const showSceneError = useCallback((error) => setSceneError(error), []);
  const openThinker = useCallback(() => {
    setEditing(false);
    setThinkerOpen(true);
    state.closeArea();
    setQuickResults([]);
  }, [state]);
  const closeThinker = useCallback(() => setThinkerOpen(false), []);
  const submitQuickSearch = useCallback(async (event) => {
    event?.preventDefault?.();
    const query = quickQuery.trim();
    if (!query) { setQuickResults([]); return; }
    setQuickLoading(true);
    try {
      const response = await libraryWS.searchItems(query);
      const list = response?.data?.items || response?.data?.results || response?.data || [];
      setQuickResults(Array.isArray(list) ? list.slice(0, 8) : []);
    } catch (err) {
      message.error(`快速找书失败：${err.message}`);
      setQuickResults([]);
    } finally { setQuickLoading(false); }
  }, [libraryWS, quickQuery]);
  const refreshBooks = useCallback(async () => {
    await onCollectionsChanged();
    state.refresh();
  }, [onCollectionsChanged, state]);
  const openArea = useCallback((id) => {
    setEditing(false);
    state.openArea(id);
  }, [state]);
  const closeArea = useCallback(() => { setHover(null); state.closeArea(); }, [state]);
  const openBookFromQuick = useCallback((book) => {
    const areaId = book.collection_id ?? book.collectionId;
    if (areaId && state.areas.some((area) => area.id === areaId)) {
      openArea(areaId);
    }
    closeThinker();
  }, [state.areas, openArea]);
  // 思考者在回复中引用 [book-NNN] 时,点击卡片跳到该书所在的书架。
  // 同时清掉搜索框与搜索结果,并展开对应的区域面板(不收起思考者侧栏,
  // 这样读者可以继续追问,或者直接点开书读)。
  const jumpToBookFromThinker = useCallback((book) => {
    const areaId = book.collection_id ?? book.collectionId;
    if (!areaId || !state.areas.some((area) => area.id === areaId)) {
      message.info('这本书还未上架,可以先去图书馆导入或在场景里放置。');
      return;
    }
    openArea(areaId);
    setQuickResults([]);
    setQuickQuery('');
  }, [openArea, state.areas]);
  const submitThinkerChat = useCallback((event) => {
    event?.preventDefault?.();
    const text = thinkerInput.trim();
    if (!text) return;
    thinkerChat.sendChat?.({ content: text });
    setThinkerInput('');
  }, [thinkerChat, thinkerInput]);
  const onHover = useCallback((value) => {
    if (!value) { setHover(null); return; }
    setHover({ ...value, x: Math.max(100, Math.min(value.x + 14, (stageRef.current?.clientWidth || 300) - 100)) });
  }, []);
  const booksByArea = useMemo(() => {
    const previews = { ...state.previews };
    if (state.activeArea) previews[state.activeArea.id] = state.books;
    return previews;
  }, [state.previews, state.activeArea, state.books]);

  const readBook = async (book) => {
    if (readLock.current) return;
    const nativeReader = window.electronAPI?.openPdfWindow;
    // Open during the user gesture so an asynchronous metadata fetch cannot trigger a popup blocker.
    const readerWindow = nativeReader ? null : window.open('about:blank', `octopus-pdf-${book.id}`, 'popup,width=1150,height=850');
    if (!nativeReader && !readerWindow) { message.warning('请允许打开阅读窗口后再试。'); return; }
    if (readerWindow) readerWindow.document.body.textContent = '正在打开书籍…';
    readLock.current = true;
    setReadingId(book.id);
    try {
      const response = await libraryWS.getItem(book.id);
      const item = response.data.item;
      if (!item?.library_path || !item.attachments?.some((attachment) => attachment.rel_path === 'main.pdf')) {
        readerWindow?.close();
        message.info('这本书尚未附带 PDF 文件，请先在图书馆中导入正文。');
        return;
      }
      if (nativeReader) await nativeReader(item.library_path, item.title, item.id);
      else {
        const url = new URL(window.location.href);
        url.hash = `/pdf-viewer?${new URLSearchParams({ path: item.library_path, title: item.title, itemId: String(item.id) })}`;
        readerWindow.location.replace(url.href);
      }
    } catch (err) { readerWindow?.close(); message.error(`打开书籍失败：${err.message}`); }
    finally { readLock.current = false; setReadingId(null); }
  };
  const saveRegion = async () => {
    if (regionSaving || !regionEditor?.name.trim()) return;
    setRegionSaving(true);
    try {
      if (regionEditor.id) await libraryWS.updateCollection(regionEditor.id, regionEditor.name.trim(), regionEditor.color);
      else await libraryWS.createCollection(regionEditor.name.trim(), null, regionEditor.color);
      await refreshBooks();
      setRegionEditor(null);
      message.success('区域已保存');
    } catch (err) { message.error(`保存区域失败：${err.message}`); }
    finally { setRegionSaving(false); }
  };
  const saveLayout = async () => {
    try { await state.saveLayout(); message.success('图书馆布置已保存'); }
    catch (err) { message.error(`布置尚未保存，请重试：${err.message}`); }
  };

  return (
    <section className="library-scene" aria-label="图书馆场景">
      <header className="library-scene-header">
        <div className="library-scene-brand"><span className="library-scene-brand-icon"><Sprout size={25} /></span><div><h2>林间图书馆</h2><p>给每一本书，一个温暖的位置</p></div></div>
        <div className="library-scene-header-actions">
          <span className="library-scene-area-count">{state.areas.length} 个图书区域</span>
          <button type="button" className={`library-scene-button ${editing ? 'is-active' : ''}`} aria-pressed={editing}
            disabled={!state.layoutReady || !!state.layoutError} onClick={() => { closeArea(); setEditing((current) => !current); }}><Move size={15} />{editing ? '完成布置' : '布置区域'}</button>
          <button type="button" className="library-scene-button library-scene-button-primary" onClick={() => setRegionEditor({ name: '', color: AREA_COLORS[state.areas.length % AREA_COLORS.length] })}><Plus size={16} />新增区域</button>
        </div>
      </header>
      {state.layoutError && <div className="library-scene-error" role="alert">{state.layoutError}</div>}
      {state.dirty && <div className="library-scene-save-bar"><span>区域位置已调整，保存后下次进入会保留布置。</span><button type="button" className="library-scene-button" onClick={saveLayout} disabled={state.saving || !!state.layoutError}>{state.saving ? <Loader2 className="library-scene-spin" size={14} /> : <Save size={14} />}保存布置</button></div>}
      <div className="library-scene-body">
        <div className="library-scene-stage" ref={stageRef}>
          {!sceneError && <LibrarySceneCanvas ref={rendererRef} areas={state.areas} booksByArea={booksByArea} activeId={state.activeArea?.id ?? null} panMode={panMode}
            editing={editing} onOpen={openArea} onRead={readBook} onMove={state.updatePosition} onHover={onHover} onThinker={openThinker} onError={showSceneError} />}
          {sceneError && <div className="library-scene-empty library-scene-render-error" role="alert"><Flower2 size={32} /><strong>三维场景暂时无法显示</strong><span>{sceneError}</span><p>仍可使用下方区域按钮挑选书籍。</p></div>}
          <div className="library-scene-camera-controls" aria-label="镜头控制">
            <button type="button" aria-label="返回图书馆全景" title="返回全景" onClick={() => { closeArea(); rendererRef.current?.reset(); }}><LayoutGrid size={17} /></button>
            <button type="button" className={panMode ? 'is-active' : ''} aria-pressed={panMode} aria-label="切换为拖动平移模式" title={panMode ? '当前:拖动 = 平移(再点切换回旋转)' : '当前:拖动 = 旋转(点击切换为平移)'} onClick={() => setPanMode((value) => !value)}>
              {panMode ? <Hand size={17} /> : <RotateCw size={17} />}
            </button>
            <button type="button" aria-label="拉近镜头" title="拉近镜头" onClick={() => rendererRef.current?.zoom(1)}><Plus size={17} /></button>
            <button type="button" aria-label="拉远镜头" title="拉远镜头" onClick={() => rendererRef.current?.zoom(-1)}><Minus size={17} /></button>
          </div>
          {editing && <div className="library-scene-edit-hint"><Move size={16} />拖动地毯或书架来调整区域位置<button type="button" onClick={state.resetLayout}>自动排列</button></div>}
          {hover && !editing && hover.type === 'thinker' && <div className="library-scene-hover library-scene-hover-thinker" style={{ left: hover.x, top: Math.max(12, hover.y - 70) }}><span className="library-scene-hover-icon"><Bot size={18} /></span><span>向思考者提问</span><small>点击打开对话，快速找书</small></div>}
          {hover && !editing && hover.book && <div className="library-scene-hover" style={{ left: hover.x, top: Math.max(12, hover.y - 84) }}><BookCover book={hover.book} /><span>{hover.book.title}</span><small>{state.activeArea ? '点击阅读' : '点击展开书架'}</small></div>}
          <div className="library-scene-camera-hint" aria-label="视角操作提示">
            <span><kbd>左键拖动</kbd> {panMode ? '平移' : '旋转'}</span>
            {!panMode && <span><kbd>右键拖动</kbd> 平移</span>}
            <span><kbd>滚轮</kbd> 缩放</span>
          </div>
          <div className="library-scene-area-nav"><p><Sprout size={15} />{editing ? '布置属于你的阅读角落' : '点击一块地毯，看看书架上的故事'}</p><div>
            {state.areas.map((area) => <button type="button" key={area.id} className={state.activeArea?.id === area.id ? 'is-active' : ''} style={{ '--area-color': area.color }} onClick={() => openArea(area.id)}><span />{area.name}<small>{area.count || 0}</small></button>)}
            {!state.areas.length && <button type="button" onClick={() => setRegionEditor({ name: '', color: AREA_COLORS[0] })}><Plus size={15} />创建第一个区域</button>}
            <button type="button" className="library-scene-area-nav-thinker" onClick={openThinker} title="向思考者提问，让它帮你找一本书"><Bot size={15} />问思考者</button>
          </div></div>
        </div>
        {state.activeArea && <aside className="library-scene-shelf-panel" aria-label={`${state.activeArea.name}的书架`}>
          <header><button type="button" className="library-scene-back" onClick={closeArea}><ChevronLeft size={16} />全景</button><button type="button" className="library-scene-icon-button" aria-label="关闭书架" onClick={closeArea}><X size={17} /></button></header>
          <div className="library-scene-shelf-heading"><span style={{ background: state.activeArea.color }} /><h3>{state.activeArea.name}</h3><p>{state.total} 本书 · 挑一本开始阅读</p></div>
          {state.activeArea.id > 2 && <div className="library-scene-shelf-actions"><button type="button" className="library-scene-button" onClick={() => setPlacingArea(state.activeArea)}><Plus size={14} />放置书籍</button><button type="button" className="library-scene-icon-button" aria-label="设置这个区域" title="设置区域名称和颜色" onClick={() => setRegionEditor({ id: state.activeArea.id, name: state.activeArea.name, color: state.activeArea.color })}><Settings2 size={17} /></button></div>}
          {state.error && <div className="library-scene-error" role="alert">{state.error}<button type="button" onClick={state.refresh}>重试</button></div>}
          <div className="library-scene-book-grid" aria-busy={state.loading}>
            {state.loading ? <div className="library-scene-empty"><Loader2 className="library-scene-spin" />正在展开书架…</div> : state.books.map((book) => <button type="button" key={book.id} className={`library-scene-book ${hover?.book.id === book.id ? 'is-hovered' : ''}`} title={book.title} aria-label={`阅读《${book.title || '未命名书籍'}》`} disabled={readingId !== null} onClick={() => readBook(book)}><BookCover book={book} /><strong>{book.title || '未命名书籍'}</strong><small>{readingId === book.id ? '正在打开…' : '点击阅读'}</small></button>)}
            {!state.loading && !state.books.length && !state.error && <div className="library-scene-empty"><BookOpen size={34} /><strong>书架还空着</strong><span>{state.activeArea.id > 2 ? '点击“放置书籍”，把喜欢的书放进来。' : '通过图书馆的“导入”添加第一本书。'}</span></div>}
          </div>
          <footer><Pagination size="small" current={state.page} total={state.total} pageSize={SHELF_PAGE_SIZE} onChange={state.setPage} showSizeChanger={false} hideOnSinglePage /></footer>
        </aside>}
        {thinkerOpen && <aside className="library-scene-thinker" aria-label="思考者石像对话">
          <header><button type="button" className="library-scene-back" onClick={closeThinker}><ChevronLeft size={16} />全景</button><div className="library-scene-thinker-title"><span className="library-scene-thinker-icon"><Bot size={18} /></span><div><h3>思考者 · 问书</h3><p>描述你想读什么，或直接搜索书名</p></div></div><button type="button" className="library-scene-icon-button" aria-label="关闭对话" onClick={closeThinker}><X size={17} /></button></header>
          <form className="library-scene-thinker-quick" onSubmit={submitQuickSearch}>
            <label htmlFor="library-scene-thinker-search"><Search size={16} />快速找书</label>
            <div className="library-scene-thinker-quick-row">
              <Input id="library-scene-thinker-search" placeholder="按书名、作者搜索" value={quickQuery} onChange={(event) => setQuickQuery(event.target.value)} disabled={quickLoading} allowClear onPressEnter={submitQuickSearch} />
              <button type="submit" className="library-scene-button library-scene-button-primary" disabled={quickLoading}>{quickLoading ? <Loader2 className="library-scene-spin" size={14} /> : <Search size={14} />}搜索</button>
            </div>
            {quickResults.length > 0 && <ul className="library-scene-thinker-results" aria-label="搜索结果">
              {quickResults.map((book) => <li key={book.id}>
                <button type="button" className="library-scene-thinker-result" onClick={() => openBookFromQuick(book)}>
                  <span className="library-scene-thinker-result-cover" style={{ background: AREA_COLORS[book.id % AREA_COLORS.length] }}><BookOpen size={18} /></span>
                  <span className="library-scene-thinker-result-text"><strong>{book.title || '未命名书籍'}</strong><small>{book.authors?.join('、') || '作者未知'}</small></span>
                  <span className="library-scene-thinker-result-go" aria-hidden>→</span>
                </button>
              </li>)}
            </ul>}
            {!quickLoading && quickQuery && !quickResults.length && <p className="library-scene-thinker-empty">没有匹配的书籍。试试在下方和思考者聊聊。</p>}
          </form>
          <div className="library-scene-thinker-chat" aria-busy={thinkerChat.loading}>
            <p className="library-scene-thinker-label"><Sparkles size={14} />与思考者对话</p>
            <ul className="library-scene-thinker-messages">
              {(thinkerChat.messages || []).map((messageItem, index) => {
                const role = messageItem.role || 'assistant';
                if (role === 'tool') {
                  const meta = messageItem.metadata || {};
                  const isDone = meta.status === 'done';
                  return (
                    <li key={index} className="library-scene-thinker-tool">
                      <span className={`library-scene-thinker-tool-icon ${isDone ? 'is-done' : 'is-running'}`}>
                        {isDone ? <Check size={12} /> : <Loader2 className="library-scene-spin" size={12} />}
                      </span>
                      <span className="library-scene-thinker-tool-body">
                        <strong><Hammer size={11} />{meta.tool || 'tool'}</strong>
                        {meta.result && <small>{String(meta.result).slice(0, 160)}{String(meta.result).length > 160 ? '…' : ''}</small>}
                      </span>
                    </li>
                  );
                }
                if (role === 'thinking') {
                  return (
                    <li key={index} className="library-scene-thinker-thinking">
                      <span className="library-scene-thinker-thinking-label"><Sparkles size={11} />思考中</span>
                      <span className="library-scene-thinker-thinking-body">{messageItem.content}</span>
                    </li>
                  );
                }
                const isAssistant = role !== 'user';
                const bookIds = isAssistant ? extractBookIds(messageItem.content) : [];
                return (
                  <li key={index} className={`library-scene-thinker-message ${isAssistant ? 'is-assistant' : 'is-user'}`}>
                    <span>{isAssistant ? renderTextWithBookRefs(messageItem.content) : messageItem.content}</span>
                    {isAssistant && bookIds.length > 0 && (
                      <ThinkerBookRefs ids={bookIds} libraryWS={libraryWS} onJump={jumpToBookFromThinker} />
                    )}
                  </li>
                );
              })}
              {thinkerChat.loading && <li className="library-scene-thinker-message is-assistant is-pending"><span><Loader2 className="library-scene-spin" size={14} /> 思考中…</span></li>}
              {!(thinkerChat.messages || []).length && !thinkerChat.loading && <li className="library-scene-thinker-empty">试着问：「想读一些关于城市的随笔，有推荐吗？」</li>}
            </ul>
            <form className="library-scene-thinker-input" onSubmit={submitThinkerChat}>
              <Input.TextArea aria-label="向思考者提问" placeholder="向思考者描述你想读的书…" value={thinkerInput} autoSize={{ minRows: 1, maxRows: 4 }} onChange={(event) => setThinkerInput(event.target.value)} onPressEnter={(event) => { if (!event.shiftKey) submitThinkerChat(event); }} disabled={thinkerChat.loading} />
              <button type="submit" className="library-scene-button library-scene-button-primary" disabled={!thinkerInput.trim() || thinkerChat.loading}><Send size={14} />发送</button>
            </form>
          </div>
        </aside>}
      </div>
      <Modal title={regionEditor?.id ? '设置图书区域' : '新的阅读角落'} open={!!regionEditor} onCancel={() => { if (!regionSaving) setRegionEditor(null); }} onOk={saveRegion} okText="保存区域" cancelText="取消" confirmLoading={regionSaving} okButtonProps={{ disabled: !regionEditor?.name.trim() }}>
        {regionEditor && <div className="library-scene-region-form"><label htmlFor="library-scene-region-name">区域名称</label><Input id="library-scene-region-name" value={regionEditor.name} maxLength={60} placeholder="例如：文学小屋、科学探索、我的收藏" onChange={(event) => setRegionEditor({ ...regionEditor, name: event.target.value })} onPressEnter={saveRegion} disabled={regionSaving} /><label htmlFor="library-scene-region-color">地毯颜色</label><div className="library-scene-color-palette">{AREA_COLORS.map((color) => <button type="button" key={color} style={{ background: color }} aria-label={`使用颜色 ${color}`} aria-pressed={regionEditor.color === color} onClick={() => setRegionEditor({ ...regionEditor, color })}>{regionEditor.color === color && <Check size={17} />}</button>)}<input id="library-scene-region-color" type="color" value={regionEditor.color} onChange={(event) => setRegionEditor({ ...regionEditor, color: event.target.value })} /></div><p className="library-scene-modal-note">区域对应图书馆分类，名称与书籍配置会同步保存。</p></div>}
      </Modal>
      {placingArea && <PlaceBooksModal area={placingArea} libraryWS={libraryWS} onClose={() => setPlacingArea(null)} onPlaced={refreshBooks} />}
    </section>
  );
}
