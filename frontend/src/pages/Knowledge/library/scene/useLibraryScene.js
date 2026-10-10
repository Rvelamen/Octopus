import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getSceneAreas, moveArea, normalizeLayout, SCENE_LAYOUT_PATH, SHELF_PAGE_SIZE } from './librarySceneState.mjs';

export default function useLibraryScene({ collections, libraryWS, sendWSMessage }) {
  const { listItems } = libraryWS;
  const [layout, setLayout] = useState(() => normalizeLayout(null));
  const [layoutReady, setLayoutReady] = useState(false);
  const [layoutError, setLayoutError] = useState('');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [page, setPage] = useState(1);
  const [books, setBooks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [previews, setPreviews] = useState({});
  const [revision, setRevision] = useState(0);
  const requestRef = useRef(0);
  const editVersion = useRef(0);
  const areas = useMemo(() => getSceneAreas(collections, layout), [collections, layout]);
  const activeArea = areas.find((area) => area.id === activeId) || null;
  const activeCollectionId = activeArea?.id ?? null;

  useEffect(() => {
    let cancelled = false;
    sendWSMessage('workspace_read', { path: SCENE_LAYOUT_PATH }).then((response) => {
      const parsed = JSON.parse(response.data.content);
      if (parsed.version !== 1) throw new Error('布置文件版本暂不支持');
      if (!cancelled) setLayout(normalizeLayout(parsed));
    }).catch((err) => {
      if (!cancelled && !/File does not exist/i.test(err.message)) {
        setLayoutError(`读取布置失败：${err.message}。当前改动不会覆盖原文件。`);
      }
    }).finally(() => { if (!cancelled) setLayoutReady(true); });
    return () => { cancelled = true; };
  }, [sendWSMessage]);

  // Refresh shelf previews when membership changes, not when furniture is moved.
  const previewKey = useMemo(() => areas.map((area) => `${area.id}:${area.count || 0}`).join(','), [areas]);
  useEffect(() => {
    let cancelled = false;
    const ids = previewKey.split(',').filter(Boolean).map((entry) => Number(entry.split(':')[0]));
    Promise.all(ids.map(async (id) => {
      const response = await listItems({ collection_id: id, limit: SHELF_PAGE_SIZE, offset: 0 });
      return [id, response.data.items || []];
    })).then((entries) => {
      if (!cancelled) setPreviews(Object.fromEntries(entries));
    }).catch((err) => { if (!cancelled) setError(`书架加载失败：${err.message}`); });
    return () => { cancelled = true; };
  }, [previewKey, listItems, revision]);

  useEffect(() => {
    if (!activeCollectionId) return;
    const request = ++requestRef.current;
    listItems({ collection_id: activeCollectionId, limit: SHELF_PAGE_SIZE, offset: (page - 1) * SHELF_PAGE_SIZE })
      .then((response) => {
        if (request !== requestRef.current) return;
        const nextTotal = response.data.pagination?.total || 0;
        const lastPage = Math.max(1, Math.ceil(nextTotal / SHELF_PAGE_SIZE));
        if (page > lastPage) { requestRef.current += 1; setPage(lastPage); return; }
        setBooks(response.data.items || []);
        setTotal(nextTotal);
      }).catch((err) => { if (request === requestRef.current) setError(`书籍加载失败：${err.message}`); })
      .finally(() => { if (request === requestRef.current) setLoading(false); });
    return () => { requestRef.current += 1; };
  }, [activeCollectionId, page, listItems, revision]);

  const openArea = useCallback((id) => {
    if (id === activeId && page === 1) return;
    setBooks([]); setTotal(0); setError(''); setLoading(true);
    setPage(1); setActiveId(id);
  }, [activeId, page]);
  const closeArea = useCallback(() => {
    setActiveId(null); setBooks([]); setTotal(0); setLoading(false); setError('');
  }, []);
  const changePage = useCallback((nextPage) => {
    if (nextPage === page) return;
    setBooks([]); setError(''); setLoading(true); setPage(nextPage);
  }, [page]);
  const updatePosition = useCallback((id, position) => {
    editVersion.current += 1;
    setLayout((current) => moveArea(current, id, position));
    setDirty(true);
  }, []);
  const saveLayout = useCallback(async () => {
    if (!layoutReady || layoutError || saving) return;
    const version = editVersion.current;
    setSaving(true);
    try {
      await sendWSMessage('workspace_write', { path: SCENE_LAYOUT_PATH, content: JSON.stringify(layout, null, 2) });
      if (version === editVersion.current) setDirty(false);
    } finally { setSaving(false); }
  }, [layout, layoutReady, layoutError, saving, sendWSMessage]);
  const resetLayout = useCallback(() => {
    editVersion.current += 1;
    setLayout(normalizeLayout(null));
    setDirty(true);
  }, []);
  const refresh = useCallback(() => {
    setError('');
    if (activeCollectionId) setLoading(true);
    setRevision((value) => value + 1);
  }, [activeCollectionId]);

  return {
    areas, activeArea, openArea, closeArea, books, total,
    page, setPage: changePage, loading, error, previews, refresh,
    layoutReady, layoutError, dirty, saving, updatePosition, saveLayout, resetLayout,
  };
}
