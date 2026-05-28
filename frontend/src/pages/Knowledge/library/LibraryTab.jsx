import React, { useState, useEffect, useCallback } from 'react';
import { Library, Search, Upload, Plus, Grid3X3, List, Table2, GitGraph, Sparkles, StickyNote, CheckSquare, Square, Trash2 } from 'lucide-react';
import { Input, Button, Segmented, Drawer, message, Progress } from 'antd';
import { useDistillTasks } from '@contexts/DistillTaskContext';
import TaskIndicator from '@components/TaskIndicator';
import TaskDetailModal from '@components/TaskIndicator/TaskDetailModal';
import useLibraryWS from './hooks/useLibraryWS';
import useLibrary from './hooks/useLibrary';
import LibrarySidebar from './LibrarySidebar';
import LibraryListView from './LibraryListView';
import LibraryItemDetail from './LibraryItemDetail';
import LibraryImportModal from './LibraryImportModal';
import LibraryCollectionModal from './LibraryCollectionModal';
import LibraryGraphTab from './LibraryGraphTab';

const DEFAULT_PAGE_SIZE = 20;

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
    pagination: itemPagination,
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
  } = useLibrary(libraryWS, sendWSMessage);

  const { registerSyncTasks, syncTasksFromBackend } = useDistillTasks();

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [collectionModalOpen, setCollectionModalOpen] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const [batchExtracting, setBatchExtracting] = useState(false);
  const [batchNoting, setBatchNoting] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [batchProgress, setBatchProgress] = useState(null); // { type, total, done, current, success, fail }

  // Distill task pagination state
  const [taskPagination, setTaskPagination] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });
  const [selectedTask, setSelectedTask] = useState(null);
  const [taskDetailModalVisible, setTaskDetailModalVisible] = useState(false);

  // Initial load
  useEffect(() => {
    loadCollections();
    loadItems(null, '', 0);
  }, []);

  // Load distill tasks from backend
  const loadDistillTasks = useCallback(async (offset = 0) => {
    try {
      const resp = await sendWSMessage('knowledge_distill_list', {
        limit: taskPagination.limit,
        offset,
      }, 10000);
      const tasks = resp.data?.tasks || [];
      const paginationData = resp.data?.pagination || {};
      syncTasksFromBackend(tasks);
      setTaskPagination({
        total: paginationData.total || 0,
        limit: paginationData.limit || DEFAULT_PAGE_SIZE,
        offset: paginationData.offset || 0,
      });
    } catch {
      // ignore
    }
  }, [sendWSMessage, syncTasksFromBackend, taskPagination.limit]);

  // Register sync function
  useEffect(() => {
    registerSyncTasks(loadDistillTasks);
  }, [registerSyncTasks, loadDistillTasks]);

  // Initial load of distill tasks
  useEffect(() => {
    loadDistillTasks(0);
  }, [loadDistillTasks]);

  // Listen for distill progress events
  useEffect(() => {
    const handler = (e) => {
      const { stage, message: msg } = e.detail;
      if (stage === 'completed') {
        message.success('Distillation complete!');
        loadDistillTasks();
      } else if (stage === 'failed') {
        message.error('Distillation failed: ' + msg);
        loadDistillTasks();
      }
    };
    window.addEventListener('knowledge-distill-progress', handler);
    return () => window.removeEventListener('knowledge-distill-progress', handler);
  }, [loadDistillTasks]);

  // Poll chunk parse status for items that are pending/processing
  useEffect(() => {
    const interval = setInterval(() => {
      const hasParsing = items.some(
        (i) => i.chunk_status && (i.chunk_status === 'pending' || i.chunk_status.startsWith('processing:'))
      );
      const selectedParsing =
        selectedItem?.chunk_status &&
        (selectedItem.chunk_status === 'pending' || selectedItem.chunk_status.startsWith('processing:'));
      if (hasParsing || selectedParsing) {
        loadItems(selectedCollectionId, searchQuery, 0);
        if (selectedItem) {
          selectItem(selectedItem.id);
        }
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [items, selectedItem, selectedCollectionId, searchQuery, loadItems, selectItem]);

  const handleViewTaskDetail = useCallback((task) => {
    setSelectedTask(task);
    setTaskDetailModalVisible(true);
  }, []);

  const handleTaskPageChange = useCallback((newOffset) => {
    const validOffset = Math.max(0, Math.min(newOffset, taskPagination.total - 1));
    loadDistillTasks(validOffset);
  }, [loadDistillTasks, taskPagination.total]);

  const handlePrevPage = useCallback(() => {
    handleTaskPageChange(taskPagination.offset - taskPagination.limit);
  }, [handleTaskPageChange, taskPagination.offset, taskPagination.limit]);

  const handleNextPage = useCallback(() => {
    handleTaskPageChange(taskPagination.offset + taskPagination.limit);
  }, [handleTaskPageChange, taskPagination.offset, taskPagination.limit]);

  const currentPage = Math.floor(taskPagination.offset / taskPagination.limit) + 1;
  const totalPages = Math.ceil(taskPagination.total / taskPagination.limit) || 1;
  const hasPrevPage = taskPagination.offset > 0;
  const hasNextPage = taskPagination.offset + taskPagination.limit < taskPagination.total;

  const viewOptions = [
    { value: 'card', icon: <Grid3X3 size={14} /> },
    { value: 'list', icon: <List size={14} /> },
    { value: 'table', icon: <Table2 size={14} /> },
  ];

  // ── Selection ──
  const toggleSelect = useCallback((id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(items.map((i) => i.id)));
  }, [items]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const selectedCount = selectedIds.size;
  const selectedItems = items.filter((i) => selectedIds.has(i.id));

  // ── Batch operations on selected ──
  const handleBatchExtract = async () => {
    if (selectedCount === 0) {
      message.info('Please select at least one paper');
      return;
    }
    setBatchExtracting(true);
    setBatchProgress({ type: 'extract', total: selectedCount, done: 0, current: '', success: 0, fail: 0 });
    let success = 0;
    let fail = 0;
    for (let i = 0; i < selectedItems.length; i++) {
      const item = selectedItems[i];
      setBatchProgress((prev) => ({ ...prev, done: i, current: item.title || `Item ${item.id}` }));
      try {
        await aiExtractAndSave(item.id);
        success++;
        setBatchProgress((prev) => ({ ...prev, success }));
      } catch (e) {
        console.error(`Batch extract failed for ${item.id}:`, e);
        fail++;
        setBatchProgress((prev) => ({ ...prev, fail }));
      }
    }
    setBatchExtracting(false);
    setBatchProgress(null);
    setSelectedIds(new Set());
    if (fail === 0) {
      message.success(`Batch extract complete: ${success} items`);
    } else {
      message.warning(`${success} extracted, ${fail} failed`);
    }
  };

  const handleBatchNotes = async () => {
    if (selectedCount === 0) {
      message.info('Please select at least one paper');
      return;
    }
    setBatchNoting(true);
    setBatchProgress({ type: 'note', total: selectedCount, done: 0, current: '', success: 0, fail: 0 });
    let success = 0;
    let fail = 0;
    for (let i = 0; i < selectedItems.length; i++) {
      const item = selectedItems[i];
      setBatchProgress((prev) => ({ ...prev, done: i, current: item.title || `Item ${item.id}` }));
      try {
        await generateNote(item);
        success++;
        setBatchProgress((prev) => ({ ...prev, success }));
      } catch (e) {
        console.error(`Batch note failed for ${item.id}:`, e);
        fail++;
        setBatchProgress((prev) => ({ ...prev, fail }));
      }
    }
    setBatchNoting(false);
    setBatchProgress(null);
    setSelectedIds(new Set());
    if (fail === 0) {
      message.success(`Batch notes complete: ${success} items`);
    } else {
      message.warning(`${success} done, ${fail} failed`);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedCount === 0) {
      message.info('Please select at least one paper');
      return;
    }
    try {
      await deleteItems(Array.from(selectedIds));
      message.success(`Deleted ${selectedCount} items`);
      setSelectedIds(new Set());
    } catch (e) {
      message.error('Batch delete failed: ' + (e.message || 'Unknown'));
    }
  };

  const handleExtractItem = async (itemId) => {
    try {
      await aiExtractAndSave(itemId);
      message.success('Metadata extracted & saved');
    } catch (e) {
      message.error('Extract failed: ' + (e.message || 'Unknown'));
    }
  };

  const handleGenerateNoteItem = async (item) => {
    try {
      await generateNote(item);
      message.success('AI note generation started');
    } catch (e) {
      message.error('Note generation failed: ' + (e.message || 'Unknown'));
    }
  };

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

        {!showGraph && (
          <Segmented
            size="small"
            value={viewMode}
            onChange={setViewMode}
            options={viewOptions.map((o) => ({
              value: o.value,
              icon: o.icon,
            }))}
          />
        )}

        <Button
          size="small"
          type={showGraph ? 'primary' : 'default'}
          icon={<GitGraph size={14} />}
          onClick={() => setShowGraph((v) => !v)}
        >
          Graph
        </Button>

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

        <TaskIndicator
          onViewTaskDetail={handleViewTaskDetail}
          pagination={taskPagination}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
          currentPage={currentPage}
          totalPages={totalPages}
          hasPrevPage={hasPrevPage}
          hasNextPage={hasNextPage}
          onRefresh={() => loadDistillTasks(taskPagination.offset)}
        />
      </div>

      {/* Selection toolbar — only shown when items are selected */}
      {selectedCount > 0 && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            padding: '8px 16px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--accent-soft)',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>
              {selectedCount} selected
            </span>
            <Button
              size="small"
              icon={<CheckSquare size={14} />}
              onClick={selectAll}
            >
              Select All
            </Button>
            <Button
              size="small"
              icon={<Square size={14} />}
              onClick={clearSelection}
            >
              Clear
            </Button>
            <div style={{ flex: 1 }} />
            <Button
              size="small"
              icon={<Sparkles size={14} />}
              loading={batchExtracting}
              onClick={handleBatchExtract}
              type="primary"
              disabled={batchNoting}
            >
              Extract Selected
            </Button>
            <Button
              size="small"
              icon={<StickyNote size={14} />}
              loading={batchNoting}
              onClick={handleBatchNotes}
              type="primary"
              disabled={batchExtracting}
            >
              Notes Selected
            </Button>
            <Button
              size="small"
              icon={<Trash2 size={14} />}
              onClick={handleBatchDelete}
              danger
              disabled={batchExtracting || batchNoting}
            >
              Delete Selected
            </Button>
          </div>
          {batchProgress && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Progress
                percent={Math.round((batchProgress.done / batchProgress.total) * 100)}
                size="small"
                style={{ flex: 1 }}
                status="active"
              />
              <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                {batchProgress.type === 'extract' ? 'Extracting' : 'Generating'} {batchProgress.done + 1} / {batchProgress.total}
                {batchProgress.current && ` — ${batchProgress.current}`}
              </span>
              <span style={{ fontSize: 12, color: 'var(--accent-green)', whiteSpace: 'nowrap' }}>
                ✓ {batchProgress.success}
              </span>
              {batchProgress.fail > 0 && (
                <span style={{ fontSize: 12, color: 'var(--accent-red)', whiteSpace: 'nowrap' }}>
                  ✗ {batchProgress.fail}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Main content: sidebar + list/graph */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        <LibrarySidebar
          collections={collections}
          selectedId={selectedCollectionId}
          onSelect={(id) => {
            selectCollection(id);
          }}
          onOpenGraph={(id) => {
            selectCollection(id);
            setShowGraph(true);
          }}
          onCreateCollection={() => setCollectionModalOpen(true)}
          onDeleteCollection={deleteCollection}
          loading={loading}
        />

        {showGraph ? (
          <LibraryGraphTab
            sendWSMessage={sendWSMessage}
            collectionId={selectedCollectionId}
            onNodeNavigate={(itemId) => {
              selectItem(Number(itemId));
            }}
          />
        ) : (
          <LibraryListView
            items={items}
            viewMode={viewMode}
            selectedId={selectedItem?.id}
            onSelect={selectItem}
            onLoadMore={handleLoadMore}
            hasMore={items.length < itemPagination.total}
            loading={loading}
            onMoveToCollection={moveItemToCollection}
            collections={collections}
            onDeleteItem={deleteItem}
            onExtractItem={handleExtractItem}
            onGenerateNoteItem={handleGenerateNoteItem}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
          />
        )}
      </div>

      <Drawer
        open={!!selectedItem}
        onClose={() => selectItem(null)}
        size={520}
        closable={false}
        mask={{ closable: true }}
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

      <TaskDetailModal
        task={selectedTask}
        visible={taskDetailModalVisible}
        onClose={() => setTaskDetailModalVisible(false)}
        sendWSMessage={sendWSMessage}
      />
    </div>
  );
};

export default LibraryTab;
