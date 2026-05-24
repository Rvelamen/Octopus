import React from 'react';
import { FileText, Calendar, Users, Tag, MoreVertical, Trash2, FolderInput } from 'lucide-react';
import { Dropdown, Empty, Spin, Table, Popconfirm } from 'antd';

const CardView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem }) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
      gap: 12,
      padding: 12,
      overflowY: 'auto',
    }}
  >
    {items.map((item) => (
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
        }}
      >
        {/* Content area — clicking here opens the detail drawer */}
        <div onClick={() => onSelect(item.id)} style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
          {/* Thumbnail placeholder */}
          <div
            style={{
              height: 100,
              borderRadius: 4,
              background: 'var(--bg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <FileText size={32} opacity={0.3} />
          </div>

          <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
            {item.title || 'Untitled'}
          </div>

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
    ))}
  </div>
);

const ListView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem }) => (
  <div style={{ overflowY: 'auto', padding: '8px 0' }}>
    {items.map((item) => (
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
        {/* Content area — clicking here opens the detail drawer */}
        <div onClick={() => onSelect(item.id)} style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 48, borderRadius: 4, background: 'var(--bg)', color: 'var(--text-muted)', flexShrink: 0 }}>
            <FileText size={20} opacity={0.4} />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {item.title || 'Untitled'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8, alignItems: 'center' }}>
              <span>{item.authors?.slice(0, 2).join(', ') || 'Unknown'}{item.authors?.length > 2 ? ' et al.' : ''}</span>
              <span>·</span>
              <span>{item.year || 'N/A'}</span>
              <span>·</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.venue}</span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
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
    ))}
  </div>
);

const TableView = ({ items, selectedId, onSelect, onMoveToCollection, collections, onDeleteItem }) => {
  const columns = [
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
