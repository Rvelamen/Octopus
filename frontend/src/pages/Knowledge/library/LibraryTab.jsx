import React, { useState, useEffect } from 'react';
import { Library, Search, Upload, Plus, Grid3X3, List, Table2 } from 'lucide-react';
import { Input, Button, Segmented, Drawer } from 'antd';
import useLibraryWS from './hooks/useLibraryWS';
import useLibrary from './hooks/useLibrary';
import LibrarySidebar from './LibrarySidebar';
import LibraryListView from './LibraryListView';
import LibraryItemDetail from './LibraryItemDetail';
import LibraryImportModal from './LibraryImportModal';
import LibraryCollectionModal from './LibraryCollectionModal';

const LibraryTab = ({ sendWSMessage }) => {
  const libraryWS = useLibraryWS(sendWSMessage);
  const {
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
  } = useLibrary(libraryWS, sendWSMessage);

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [collectionModalOpen, setCollectionModalOpen] = useState(false);

  // Initial load
  useEffect(() => {
    loadCollections();
    loadItems(null, '', true);
  }, []);

  const viewOptions = [
    { value: 'card', icon: <Grid3X3 size={14} /> },
    { value: 'list', icon: <List size={14} /> },
    { value: 'table', icon: <Table2 size={14} /> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden' }}>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '8px 16px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <Library size={18} style={{ color: 'var(--accent)' }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>Library</span>

        <div style={{ flex: 1 }} />

        <Input
          prefix={<Search size={14} style={{ color: 'var(--text-muted)' }} />}
          placeholder="Search papers..."
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          style={{ width: 240 }}
          size="small"
        />

        <Segmented
          size="small"
          value={viewMode}
          onChange={setViewMode}
          options={viewOptions.map((o) => ({
            value: o.value,
            icon: o.icon,
          }))}
        />

        <Button
          type="primary"
          size="small"
          icon={<Plus size={14} />}
          onClick={() => setCollectionModalOpen(true)}
        >
          Collection
        </Button>

        <Button
          type="default"
          size="small"
          icon={<Upload size={14} />}
          onClick={() => setImportModalOpen(true)}
        >
          Import
        </Button>
      </div>

      {/* Main content: sidebar + list */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        <LibrarySidebar
          collections={collections}
          selectedId={selectedCollectionId}
          onSelect={selectCollection}
          onCreateCollection={() => setCollectionModalOpen(true)}
          onDeleteCollection={deleteCollection}
          loading={loading}
        />

        <LibraryListView
          items={items}
          viewMode={viewMode}
          selectedId={selectedItem?.id}
          onSelect={selectItem}
          onLoadMore={handleLoadMore}
          hasMore={items.length < pagination.total}
          loading={loading}
          onMoveToCollection={moveItemToCollection}
          collections={collections}
          onDeleteItem={deleteItem}
        />
      </div>

      <Drawer
        open={!!selectedItem}
        onClose={() => selectItem(null)}
        width={520}
        closable={false}
        mask
        maskClosable
        styles={{ body: { padding: 0 } }}
      >
        {selectedItem && (
          <LibraryItemDetail
            item={selectedItem}
            onClose={() => selectItem(null)}
            onDelete={() => selectedItem && deleteItem(selectedItem.id)}
            onUpdateItem={updateItemMetadata}
            onRefreshItem={selectItem}
            sendWSMessage={sendWSMessage}
          />
        )}
      </Drawer>

      <LibraryImportModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportPdf={importPdf}
        onImportDoi={importByDoi}
        onImportArxiv={importByArxiv}
        collections={collections}
      />

      <LibraryCollectionModal
        open={collectionModalOpen}
        onClose={() => setCollectionModalOpen(false)}
        onCreate={createCollection}
        collections={collections}
      />
    </div>
  );
};

export default LibraryTab;
