import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Empty, Input, Modal, Select, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import BookSingleChatModal from './BookSingleChatModal';

const characterKey = (entry) => `${entry.item_id}:${entry.build_id}:${entry.character_id}`;

export default function BookRoomManager({ sendWSMessage, onClose }) {
  const { t } = useTranslation();
  const [rooms, setRooms] = useState([]);
  const [roomCursor, setRoomCursor] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [catalogCursor, setCatalogCursor] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [opened, setOpened] = useState(null);
  const [adding, setAdding] = useState(null);
  const [choosing, setChoosing] = useState(false);
  const [selected, setSelected] = useState([]);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  const listRevision = useRef(0);
  const pendingCreation = useRef(null);
  const workspaceRef = useRef(null);

  const request = useCallback(async (action, data = {}) => {
    const response = await sendWSMessage('book_room', { action, ...data }, 120000);
    if (response.type === 'error') throw new Error(response.data.error);
    return response.data;
  }, [sendWSMessage]);

  const load = useCallback(async () => {
    const current = generation.current;
    const sequence = ++listRevision.current;
    try {
      const [list, characters] = await Promise.all([request('list_rooms', { limit: 25 }), request('list_room_characters', { limit: 100 })]);
      if (current !== generation.current || sequence !== listRevision.current) return;
      if (list.workspace_id !== characters.workspace_id) throw new Error(t('bookRoom.workspaceChanged'));
      if (workspaceRef.current && workspaceRef.current !== list.workspace_id) {
        setOpened(null); setAdding(null); setChoosing(false); setSelected([]);
        pendingCreation.current = null;
      }
      workspaceRef.current = list.workspace_id;
      setWorkspace(list.workspace_id); setRooms(list.rooms); setRoomCursor(list.next_offset);
      setCatalog(characters.characters); setCatalogCursor(characters.next_offset);
    } catch (failure) { if (current === generation.current && sequence === listRevision.current) throw failure; }
  }, [request, t]);

  useEffect(() => {
    const current = ++generation.current;
    Promise.resolve().then(load).catch((failure) => { if (current === generation.current) setError(failure.message); });
    return () => { generation.current += 1; };
  }, [load]);

  const loadMore = async (kind) => {
    const current = generation.current;
    const sequence = listRevision.current;
    setBusy(true); setError('');
    try {
      const result = await request(kind === 'rooms' ? 'list_rooms' : 'list_room_characters', { workspace_id: workspace, offset: kind === 'rooms' ? roomCursor : catalogCursor, limit: kind === 'rooms' ? 25 : 100 });
      if (current !== generation.current || sequence !== listRevision.current) return;
      if (kind === 'rooms') { setRooms((previous) => [...previous, ...result.rooms]); setRoomCursor(result.next_offset); }
      else { setCatalog((previous) => [...previous, ...result.characters]); setCatalogCursor(result.next_offset); }
    } catch (failure) { if (current === generation.current && sequence === listRevision.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  const choose = (room = null) => { setAdding(room); setChoosing(true); setSelected([]); setError(''); };
  const save = async () => {
    const current = generation.current;
    listRevision.current += 1;
    const entries = selected.map((key) => catalog.find((entry) => characterKey(entry) === key));
    if (entries.some((entry) => !entry)) { setError(t('bookRoom.selectionChanged')); return; }
    const characters = entries.map(({ item_id, build_id, character_id }) => ({ item_id, build_id, character_id }));
    setBusy(true); setError('');
    try {
      let result;
      if (adding) result = await request('add_members', { workspace_id: workspace, room_id: adding.room_id, expected_epoch: adding.epoch, characters });
      else {
        const signature = JSON.stringify({ characters, title });
        if (pendingCreation.current?.signature !== signature) pendingCreation.current = { signature, id: crypto.randomUUID() };
        result = await request('create_group_room', { workspace_id: workspace, client_room_id: pendingCreation.current.id, characters, ...(title.trim() ? { title: title.trim() } : {}) });
      }
      if (current !== generation.current) return;
      setChoosing(false);
      if (adding) setRevision((value) => value + 1);
      else { setOpened(result); pendingCreation.current = null; setTitle(''); }
      await load();
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  return <>
    <Modal open title={t('bookRoom.manager')} onCancel={onClose} footer={<Button onClick={onClose}>{t('bookWorld.closeArchive')}</Button>} width={900}>
      {error && <Alert type="error" showIcon title={error} />}
      <Space><Button type="primary" disabled={!workspace || busy} onClick={() => choose()}>{t('bookRoom.createGroup')}</Button><Button disabled={busy} onClick={() => load().catch((failure) => setError(failure.message))}>{t('bookWorld.refreshBuild')}</Button></Space>
      {!rooms.length && <Empty description={t('bookRoom.noRooms')} />}
      {rooms.map((room) => <article key={room.room_id} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <strong>{room.title}</strong> <Tag>{room.members.filter((member) => member.active).length}</Tag>
        <p>{room.sources.map((source) => `${source.identity.book_title} · ${source.status !== 'active' ? t('bookRoom.deletedSource') : source.is_latest_version ? t('bookRoom.latestVersion') : t('bookRoom.fixedOldVersion')} · ${source.build_id.slice(0, 8)}`).join(' / ')}</p>
        <Button onClick={() => setOpened(room)}>{t('bookRoom.openRoom')}</Button>
      </article>)}
      {roomCursor !== null && <Button disabled={busy} onClick={() => loadMore('rooms')}>{t('bookRoom.moreRooms')}</Button>}
    </Modal>
    {opened && <BookSingleChatModal group detail={{ workspace_id: opened.workspace_id, room_id: opened.room_id, epoch: opened.epoch, public: { name: opened.title } }} sendWSMessage={sendWSMessage} onClose={() => { setOpened(null); load().catch((failure) => setError(failure.message)); }} onAddMembers={choose} refreshRevision={revision} />}
    <Modal open={choosing} title={t(adding ? 'bookRoom.addMembers' : 'bookRoom.createGroup')} onCancel={() => setChoosing(false)} onOk={save} confirmLoading={busy} okButtonProps={{ disabled: !selected.length || !workspace }} okText={t(adding ? 'bookRoom.addMembers' : 'bookRoom.createGroup')} cancelText={t('bookWorld.closeArchive')}>
      <p>{t('bookRoom.selectCharactersHint')}</p>
      {error && <Alert type="error" title={error} />}
      {!adding && <Input aria-label={t('bookRoom.roomName')} placeholder={t('bookRoom.roomName')} value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} style={{ marginBottom: 8 }} />}
      <Select aria-label={t('bookRoom.chooseCharacters')} mode="multiple" value={selected} onChange={setSelected} optionFilterProp="label" style={{ width: '100%' }} options={catalog.map((entry) => ({ value: characterKey(entry), disabled: !!adding?.members.some((member) => member.character_id === entry.character_id), label: `${entry.name} · ${entry.book_title} · ${entry.build_id.slice(0, 8)}${entry.agent_status === 'sparse' ? ` · ${t('bookRoom.sparse')}` : ''}` }))} />
      {!catalog.length && <Alert type="info" title={t('bookRoom.noCharacters')} style={{ marginTop: 8 }} />}
      {catalogCursor !== null && <Button disabled={busy} onClick={() => loadMore('characters')}>{t('bookRoom.moreCharacters')}</Button>}
    </Modal>
  </>;
}
