import { useState } from 'react';
import { Alert, Button, Input, Modal, Select, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

export default function BookRoomDiscussion({chat}) {
  const {t}=useTranslation();
  const [draft,setDraft]=useState(null);
  const [summaryScope,setSummaryScope]=useState(null);
  const discussion=chat.room?.discussion;
  if(!discussion)return null;
  const active=['queued','running','paused','interrupted'].includes(chat.round?.status);
  const count=value=>Array.from(value||'').length;
  const scope=`${chat.room.room_id}:${chat.room.epoch}`;
  const working=['queued','running'].includes(chat.summaryJob?.status);
  const remaining=chat.memory ? chat.messages.filter(message=>message.seq>chat.memory.through_seq).length : chat.messages.length;
  const invalid=draft&&(draft.mode==='topic'&&(!draft.topic.trim()||count(draft.topic)>200||count(draft.goal)>1000));
  const save=async()=>{
    if(await chat.act('set_discussion',null,{expected_discussion_revision:draft.revision,discussion_mode:draft.mode,topic:draft.topic,goal:draft.goal}))setDraft(null);
  };
  return <section className="book-discussion" aria-label={t('bookDiscussion.title')}>
    <Tag>{t(discussion.mode==='topic'?'bookDiscussion.topicMode':'bookDiscussion.free')}</Tag>
    {discussion.mode==='topic'&&<span><strong>{discussion.topic}</strong>{discussion.goal&&<small> · {discussion.goal}</small>}</span>}
    <Button size="small" disabled={chat.busy||active||chat.room.status!=='active'} onClick={()=>setDraft({...discussion,topic:discussion.topic||'',goal:discussion.goal||''})}>{t('bookDiscussion.edit')}</Button>
    <Button size="small" disabled={chat.busy||working||!chat.modelKey||!chat.messages.length||chat.room.status!=='active'} onClick={async()=>{if(await chat.act('summarize_room'))setSummaryScope(scope);}}>{t('bookDiscussion.summarize')}</Button>
    {working&&<Button size="small" disabled={chat.busy} onClick={()=>chat.act('cancel_summary',null,{summary_job_id:chat.summaryJob.id})}>{t('bookDiscussion.cancelSummary')}</Button>}
    {chat.summaryJob&&<Tag>{t(`bookDiscussion.summaryStatus.${chat.summaryJob.status}`)}</Tag>}
    {chat.summaryJob?.error_code&&<Alert type="warning" title={t(`bookDiscussion.summaryError.${chat.summaryJob.error_code}`,{defaultValue:t('bookDiscussion.summaryError.summary_failed')})}/>}
    {active&&<small>{t('bookDiscussion.busy')}</small>}
    <Modal open={draft!==null} title={t('bookDiscussion.title')} onCancel={()=>setDraft(null)} onOk={save} okButtonProps={{disabled:invalid||active||chat.busy}} confirmLoading={chat.busy}>
      {chat.error&&<Alert type="error" title={chat.error}/>}
      {draft&&<><Select aria-label={t('bookDiscussion.mode')} value={draft.mode} onChange={mode=>setDraft({...draft,mode})} options={['free','topic'].map(value=>({value,label:t(value==='topic'?'bookDiscussion.topicMode':'bookDiscussion.free')}))}/>
        {draft.mode==='topic'&&<><p>{t('bookDiscussion.topic')}</p><Input aria-label={t('bookDiscussion.topic')} value={draft.topic} onChange={event=>setDraft({...draft,topic:event.target.value})}/><small>{count(draft.topic)}/200</small><p>{t('bookDiscussion.goal')}</p><Input.TextArea aria-label={t('bookDiscussion.goal')} value={draft.goal} onChange={event=>setDraft({...draft,goal:event.target.value})}/><small>{count(draft.goal)}/1000</small></>}
        <p>{t('bookDiscussion.hint')}</p>
      </>}
    </Modal>
    <Modal open={summaryScope===scope} title={t('bookDiscussion.summaryTitle')} onCancel={()=>setSummaryScope(null)} footer={null}>
      <p>{t('bookDiscussion.summaryHint')}</p>
      {chat.memory&&<small>{t('bookDiscussion.through',{seq:chat.memory.through_seq})}</small>}
      {remaining>0&&<Alert type="warning" title={t('bookDiscussion.partial',{count:remaining})}/>}
      {chat.memory?.items.map((item,index)=><article key={index}><strong>{item.speaker_type==='user'?t('bookRoom.you'):chat.room.members.find(member=>member.id===item.speaker_member_id)?.identity.name}</strong><Tag>{t(`bookRoom.origin.${item.origin}`)}</Tag><p>{item.text}</p>{item.source_message_ids.map(id=>{const source=chat.messages.find(message=>message.id===id);return source&&<blockquote key={id}>{source.content}</blockquote>;})}</article>)}
      {!working&&!chat.memory?.items.length&&<p>{t('bookDiscussion.noSummary')}</p>}
    </Modal>
  </section>;
}
