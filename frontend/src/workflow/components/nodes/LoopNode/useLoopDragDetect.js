import { useState, useEffect } from 'react';

const COLLISION_PADDING = 50;
const LOOP_HEADER_OFFSET = 110;
const LOOP_BODY_MARGIN_LEFT = 12;
const CHILD_NODE_PADDING_TOP = 8;

const checkCollision = (loopNode, dragNode) => {
  if (!loopNode || !dragNode) return false;

  const loopW = loopNode.measured?.width ?? loopNode.width ?? 400;
  const loopH = loopNode.measured?.height ?? loopNode.height ?? 280;
  const nodeW = dragNode.measured?.width ?? dragNode.width ?? 150;
  const nodeH = dragNode.measured?.height ?? dragNode.height ?? 44;

  const nodeCenterX = (dragNode.position?.x || 0) + nodeW / 2;
  const nodeCenterY = (dragNode.position?.y || 0) + nodeH / 2;

  const bodyX = loopNode.position.x + LOOP_BODY_MARGIN_LEFT;
  const bodyY = loopNode.position.y + LOOP_HEADER_OFFSET + 30;
  const bodyW = loopW - 24;
  const bodyH = loopH - LOOP_HEADER_OFFSET - 30 - 8;

  return (
    nodeCenterX >= bodyX - COLLISION_PADDING &&
    nodeCenterX <= bodyX + bodyW + COLLISION_PADDING &&
    nodeCenterY >= bodyY - COLLISION_PADDING &&
    nodeCenterY <= bodyY + bodyH + COLLISION_PADDING
  );
};

export const useLoopDragDetect = ({ loopNodeId, nodes, reactFlow }) => {
  const [isDragOver, setIsDragOver] = useState(false);

  useEffect(() => {
    const unsubscribe = reactFlow?.onNodeDrag?.((event, node) => {
      if (!node || node.id === loopNodeId || node.parentId) {
        setIsDragOver(false);
        return;
      }

      const loopNode = nodes.find((n) => n.id === loopNodeId);
      if (!loopNode || loopNode.type !== 'loop') {
        setIsDragOver(false);
        return;
      }

      setIsDragOver(checkCollision(loopNode, node));
    });

    const unsubscribeStop = reactFlow?.onNodeDragStop?.(() => {
      setIsDragOver(false);
    });

    return () => {
      if (unsubscribe) unsubscribe();
      if (unsubscribeStop) unsubscribeStop();
    };
  }, [loopNodeId, nodes, reactFlow]);

  return isDragOver;
};

export { checkCollision };
