import React, { useState } from 'react';
import { FileText, Calendar, Users, Tag, MoreVertical, Trash2, FolderInput, StickyNote, Sparkles, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { Dropdown, Empty, Spin, Table, Popconfirm, Checkbox } from 'antd';

const getApiPort = () => {
  if (window.electronAPI?.getApiPort) {
    // Will be resolved async, but for initial render use location.port
    return window.location.port || '18791';
  }
  return window.location.port || '18791';
};

const getThumbnailUrl = (thumbnailPath) => {
  if (!thumbnailPath) return null;
  const port = getApiPort();
  return `http://127.0.0.1:${port}/workspace/${thumbnailPath}`;
};

const ThumbnailImage = ({ thumbnailPath, fallbackSize = 32, style = {} }) => {
  const [error, setError] = useState(false);

  if (!thumbnailPath || error) {
    return <FileText size={fallbackSize} opacity={0.3} />;
  }

  return (
    <img
      src={getThumbnailUrl(thumbnailPath)}
      alt=""
      style={{ width: '100%', height: '100%', objectFit: 'cover', ...style }}
      onError={() => setError(true)}
    />
  );
};

const ParseStatusBadge = ({ status }) => {
  if (!status) return null;
  if (status === 'completed') return null; // completed is the default, don't clutter
  if (status === 'pending') {
    return (
      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--bg)', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
        <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> Processing
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: '#fff1f0', color: '#ff4d4f', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
        <XCircle size={10} /> Failed
      </span>
    );
  }
  if (status.startsWith('processing:')) {
    const m = status.match(/processing:(\d+)\/(\d+)/);
    const current = m ? parseInt(m[1], 10) : 0;
    const total = m ? parseInt(m[2], 10) : 1;
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    return (
      <span style={{ fontSize: 10, display: 'inline-flex', flexDirection: 'column', gap: 2, minWidth: 60 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: 'var(--accent)' }}>
          <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> Parsing {current}/{total}
        </span>
        <span style={{ height: 3, borderRadius: 2, background: 'var(--bg)', overflow: 'hidden', width: '100%' }}>
          <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s ease' }} />
        </span>
      </span>
    );
  }
  return null;
};

const CardView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem, onExtractItem, onGenerateNoteItem, selectedIds, onToggleSelect }) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
      gap: 12,
      padding: 12,
      overflowY: 'auto',
    }}
  >
    {items.map((item) => {
      const isSelected = selectedIds.has(item.id);
      return (
        <div
          key={item.id}
          style={{
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: selectedId === item.id ? 'var(--accent-soft)' : 'var(--bg-elevated)',
            padding: 12,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            position: 'relative',
          }}
        >
          {/* Checkbox top-left */}
          <div
            style={{ position: 'absolute', top: 8, left: 8, zIndex: 2 }}
            onClick={(e) => e.stopPropagation()}
          >
            <Checkbox
              checked={isSelected}
              onChange={() => onToggleSelect(item.id)}
            />
          </div>

          {/* Content area — clicking here opens the detail drawer */}
          <div onClick={() => onSelect(item.id)} style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, position: 'relative' }}>
            {/* Thumbnail */}
            <div
              style={{
                height: 100,
                borderRadius: 4,
                background: 'var(--bg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-muted)',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <ThumbnailImage thumbnailPath={item.thumbnail_path} fallbackSize={32} />
              {item.has_notes && (
                <span
                  style={{
                    position: 'absolute',
                    top: 6,
                    right: 6,
                    fontSize: 10,
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: 'var(--accent)',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 3,
                    fontWeight: 600,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                >
                  <StickyNote size={10} />
                  Note
                </span>
              )}
            </div>

            <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {item.title || 'Untitled'}
            </div>
            <ParseStatusBadge status={item.chunk_status} />

            <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Users size={12} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.authors?.slice(0, 2).join(', ') || 'Unknown'}
                {item.authors?.length > 2 ? ' et al.' : ''}
              </span>
            </div>

            <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Calendar size={12} />
                {item.year || 'N/A'}
              </span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.venue}
              </span>
            </div>

            {item.tags?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                {item.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 10,
                      background: 'var(--accent-soft)',
                      color: 'var(--accent)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
                {item.tags.length > 3 && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>+{item.tags.length - 3}</span>
                )}
              </div>
            )}
          </div>

          {/* Action area — separate from content, no onSelect */}
          <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'flex-end' }}>
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'extract',
                    label: (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Sparkles size={14} /> Extract
                      </span>
                    ),
                    onClick: () => onExtractItem(item.id),
                  },
                  {
                    key: 'note',
                    label: (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <StickyNote size={14} /> AI Note
                      </span>
                    ),
                    onClick: () => onGenerateNoteItem(item),
                  },
                  { type: 'divider' },
                  {
                    key: 'move',
                    label: 'Move to Collection',
                    icon: <FolderInput size={14} />,
                    children: collections
                      .filter((c) => c.id !== 1 && c.id !== 2)
                      .map((c) => ({
                        key: `move-${c.id}`,
                        label: c.name,
                        onClick: () => onMoveToCollection(item.id, c.id),
                      })),
                  },
                  { type: 'divider' },
                  {
                    key: 'delete',
                    label: (
                      <Popconfirm
                        title="Delete this paper?"
                        onConfirm={() => onDeleteItem(item.id)}
                        okText="Delete"
                        cancelText="Cancel"
                        okType="danger"
                      >
                        <span style={{ color: '#ff4d4f', display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Trash2 size={14} /> Delete
                        </span>
                      </Popconfirm>
                    ),
                  },
                ],
              }}
              trigger={['click']}
            >
              <span
                style={{ display: 'flex', padding: 4, borderRadius: 4, cursor: 'pointer' }}
              >
                <MoreVertical size={14} />
              </span>
            </Dropdown>
          </div>
        </div>
      );
    })}
  </div>
);

const ListView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem, onExtractItem, onGenerateNoteItem, selectedIds, onToggleSelect }) => (
  <div style={{ overflowY: 'auto', padding: '8px 0' }}>
    {items.map((item) => {
      const isSelected = selectedIds.has(item.id);
      return (
        <div
          key={item.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '10px 16px',
            cursor: 'pointer',
            background: selectedId === item.id ? 'var(--accent-soft)' : 'transparent',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {/* Checkbox */}
          <div onClick={(e) => e.stopPropagation()}>
            <Checkbox checked={isSelected} onChange={() => onToggleSelect(item.id)} />
          </div>

          {/* Content area — clicking here opens the detail drawer */}
          <div onClick={() => onSelect(item.id)} style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 48, borderRadius: 4, background: 'var(--bg)', color: 'var(--text-muted)', flexShrink: 0, overflow: 'hidden' }}>
              <ThumbnailImage thumbnailPath={item.thumbnail_path} fallbackSize={20} />
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 8 }}>
                {item.title || 'Untitled'}
                {item.has_notes && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 8px',
                      borderRadius: 10,
                      background: 'var(--accent)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    <StickyNote size={10} />
                    Note
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span>{item.authors?.slice(0, 2).join(', ') || 'Unknown'}{item.authors?.length > 2 ? ' et al.' : ''}</span>
                <span>·</span>
                <span>{item.year || 'N/A'}</span>
                <span>·</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.venue}</span>
                <ParseStatusBadge status={item.chunk_status} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 4, flexShrink: 0, alignItems: 'center' }}>
              {item.tags?.slice(0, 2).map((tag) => (
                <span key={tag} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--accent-soft)', color: 'var(--accent)' }}>
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Action area — separate from content */}
          <Dropdown
            menu={{
              items: [
                {
                  key: 'extract',
                  label: (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Sparkles size={14} /> Extract
                    </span>
                  ),
                  onClick: () => onExtractItem(item.id),
                },
                {
                  key: 'note',
                  label: (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <StickyNote size={14} /> AI Note
                    </span>
                  ),
                  onClick: () => onGenerateNoteItem(item),
                },
                { type: 'divider' },
                {
                  key: 'move',
                  label: 'Move to Collection',
                  icon: <FolderInput size={14} />,
                  children: collections.filter((c) => c.id !== 1 && c.id !== 2).map((c) => ({
                    key: `move-${c.id}`,
                    label: c.name,
                    onClick: () => onMoveToCollection(item.id, c.id),
                  })),
                },
                { type: 'divider' },
                {
                  key: 'delete',
                  label: (
                    <Popconfirm
                      title="Delete this paper?"
                      onConfirm={() => onDeleteItem(item.id)}
                      okText="Delete"
                      cancelText="Cancel"
                      okType="danger"
                    >
                      <span style={{ color: '#ff4d4f', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Trash2 size={14} /> Delete
                      </span>
                    </Popconfirm>
                  ),
                },
              ],
            }}
            trigger={['click']}
          >
            <span style={{ display: 'flex', padding: 4, cursor: 'pointer', flexShrink: 0 }}>
              <MoreVertical size={14} />
            </span>
          </Dropdown>
        </div>
      );
    })}
  </div>
);

const TableView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem, onExtractItem, onGenerateNoteItem, selectedIds, onToggleSelect }) => {
  const columns = [
    {
      title: '',
      key: 'select',
      width: 50,
      render: (_, record) => (
        <Checkbox
          checked={selectedIds.has(record.id)}
          onChange={() => onToggleSelect(record.id)}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (text, record) => (
        <span style={{ fontWeight: 600, cursor: 'pointer' }} onClick={() => onSelect(record.id)}>
          {text || 'Untitled'}
        </span>
      ),
    },
    {
      title: 'Authors',
      dataIndex: 'authors',
      key: 'authors',
      render: (authors) => authors?.slice(0, 2).join(', ') + (authors?.length > 2 ? ' et al.' : '') || 'Unknown',
    },
    {
      title: 'Year',
      dataIndex: 'year',
      key: 'year',
      width: 80,
      sorter: (a, b) => (a.year || 0) - (b.year || 0),
    },
    {
      title: 'Venue',
      dataIndex: 'venue',
      key: 'venue',
    },
    {
      title: '',
      key: 'note',
      width: 60,
      render: (_, record) =>
        record.has_notes ? (
          <span
            style={{
              fontSize: 10,
              padding: '2px 8px',
              borderRadius: 10,
              background: 'var(--accent)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              fontWeight: 600,
            }}
          >
            <StickyNote size={10} />
            Note
          </span>
        ) : null,
    },
    {
      title: 'Parse',
      dataIndex: 'chunk_status',
      key: 'chunk_status',
      width: 100,
      render: (status) => <ParseStatusBadge status={status} />,
    },
    {
      title: 'Tags',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {tags?.slice(0, 3).map((tag) => (
            <span key={tag} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--accent-soft)', color: 'var(--accent)' }}>
              {tag}
            </span>
          ))}
        </div>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 50,
      render: (_, record) => (
        <Dropdown
          menu={{
            items: [
              {
                key: 'extract',
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Sparkles size={14} /> Extract
                  </span>
                ),
                onClick: () => onExtractItem(record.id),
              },
              {
                key: 'note',
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <StickyNote size={14} /> AI Note
                  </span>
                ),
                onClick: () => onGenerateNoteItem(record),
              },
              { type: 'divider' },
              {
                key: 'move',
                label: 'Move to Collection',
                icon: <FolderInput size={14} />,
                children: collections.filter((c) => c.id !== 1 && c.id !== 2).map((c) => ({
                  key: `move-${c.id}`,
                  label: c.name,
                  onClick: () => onMoveToCollection(record.id, c.id),
                })),
              },
              { type: 'divider' },
              {
                key: 'delete',
                label: (
                  <Popconfirm
                    title="Delete this paper?"
                    onConfirm={() => onDeleteItem(record.id)}
                    okText="Delete"
                    cancelText="Cancel"
                    okType="danger"
                  >
                    <span style={{ color: '#ff4d4f', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Trash2 size={14} /> Delete
                    </span>
                  </Popconfirm>
                ),
              },
            ],
          }}
          trigger={['click']}
        >
          <span style={{ display: 'flex', padding: 4, cursor: 'pointer' }}>
            <MoreVertical size={14} />
          </span>
        </Dropdown>
      ),
    },
  ];

  return (
    <div style={{ padding: 12, overflowY: 'auto' }}>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        size="small"
        pagination={false}
        rowClassName={(record) => (record.id === selectedId ? 'library-row-selected' : '')}
      />
    </div>
  );
};

const LibraryListView = ({
  items,
  viewMode,
  selectedId,
  onSelect,
  onLoadMore,
  hasMore,
  loading,
  onMoveToCollection,
  collections,
  onDeleteItem,
  onExtractItem,
  onGenerateNoteItem,
  selectedIds,
  onToggleSelect,
}) => {
  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    if (scrollHeight - scrollTop - clientHeight < 100 && hasMore && !loading) {
      onLoadMore();
    }
  };

  if (!loading && items.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="No papers in this collection" />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, overflow: 'auto' }} onScroll={handleScroll}>
        {viewMode === 'card' && (
          <CardView
            items={items}
            selectedId={selectedId}
            onSelect={onSelect}
            onMoveToCollection={onMoveToCollection}
            collections={collections}
            onDeleteItem={onDeleteItem}
            onExtractItem={onExtractItem}
            onGenerateNoteItem={onGenerateNoteItem}
            selectedIds={selectedIds}
            onToggleSelect={onToggleSelect}
          />
        )}
        {viewMode === 'list' && (
          <ListView
            items={items}
            selectedId={selectedId}
            onSelect={onSelect}
            onMoveToCollection={onMoveToCollection}
            collections={collections}
            onDeleteItem={onDeleteItem}
            onExtractItem={onExtractItem}
            onGenerateNoteItem={onGenerateNoteItem}
            selectedIds={selectedIds}
            onToggleSelect={onToggleSelect}
          />
        )}
        {viewMode === 'table' && (
          <TableView
            items={items}
            selectedId={selectedId}
            onSelect={onSelect}
            onMoveToCollection={onMoveToCollection}
            collections={collections}
            onDeleteItem={onDeleteItem}
            onExtractItem={onExtractItem}
            onGenerateNoteItem={onGenerateNoteItem}
            selectedIds={selectedIds}
            onToggleSelect={onToggleSelect}
          />
        )}
        {loading && (
          <div style={{ padding: 16, textAlign: 'center' }}>
            <Spin size="small" />
          </div>
        )}
      </div>
    </div>
  );
};

export default LibraryListView;
