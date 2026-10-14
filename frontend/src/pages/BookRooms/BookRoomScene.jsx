import { useRef, useState } from 'react';
import { Alert, Button, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import BookRoomSceneCanvas from './BookRoomSceneCanvas';

export default function BookRoomScene({chat,selected,onSelect,onMessage}) {
  const {t}=useTranslation();
  const renderer=useRef(null);
  const [flat,setFlat]=useState(false),[failed,setFailed]=useState(false);
  const scene=chat.scene;
  if(!scene)return null;
  const select=id=>{onSelect(id);renderer.current?.focus(id);};
  const label=member=>`${member.identity.name} · ${member.identity.book_title} · ${member.member_id.slice(0,6)}`;
  const overlay=positions=>{
    const placed=[];
    const namePlaced=[];
    const ordered=[...positions].sort((a,b)=>Number(b.id===scene.generation?.member_id)-Number(a.id===scene.generation?.member_id)||Number(b.id===selected)-Number(a.id===selected));
    return ordered.filter(point=>point.visible).map(point=>{
      const member=scene.members.find(member=>member.member_id===point.id);
      const bubble=chat.bubbles.find(bubble=>bubble.member_id===point.id);
      const phase=scene.generation?.member_id===point.id ? scene.generation.phase : null;
      const compact = namePlaced.some(other => Math.abs(other.x-point.x)<115 && Math.abs(other.y-point.y)<50);
      if (!compact) namePlaced.push(point);
      const overlap=(bubble||phase)&&placed.some(other=>Math.abs(other.x-point.x)<230&&Math.abs(other.y-point.y)<130);
      if((bubble||phase)&&!overlap)placed.push(point);
      return <div key={point.id} className={`book-seat-label ${selected===point.id?'selected':''}`} style={{left:point.x,top:point.y}}>
        {(bubble||phase)&&<button className="book-seat-bubble" data-message-id={!phase ? bubble?.id : undefined} data-message-seq={!phase ? bubble?.seq : undefined} onMouseEnter={()=>!phase&&bubble&&chat.pin(bubble.id)} onMouseLeave={()=>chat.pin(null)} onFocus={()=>!phase&&bubble&&chat.pin(bubble.id)} onBlur={()=>chat.pin(null)} onClick={()=>phase?select(point.id):onMessage(bubble.id)}>
          {phase?t(`bookRoom.phase.${phase}`):<>{bubble.historical&&<small>{t('bookScene.history')}</small>}<span>{overlap?'…':bubble.content.slice(0,120)}{!overlap&&bubble.content.length>120?'…':''}</span><small>{t('bookScene.fullMessage')}</small></>}
        </button>}
        <button className={`book-seat-name ${compact?'compact':''}`} aria-label={label(member)} onClick={()=>select(point.id)} title={label(member)}>{compact?member.seat_index+1:<>{member.identity.name}<small>{member.identity.book_title} · {member.member_id.slice(0,6)}</small>{(!member.present||member.speaking_mode!=='auto')&&<small>{!member.present?t(member.source_removed?'bookRoom.deletedSource':'bookScene.left'):t(`bookRoom.speaking.${member.speaking_mode}`)}</small>}</>}</button>
      </div>;
    });
  };
  return <section className="book-room-scene" aria-label={t('bookScene.scene')}>
    <div className="book-scene-tools"><Button onClick={()=>renderer.current?.reset()} disabled={flat}>{t('bookScene.overview')}</Button><Button aria-label={t('bookScene.zoomIn')} onClick={()=>renderer.current?.zoom(.85)} disabled={flat}>＋</Button><Button aria-label={t('bookScene.zoomOut')} onClick={()=>renderer.current?.zoom(1.15)} disabled={flat}>－</Button><Button onClick={()=>setFlat(!flat)} disabled={failed}>{t(flat?'bookScene.threeD':'bookScene.twoD')}</Button>{chat.viewingHistory&&<Button onClick={chat.clearHistory}>{t('bookScene.closeHistory')}</Button>}</div>
    {failed&&<Alert type="warning" title={t('bookScene.fallback')} />}
    {flat?<div className="book-flat-seats">{Array.from({length:scene.capacity},(_,index)=>{
      const member=scene.members.find(member=>member.seat_index===index);
      return <button key={index} disabled={!member} className={member?.present?'occupied':'empty'} onClick={()=>member&&select(member.member_id)}><small>{t('bookScene.seat',{index:index+1})}</small>{member?label(member):t('bookScene.emptySeat')}{member&&!member.present&&<Tag>{t(member.source_removed?'bookRoom.deletedSource':'bookScene.left')}</Tag>}</button>;
    })}</div>:<BookRoomSceneCanvas ref={renderer} projection={scene} onSelect={select} onError={()=>{setFlat(true);setFailed(true);}}>{overlay}</BookRoomSceneCanvas>}
    <details className="book-scene-member-list"><summary>{t('bookRoom.members')} ({scene.members.length})</summary><div>{scene.members.map(member=><Button key={member.member_id} onClick={()=>select(member.member_id)}>{label(member)} · {t('bookScene.seat',{index:member.seat_index+1})}</Button>)}</div></details>
  </section>;
}
