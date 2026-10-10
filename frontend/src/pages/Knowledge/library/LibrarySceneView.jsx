import React, { useEffect, useCallback } from 'react';
import LibraryScene from './scene/LibraryScene';
import useLibraryWS from './hooks/useLibraryWS';
import useLibrary from './hooks/useLibrary';

/**
 * 林间图书馆 — 以图书馆"区域"为单位的 3D 书架场景入口。
 * 共享与 LibraryTab 同一套 collections 数据,确保两边看到同一个区域布局。
 */
export default function LibrarySceneView({ sendWSMessage }) {
  const libraryWS = useLibraryWS(sendWSMessage);
  // Scene 只需要 collections 与刷新;其余 useLibrary 状态(分页/选中/搜索/批量选择)在这里都不需要
  const { collections, loadCollections } = useLibrary(libraryWS, sendWSMessage);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  return (
    <LibraryScene
      collections={collections}
      libraryWS={libraryWS}
      sendWSMessage={sendWSMessage}
      onCollectionsChanged={loadCollections}
    />
  );
}
