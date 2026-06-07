import { useState, useCallback, useRef } from 'react';

const getApiPort = async () => {
  if (window.electronAPI?.getApiPort) {
    try {
      const port = await window.electronAPI.getApiPort();
      if (port) return port;
    } catch {}
  }
  return window.location.port || '18791';
};

const uploadPdf = async (file, onProgress) => {
  const port = await getApiPort();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `http://127.0.0.1:${port}/api/library/upload`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(e.loaded / e.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const result = JSON.parse(xhr.responseText);
          if (result.success) {
            resolve(result.temp_path);
          } else {
            reject(new Error(result.error || 'Upload failed'));
          }
        } catch {
          reject(new Error('Invalid response'));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.ontimeout = () => reject(new Error('Upload timeout'));
    xhr.timeout = 300000; // 5 minutes for large PDFs

    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
};

const useLibrary = (libraryWS, sendWSMessage) => {
  const [collections, setCollections] = useState([]);
  const [items, setItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [viewMode, setViewMode] = useState('card'); // 'card' | 'list' | 'table'
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ total: 0, limit: 50, offset: 0 });
  const loadMoreRef = useRef(false);
  const searchTimeoutRef = useRef(null);

  // ── Load collections tree ──
  const loadCollections = useCallback(async () => {
    try {
      const response = await libraryWS.listCollections(false);
      if (response?.data?.collections) {
        setCollections(response.data.collections);
      }
    } catch (e) {
      console.error('Failed to load collections:', e);
    }
  }, [libraryWS]);

  // ── Load items (core, no stale closure) ──
  // offset is passed explicitly to avoid depending on pagination.offset
  const loadItems = useCallback(
    async (collectionId, query, offset = 0) => {
      setLoading(true);
      try {
        const limit = pagination.limit;
        const response = await libraryWS.listItems({
          collection_id: collectionId ?? undefined,
          query: query || undefined,
          limit,
          offset,
        });
        if (response?.data) {
          const newItems = response.data.items || [];
          const isReset = offset === 0;
          setItems((prev) => (isReset ? newItems : [...prev, ...newItems]));
          setPagination(response.data.pagination || { total: 0, limit, offset });
        }
      } catch (e) {
        console.error('Failed to load items:', e);
      } finally {
        setLoading(false);
      }
    },
    [libraryWS, pagination.limit]
  );

  // ── Load more (scroll pagination) ──
  const handleLoadMore = useCallback(() => {
    if (items.length >= pagination.total || loading) return;
    const nextOffset = pagination.offset + pagination.limit;
    loadItems(selectedCollectionId, searchQuery, nextOffset);
  }, [items.length, pagination.total, pagination.offset, pagination.limit, loading, loadItems, selectedCollectionId, searchQuery]);

  // ── Select item (re-fetch from server to avoid stale data) ──
  const selectItem = useCallback(
    async (itemId) => {
      if (!itemId) {
        setSelectedItem(null);
        return;
      }
      try {
        const response = await libraryWS.getItem(itemId);
        if (response?.data?.item) {
          setSelectedItem(response.data.item);
        }
      } catch (e) {
        console.error('Failed to get item:', e);
      }
    },
    [libraryWS]
  );

  // ── Select collection ──
  const selectCollection = useCallback(
    async (collectionId) => {
      setSelectedCollectionId(collectionId);
      setSearchQuery('');
      await loadItems(collectionId, '', 0);
    },
    [loadItems]
  );

  // ── Search with debounce ──
  const handleSearch = useCallback(
    (query) => {
      setSearchQuery(query);
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
      searchTimeoutRef.current = setTimeout(() => {
        loadItems(selectedCollectionId, query, 0);
      }, 300);
    },
    [loadItems, selectedCollectionId]
  );

  // ── Create collection ──
  const createCollection = useCallback(
    async (name, parentId, color) => {
      try {
        await libraryWS.createCollection(name, parentId, color);
        await loadCollections();
      } catch (e) {
        console.error('Failed to create collection:', e);
      }
    },
    [libraryWS, loadCollections]
  );

  // ── Delete collection ──
  const deleteCollection = useCallback(
    async (id) => {
      try {
        await libraryWS.deleteCollection(id);
        const wasSelected = selectedCollectionId === id;
        if (wasSelected) {
          setSelectedCollectionId(null);
        }
        await loadCollections();
        // Refresh items: if deleted collection was selected, show all; else refresh current filter
        await loadItems(wasSelected ? null : selectedCollectionId, searchQuery, 0);
      } catch (e) {
        console.error('Failed to delete collection:', e);
      }
    },
    [libraryWS, loadCollections, loadItems, selectedCollectionId, searchQuery]
  );

  // ── Import PDF via HTTP upload ──
  const importPdf = useCallback(
    async (file, metadata = {}, collectionIds, onProgress) => {
      try {
        const tempPath = await uploadPdf(file, onProgress);
        const response = await libraryWS.createItem({
          temp_pdf_path: tempPath,
          metadata,
          collection_ids: collectionIds,
        });
        await loadItems(selectedCollectionId, searchQuery, 0);
        await loadCollections(); // update collection counts
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import PDF:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, loadCollections, selectedCollectionId, searchQuery]
  );

  // ── Import by DOI ──
  const importByDoi = useCallback(
    async (doi, collectionIds) => {
      try {
        const response = await libraryWS.importByDoi(doi, collectionIds);
        await loadItems(selectedCollectionId, searchQuery, 0);
        await loadCollections();
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import DOI:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, loadCollections, selectedCollectionId, searchQuery]
  );

  // ── Import by arXiv ──
  const importByArxiv = useCallback(
    async (arxivId, collectionIds) => {
      try {
        const response = await libraryWS.importByArxiv(arxivId, collectionIds);
        await loadItems(selectedCollectionId, searchQuery, 0);
        await loadCollections();
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import arXiv:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, loadCollections, selectedCollectionId, searchQuery]
  );

  // ── Move item to collection ──
  const moveItemToCollection = useCallback(
    async (itemId, collectionId) => {
      try {
        await libraryWS.addToCollection(itemId, collectionId);
        await loadCollections();
        await loadItems(selectedCollectionId, searchQuery, 0);
        // Refresh selected item if open
        if (selectedItem?.id === itemId) {
          await selectItem(itemId);
        }
      } catch (e) {
        console.error('Failed to move item:', e);
      }
    },
    [libraryWS, loadCollections, loadItems, selectItem, selectedItem, selectedCollectionId, searchQuery]
  );

  // ── Update item metadata ──
  const updateItemMetadata = useCallback(
    async (itemId, metadata) => {
      try {
        const response = await libraryWS.updateMetadata(itemId, metadata);
        if (response?.data?.item) {
          setSelectedItem(response.data.item);
        }
        await loadItems(selectedCollectionId, searchQuery, 0);
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to update item metadata:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, selectedCollectionId, searchQuery]
  );

  // ── Delete item ──
  const deleteItem = useCallback(
    async (itemId) => {
      try {
        await libraryWS.deleteItem(itemId);
        if (selectedItem?.id === itemId) {
          setSelectedItem(null);
        }
        await loadItems(selectedCollectionId, searchQuery, 0);
        await loadCollections(); // update counts
      } catch (e) {
        console.error('Failed to delete item:', e);
      }
    },
    [libraryWS, loadItems, loadCollections, selectedItem, selectedCollectionId, searchQuery]
  );

  // ── Delete multiple items ──
  const deleteItems = useCallback(
    async (itemIds) => {
      try {
        await libraryWS.deleteItems(itemIds);
        if (selectedItem && itemIds.includes(selectedItem.id)) {
          setSelectedItem(null);
        }
        await loadItems(selectedCollectionId, searchQuery, 0);
        await loadCollections(); // update counts
      } catch (e) {
        console.error('Failed to delete items:', e);
      }
    },
    [libraryWS, loadItems, loadCollections, selectedItem, selectedCollectionId, searchQuery]
  );

  // ── AI Extract metadata and auto-save ──
  const aiExtractAndSave = useCallback(
    async (itemId) => {
      const extractResp = await libraryWS.aiExtractMetadata(itemId);
      const meta = extractResp?.data?.metadata;
      if (!meta) throw new Error('AI extraction returned no metadata');
      const updateResp = await libraryWS.updateMetadata(itemId, {
        title: meta.title,
        authors: meta.authors || [],
        year: meta.year,
        venue: meta.venue,
        doi: meta.doi,
        url: meta.url,
        abstract: meta.abstract,
        tags: meta.tags || [],
        citekey: meta.citekey,
      });
      await loadItems(selectedCollectionId, searchQuery, 0);
      if (selectedItem?.id === itemId) {
        setSelectedItem(updateResp?.data?.item || selectedItem);
      }
      return updateResp?.data?.item;
    },
    [libraryWS, loadItems, selectedCollectionId, searchQuery, selectedItem]
  );

  // ── Generate AI note (distill) ──
  const generateNote = useCallback(
    async (item) => {
      if (!item?.id || !item.library_path) throw new Error('Item missing path');
      const sourcePath = `${item.library_path}/main.pdf`;
      const outputPath = `${item.library_path}/notes/summary.md`;
      const prompt = `Please read this academic paper and generate a comprehensive summary note in Markdown format with the following structure:

---
title: "${item.title || 'Untitled'}"
authors: [${(item.authors || []).map((a) => `"${a}"`).join(', ')}]
year: ${item.year || 'N/A'}
venue: "${item.venue || ''}"
tags: [${(item.tags || []).map((t) => `"${t}"`).join(', ')}]
---

## Summary
[A concise 2-3 paragraph summary of the paper's main contributions]

## Key Contributions
- [List the main contributions]

## Methodology
[Describe the methods/approaches used]

## Results
[Summarize the key findings and experimental results]

## Insights & Implications
[Your analysis of the paper's significance and potential impact]

## Related Work Connections
[How this work connects to other papers in the field, use [[wiki-links]] if relevant]

Please write in English, use academic tone, and include specific details from the paper.`;

      await sendWSMessage(
        'knowledge_distill',
        {
          source_path: sourcePath,
          prompt,
          target_path: outputPath,
          template: 'custom',
          vault: 'library',
          options: { task_id: `library-note-${item.id}-${Date.now()}` },
        },
        30000
      );
      // Refresh item to update has_notes flag
      await loadItems(selectedCollectionId, searchQuery, 0);
      return true;
    },
    [sendWSMessage, loadItems, selectedCollectionId, searchQuery]
  );

  return {
    collections,
    items,
    selectedItem,
    selectedCollectionId,
    viewMode,
    setViewMode,
    searchQuery,
    loading,
    pagination,
    loadCollections,
    loadItems,
    handleLoadMore,
    selectItem,
    selectCollection,
    handleSearch,
    createCollection,
    deleteCollection,
    importPdf,
    importByDoi,
    importByArxiv,
    moveItemToCollection,
    updateItemMetadata,
    deleteItem,
    deleteItems,
    aiExtractAndSave,
    generateNote,
  };
};

export default useLibrary;
