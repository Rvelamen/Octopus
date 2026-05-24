import { useState, useCallback, useRef } from 'react';

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

  // Load collections tree
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

  // Load items
  const loadItems = useCallback(
    async (collectionId = selectedCollectionId, query = searchQuery, reset = true) => {
      setLoading(true);
      try {
        const offset = reset ? 0 : pagination.offset;
        const limit = pagination.limit;
        const response = await libraryWS.listItems({
          collection_id: collectionId,
          query: query || undefined,
          limit,
          offset,
        });
        if (response?.data) {
          const newItems = response.data.items || [];
          setItems(reset ? newItems : [...items, ...newItems]);
          setPagination(response.data.pagination || { total: 0, limit, offset });
        }
      } catch (e) {
        console.error('Failed to load items:', e);
      } finally {
        setLoading(false);
      }
    },
    [libraryWS, selectedCollectionId, searchQuery, pagination.limit, pagination.offset, items]
  );

  const handleLoadMore = useCallback(() => {
    if (items.length < pagination.total && !loading) {
      setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
      loadMoreRef.current = true;
    }
  }, [items.length, pagination.total, loading]);

  // Select item
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

  // Select collection
  const selectCollection = useCallback(
    async (collectionId) => {
      setSelectedCollectionId(collectionId);
      setSearchQuery('');
      await loadItems(collectionId, '', true);
    },
    [loadItems]
  );

  // Search
  const handleSearch = useCallback(
    async (query) => {
      setSearchQuery(query);
      await loadItems(selectedCollectionId, query, true);
    },
    [loadItems, selectedCollectionId]
  );

  // Create collection
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

  // Delete collection
  const deleteCollection = useCallback(
    async (id) => {
      try {
        await libraryWS.deleteCollection(id);
        if (selectedCollectionId === id) {
          setSelectedCollectionId(null);
        }
        await loadCollections();
      } catch (e) {
        console.error('Failed to delete collection:', e);
      }
    },
    [libraryWS, loadCollections, selectedCollectionId]
  );

  // Import PDF
  const importPdf = useCallback(
    async (file, metadata = {}, collectionIds) => {
      try {
        // First upload file to workspace temp location via workspace_write
        const arrayBuffer = await file.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        const hex = Array.from(bytes)
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('');
        const tempPath = `knowledge/library/_tmp_${Date.now()}_${file.name}`;
        await sendWSMessage('workspace_write', {
          path: tempPath,
          content: hex,
          encoding: 'hex',
        });

        // Then create library item
        const response = await libraryWS.createItem({
          temp_pdf_path: tempPath,
          metadata,
          collection_ids: collectionIds,
        });
        await loadItems(selectedCollectionId, searchQuery, true);
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import PDF:', e);
        throw e;
      }
    },
    [libraryWS, sendWSMessage, loadItems, selectedCollectionId, searchQuery]
  );

  // Import by DOI
  const importByDoi = useCallback(
    async (doi, collectionIds) => {
      try {
        const response = await libraryWS.importByDoi(doi, collectionIds);
        await loadItems(selectedCollectionId, searchQuery, true);
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import DOI:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, selectedCollectionId, searchQuery]
  );

  // Import by arXiv
  const importByArxiv = useCallback(
    async (arxivId, collectionIds) => {
      try {
        const response = await libraryWS.importByArxiv(arxivId, collectionIds);
        await loadItems(selectedCollectionId, searchQuery, true);
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to import arXiv:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, selectedCollectionId, searchQuery]
  );

  // Move item to collection
  const moveItemToCollection = useCallback(
    async (itemId, collectionId) => {
      try {
        await libraryWS.addToCollection(itemId, collectionId);
        await loadCollections();
        await loadItems(selectedCollectionId, searchQuery, true);
      } catch (e) {
        console.error('Failed to move item:', e);
      }
    },
    [libraryWS, loadCollections, loadItems, selectedCollectionId, searchQuery]
  );

  // Update item metadata
  const updateItemMetadata = useCallback(
    async (itemId, metadata) => {
      try {
        const response = await libraryWS.updateMetadata(itemId, metadata);
        if (response?.data?.item) {
          setSelectedItem(response.data.item);
        }
        await loadItems(selectedCollectionId, searchQuery, true);
        return response?.data?.item;
      } catch (e) {
        console.error('Failed to update item metadata:', e);
        throw e;
      }
    },
    [libraryWS, loadItems, selectedCollectionId, searchQuery]
  );

  // Delete item
  const deleteItem = useCallback(
    async (itemId) => {
      try {
        await libraryWS.deleteItem(itemId);
        if (selectedItem?.id === itemId) {
          setSelectedItem(null);
        }
        await loadItems(selectedCollectionId, searchQuery, true);
      } catch (e) {
        console.error('Failed to delete item:', e);
      }
    },
    [libraryWS, loadItems, selectedItem, selectedCollectionId, searchQuery]
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
  };
};

export default useLibrary;
