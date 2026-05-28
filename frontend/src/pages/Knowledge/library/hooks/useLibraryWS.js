import { useCallback } from 'react';

const useLibraryWS = (sendWSMessage) => {
  const send = useCallback(
    async (type, payload = {}, timeout = 30000) => {
      try {
        const response = await sendWSMessage(type, payload, timeout);
        return response;
      } catch (error) {
        console.error(`Library WS error [${type}]:`, error);
        throw error;
      }
    },
    [sendWSMessage]
  );

  const listItems = useCallback(
    (params = {}) => send('library_list', params),
    [send]
  );
  const getItem = useCallback(
    (itemId) => send('library_get', { item_id: itemId }),
    [send]
  );
  const createItem = useCallback(
    (params) => send('library_create', params, 60000),
    [send]
  );
  const updateMetadata = useCallback(
    (itemId, metadata) => send('library_update_meta', { item_id: itemId, metadata }),
    [send]
  );
  const deleteItem = useCallback(
    (itemId) => send('library_delete', { item_id: itemId }),
    [send]
  );
  const deleteItems = useCallback(
    (itemIds) => send('library_delete', { item_ids: itemIds }),
    [send]
  );
  const searchItems = useCallback(
    (query, collectionId) => send('library_search', { query, collection_id: collectionId }),
    [send]
  );
  const addAttachment = useCallback(
    (params) => send('library_add_attachment', params),
    [send]
  );
  const linkNote = useCallback(
    (itemId, notePath, relation = 'manual') =>
      send('library_link_note', { item_id: itemId, note_path: notePath, relation }),
    [send]
  );

  const listCollections = useCallback(
    (flat = false) => send('library_collection_list', { flat }),
    [send]
  );
  const createCollection = useCallback(
    (name, parentId, color) => send('library_collection_create', { name, parent_id: parentId, color }),
    [send]
  );
  const updateCollection = useCallback(
    (id, name, color) => send('library_collection_update', { id, name, color }),
    [send]
  );
  const deleteCollection = useCallback(
    (id) => send('library_collection_delete', { id }),
    [send]
  );
  const moveCollection = useCallback(
    (id, newParentId) => send('library_collection_move', { id, new_parent_id: newParentId }),
    [send]
  );
  const addToCollection = useCallback(
    (itemId, collectionId) => send('library_collection_add_item', { item_id: itemId, collection_id: collectionId }),
    [send]
  );
  const removeFromCollection = useCallback(
    (itemId, collectionId) =>
      send('library_collection_remove_item', { item_id: itemId, collection_id: collectionId }),
    [send]
  );

  const importByDoi = useCallback(
    (doi, collectionIds) => send('library_import_doi', { doi, collection_ids: collectionIds }, 120000),
    [send]
  );
  const importByArxiv = useCallback(
    (arxivId, collectionIds) => send('library_import_arxiv', { arxiv_id: arxivId, collection_ids: collectionIds }, 120000),
    [send]
  );

  const searchChunks = useCallback(
    (query, limit = 20) => send('library_search_chunks', { query, limit }),
    [send]
  );
  const aiExtractMetadata = useCallback(
    (itemId) => send('library_ai_extract_meta', { item_id: itemId }, 120000),
    [send]
  );

  return {
    listItems,
    getItem,
    createItem,
    updateMetadata,
    deleteItem,
    deleteItems,
    searchItems,
    addAttachment,
    linkNote,
    listCollections,
    createCollection,
    updateCollection,
    deleteCollection,
    moveCollection,
    addToCollection,
    removeFromCollection,
    importByDoi,
    importByArxiv,
    searchChunks,
    aiExtractMetadata,
  };
};

export default useLibraryWS;
