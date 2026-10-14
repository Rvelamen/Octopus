import test from 'node:test';
import assert from 'node:assert/strict';
import {projectRoomScene,seatPosition} from './sceneProjection.mjs';

test('scene receives only public identity, validated messages and authorized generation',()=>{
  const room={room_id:'room',epoch:2,scene_capacity:8,scene_layout_version:1,members:[{id:'a',seat_index:0,active:true,available:true,speaking_mode:'auto',identity:{name:'甲',book_title:'书甲'},runtime_policy:{secret:'private'}},{id:'b',seat_index:1,active:false,available:true,speaking_mode:'auto',identity:{name:'甲',book_title:'书乙'}}]};
  const messages=[{id:'old',seq:1,speaker_type:'character',speaker_member_id:'a',content:'历史'},{id:'new',seq:2,speaker_type:'character',speaker_member_id:'a',content:'已校验',refs:[{quote:'private evidence'}]}];
  const projection=projectRoomScene(room,{status:'running',generation:{member_id:'b',phase:'generate',candidate:'unpublished secret'}},messages,['new']);
  assert.equal(projection.generation,null);assert.deepEqual(projection.messages,[{id:'new',seq:2,member_id:'a',content:'已校验'}]);
  assert.equal(JSON.stringify(projection).includes('private'),false);assert.equal(projection.members[1].present,false);
  assert.equal(projectRoomScene(room,null,messages,[]).messages.length,0);
});
test('1/4/8/16/32 occupants retain individual fixed seats and chair clearance',()=>{
  for(const capacity of [8,16,32]){
    const positions=Array.from({length:capacity},(_,index)=>seatPosition(index,capacity));
    assert.equal(new Set(positions.map(point=>`${point.x}:${point.z}`)).size,capacity);
    for(let index=0;index<capacity;index+=1){const next=positions[(index+1)%capacity];assert.ok(Math.hypot(positions[index].x-next.x,positions[index].z-next.z)>.79);}
  }
});

test('a published slot takes precedence over an older progress snapshot',()=>{
  const room={room_id:'r',epoch:1,scene_capacity:8,scene_layout_version:1,members:[{id:'a',seat_index:0,active:true,available:true,speaking_mode:'auto',identity:{name:'甲',book_title:'书'}}]};
  const round={round_id:'turn',status:'running',generation:{member_id:'a',slot_id:'slot',phase:'validate'}};
  const message={id:'published',seq:2,round_id:'turn',slot_id:'slot',speaker_type:'character',speaker_member_id:'a',content:'已发布'};
  const scene=projectRoomScene(room,round,[message],['published']);
  assert.equal(scene.generation,null);
  assert.equal(scene.messages[0].id,'published');
  assert.equal(projectRoomScene(room,round,[{...message,round_id:'old'}],[]).generation.member_id,'a');
});
