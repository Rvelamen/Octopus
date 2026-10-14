import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Empty, Modal, Select, Spin } from 'antd';
import { useTranslation } from 'react-i18next';
import { useBookWorldFeatures } from '@contexts/WebSocketContext';
import BookRoomManager from '../Knowledge/library/BookRoomManager';
import { BookConversation } from '../Knowledge/library/BookSingleChatModal';
import BookRoomScene from './BookRoomScene';
import useBookRoom from './useBookRoom';
import BookRoomDiscussion from '../Knowledge/library/BookRoomDiscussion';
import './BookRooms.css';

function ActiveRoom({snapshot,sendWSMessage,onAdd,connectionStatus,connectionIdentity}) {
  const features = useBookWorldFeatures();
  const readOnly = !features.single_chat || ((snapshot.kind === 'group' || snapshot.members.length > 1) && !features.group_chat);
  const {t}=useTranslation();
  const detail={workspace_id:snapshot.workspace_id,room_id:snapshot.room_id,epoch:snapshot.epoch,public:{name:snapshot.title}};
  const chat=useBookRoom(detail,sendWSMessage,connectionStatus,connectionIdentity);
  const [selected,setSelected]=useState(null),[card,setCard]=useState(null),[mention,setMention]=useState(null),[width,setWidth]=useState(400);
  const [profile,setProfile]=useState(null),[profileError,setProfileError]=useState('');
  const member=chat.room?.members.find(member=>member.id===card);
  const active=['queued','running','paused','interrupted'].includes(chat.round?.status);
  const showMessage=id=>{
    const message=chat.messages.find(message=>message.id===id);
    if(message){chat.showHistory(message);chat.pin(id);setSelected(message.speaker_member_id);document.getElementById(`book-room-message-${id}`)?.scrollIntoView({block:'nearest',behavior:chat.reduced?'instant':'smooth'});}
  };
  return <>
    <BookRoomDiscussion chat={chat}/>
    <div className="book-room-body" style={{'--conversation-width':`${width}px`}}>
      <BookRoomScene chat={chat} selected={selected} onSelect={id=>{setSelected(id);setCard(id);setProfile(null);setProfileError('');}} onMessage={showMessage}/>
      <input type="range" className="book-room-divider" min={360} max={560} step={20} value={width} onChange={event=>setWidth(Number(event.target.value))} aria-orientation="vertical" aria-label={t('bookScene.resize')} tabIndex={0} aria-valuemin={360} aria-valuemax={560} aria-valuenow={width} onKeyDown={event=>{if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();setWidth(value=>Math.min(560,Math.max(360,value+(event.key==='ArrowLeft'?20:-20))));}}} onPointerDown={event=>event.currentTarget.setPointerCapture(event.pointerId)} onPointerMove={event=>{if(event.currentTarget.hasPointerCapture(event.pointerId)){const right=event.currentTarget.parentElement.getBoundingClientRect().right;setWidth(Math.max(360,Math.min(560,right-event.clientX)));}}}/>
      <BookConversation embedded group detail={detail} chat={chat} onAddMembers={onAdd} mention={mention} displayText={chat.displayText} onShowMessage={message=>showMessage(message.id)}/>
    </div>
    <Modal open={Boolean(member)} title={member&&`${member.identity.name} · ${member.identity.book_title}`} onCancel={()=>setCard(null)} footer={<Button onClick={()=>setCard(null)}>{t('bookWorld.closeArchive')}</Button>}>
      {member&&<><p>{t('bookScene.seat',{index:member.seat_index+1})} · {member.id.slice(0,6)}</p><p>{member.available?t(`bookRoom.speaking.${member.speaking_mode}`):t('bookRoom.deletedSource')}</p>
        <Button disabled={chat.busy||!member.available} onClick={()=>{setProfileError('');chat.profile(member.id).then(setProfile).catch(failure=>setProfileError({member_id:member.id,epoch:chat.room.epoch,message:failure.message}));}}>{t('bookScene.publicProfile')}</Button>
        {profileError?.member_id===member.id&&profileError.epoch===chat.room.epoch&&<Alert type="error" title={profileError.message}/>}
        {member.available&&profile?.member_id===member.id&&profile.epoch===chat.room.epoch&&<div><p>{profile.public.name} · {profile.identity.book_title}</p><p>{t(`bookWorld.characterStatus.${profile.agent_status}`,{defaultValue:profile.agent_status})}</p><small>{t('bookScene.sourceIdentity',{version:profile.source_version_id.slice(0,8)})}</small></div>}
        <Button disabled={readOnly||chat.busy||active||!member.active||!member.available||member.speaking_mode==='muted'} onClick={()=>{setMention({member_id:member.id,request:crypto.randomUUID()});setCard(null);}}>{t('bookRoom.mention')}</Button>
        <Select aria-label={t('bookRoom.memberMode',{name:member.identity.name,id:member.id.slice(0,6)})} disabled={chat.busy||!member.active||!member.available} value={member.speaking_mode} onChange={speaking_mode=>chat.act('set_member',null,{member_id:member.id,speaking_mode})} options={['auto','mention_only','muted'].map(value=>({value,label:t(`bookRoom.speaking.${value}`),disabled:readOnly&&value!=='muted'}))}/>
        <Button danger disabled={chat.busy||!member.active} onClick={()=>chat.act('set_member',null,{member_id:member.id,active:false})}>{t('bookRoom.remove')}</Button>
        {!member.active&&<Button disabled={readOnly||chat.busy||active||!member.available} onClick={()=>chat.act('set_member',null,{member_id:member.id,active:true})}>{t('bookRoom.rejoin')}</Button>}
      </>}
    </Modal>
  </>;
}

export default function BookRooms({sendWSMessage,connectionStatus,connectionIdentity}) {
  const bookFeatures = useBookWorldFeatures();
  const {t}=useTranslation(),navigate=useNavigate(),location=useLocation(),{roomId}=useParams();
  const [snapshot,setSnapshot]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[manager,setManager]=useState(()=>{
    const query=new URLSearchParams(location.search);
    if(location.state?.create)return {create:true,characters:location.state.characters||[]};
    if(query.get('create')==='1')return {create:true,characters:query.get('item_id')?[{item_id:Number(query.get('item_id')),build_id:query.get('build_id'),character_id:query.get('character_id')}]:[]};
    return null;
  });
  const generation=useRef(0);
  const load=useCallback(async()=>{
    const revision=++generation.current;setLoading(true);setError('');setSnapshot(null);
    if(!roomId){setLoading(false);return;}
    try{
      const list=await sendWSMessage('book_room',{action:'list_rooms',limit:1});
      if(list.type==='error')throw Error(list.data.error);
      const response=await sendWSMessage('book_room',{action:'open_room',workspace_id:list.data.workspace_id,room_id:roomId});
      if(response.type==='error')throw Error(response.data.error);
      if(revision===generation.current)setSnapshot(response.data);
    }catch(failure){if(revision===generation.current)setError(failure.message);}
    finally{if(revision===generation.current)setLoading(false);}
  },[roomId,sendWSMessage]);
  useEffect(()=>{
    if (connectionStatus && connectionStatus !== 'connected') return undefined;
    Promise.resolve().then(load);
    return()=>{generation.current+=1;};
  },[load,connectionStatus,bookFeatures.single_chat]);
  const readOnly = !bookFeatures.single_chat || ((snapshot?.kind === 'group' || snapshot?.members.length > 1) && !bookFeatures.group_chat);
  return <main className="book-rooms-page">
    <header><div><h1>{snapshot?.title||t('nav.bookRooms')}</h1></div><nav><Button onClick={()=>setManager({})}>{t('bookScene.switchRoom')}</Button><Button disabled={!bookFeatures.group_chat} onClick={()=>setManager({create:true})}>{t('bookRoom.createGroup')}</Button><Button onClick={()=>load()} disabled={loading}>{t('bookWorld.refreshBuild')}</Button><Button onClick={()=>navigate('/config')}>{t('nav.config')}</Button></nav></header>
    {error&&<Alert type="error" title={error}/>}
    {readOnly&&<Alert type="info" title={t('bookRelease.disabled')}/>}
    {loading?<Spin/>:snapshot?<ActiveRoom key={`${snapshot.workspace_id}:${snapshot.room_id}`} snapshot={snapshot} sendWSMessage={sendWSMessage} connectionStatus={connectionStatus} connectionIdentity={connectionIdentity} onAdd={room=>setManager({adding:room})}/>:<div className="book-room-empty"><Empty description={t('bookScene.empty')}/><Button type="primary" disabled={!bookFeatures.group_chat} onClick={()=>setManager({create:true})}>{t('bookRoom.createGroup')}</Button></div>}
    {manager&&<BookRoomManager sendWSMessage={sendWSMessage} onClose={()=>setManager(null)} initialCreate={manager.create} initialAdding={manager.adding} initialCharacters={manager.characters} onOpenRoom={room=>{setManager(null);navigate(`/book-rooms/${room.room_id}`);if(room.room_id===roomId)load();}}/>}
  </main>;
}
