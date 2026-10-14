// Explicit public projection: scene code never receives canon, refs or reader evidence.
export function projectRoomScene(room, round, messages, liveIds) {
  if (!room) return null;
  const members = room.members.map(member => ({
    member_id: member.id, seat_index: member.seat_index,
    identity: { name: member.identity.name, book_title: member.identity.book_title },
    present: Boolean(member.active && member.available),
    speaking_mode: member.speaking_mode,
    removed: !member.active, source_removed: !member.available,
  }));
  const valid = new Set(members.filter(member => member.present).map(member => member.member_id));
  const generation = round?.status === 'running' && !messages.some(message => message.slot_id && message.slot_id === round.generation?.slot_id && message.round_id === round.round_id) && members.some(member => member.member_id === round.generation?.member_id && member.present && member.speaking_mode !== 'muted')
    ? { member_id: round.generation.member_id, phase: round.generation.phase } : null;
  const live = new Set(liveIds);
  return {
    room_id: room.room_id, epoch: room.epoch,
    capacity: room.scene_capacity, layout_version: room.scene_layout_version,
    members, generation,
    messages: messages.filter(message => message.speaker_type === 'character' && live.has(message.id) && valid.has(message.speaker_member_id)).map(message => ({
      id: message.id, seq: message.seq, member_id: message.speaker_member_id, content: message.content,
    })),
  };
}

export function seatPosition(index, capacity) {
  const radius = Math.max(2.6, capacity * 0.8 / (2 * Math.PI));
  const angle = -Math.PI / 2 + 2 * Math.PI * index / capacity;
  return { x: Math.cos(angle) * radius, z: Math.sin(angle) * radius, radius, angle };
}
