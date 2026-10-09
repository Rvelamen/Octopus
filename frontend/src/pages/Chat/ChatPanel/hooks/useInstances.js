import { useState, useCallback, useEffect, useRef } from 'react';

const PAGE_SIZE = 20;
const INFLIGHT_TTL_MS = 5000;

export function useInstances(sendWSMessage, connectionStatus, options = {}) {
  const { subscribe, onActiveChanged, onInstanceDeleted } = options;

  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState(null);
  const [instancesPage, setInstancesPage] = useState(0);
  const [instancesHasMore, setInstancesHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const [archivedInstances, setArchivedInstances] = useState([]);
  const [archivedExpanded, setArchivedExpanded] = useState(false);
  const [isLoadingArchived, setIsLoadingArchived] = useState(false);

  const isComponentMounted = useRef(true);

  // Self-echo dedupe: when we send an archive/unarchive, the bus will also
  // echo back a chat_instance_changed event for the same id. Track the ids
  // we just touched so we can ignore the echo and not stomp on the
  // optimistic write we already did.
  const inflightArchive = useRef(new Set());
  const inflightUnarchive = useRef(new Set());

  const fetchInstances = useCallback(async (showError = true, isInitialLoad = false, append = false) => {
    if (!sendWSMessage) return;

    if (isInitialLoad) {
      setInitialLoading(true);
      setInstancesPage(0);
      setInstancesHasMore(true);
    } else if (!append) {
      setLoading(true);
    } else {
      setIsLoadingMore(true);
    }

    if (showError) setError(null);
    try {
      const offset = append ? (instancesPage * PAGE_SIZE) : 0;
      const response = await sendWSMessage('session_get_instances', {
        channel: 'desktop',
        limit: PAGE_SIZE,
        offset: offset
      }, 5000);

      const newInstances = response.data?.instances || [];
      const hasMore = response.data?.has_more ?? false;

      if (append) {
        setInstances(prev => [...prev, ...newInstances]);
      } else {
        setInstances(newInstances);
      }

      setInstancesHasMore(hasMore);
      setInstancesPage(append ? instancesPage + 1 : 1);
    } catch (err) {
      console.error('Failed to fetch instances:', err);
      if (showError) {
        setError(err.message);
      }
    } finally {
      if (isInitialLoad) {
        setInitialLoading(false);
      } else if (!append) {
        setLoading(false);
      } else {
        setIsLoadingMore(false);
      }
    }
  }, [sendWSMessage, instancesPage]);

  const fetchArchivedInstances = useCallback(async (showError = true) => {
    if (!sendWSMessage) return;
    setIsLoadingArchived(true);
    try {
      const response = await sendWSMessage('session_get_instances', {
        channel: 'desktop',
        limit: 100,
        offset: 0,
        archived_only: true
      }, 5000);
      setArchivedInstances(response.data?.instances || []);
    } catch (err) {
      console.error('Failed to fetch archived instances:', err);
      if (showError) {
        setError(err.message);
      }
    } finally {
      setIsLoadingArchived(false);
    }
  }, [sendWSMessage]);

  const loadMoreInstances = useCallback(() => {
    if (!instancesHasMore || isLoadingMore || loading) return;
    fetchInstances(false, false, true);
  }, [instancesHasMore, isLoadingMore, loading, fetchInstances]);

  const deleteInstance = useCallback(async (instanceId) => {
    // Hard delete confirmation — kept as-is for now (pre-existing tech debt
    // noted in the plan; will switch to a proper modal later).
    if (!confirm('Are you sure you want to delete this session instance? This will also delete all messages in it.')) {
      return false;
    }

    try {
      await sendWSMessage('session_delete_instance', { instance_id: instanceId }, 5000);
      fetchInstances();
      return true;
    } catch (err) {
      console.error('Failed to delete instance:', err);
      alert('Failed to delete instance: ' + err.message);
      return false;
    }
  }, [sendWSMessage, fetchInstances]);

  const archiveInstance = useCallback(async (instance, t) => {
    if (!sendWSMessage || !instance) return false;
    const label = instance.instance_name || 'this chat';
    const confirmMsg = t ? t('chat.archiveConfirm', { name: label }) : `Archive "${label}"?`;
    if (!window.confirm(confirmMsg)) {
      return false;
    }

    const instanceId = instance.id;
    // Mark as in-flight so the bus echo is ignored.
    inflightArchive.current.add(instanceId);
    setTimeout(() => inflightArchive.current.delete(instanceId), INFLIGHT_TTL_MS);

    try {
      // Optimistic UI: move the row from active to archived immediately.
      // The bus event will not stomp on this because of the inflight guard.
      const archivedCopy = { ...instance, archived_at: new Date().toISOString() };
      setInstances(prev => prev.filter(i => i.id !== instanceId));
      setArchivedInstances(prev => [archivedCopy, ...prev.filter(i => i.id !== instanceId)]);

      await sendWSMessage('session_archive_instance', { instance_id: instanceId }, 5000);
      // Don't re-fetch — the bus event is the source of truth for
      // cross-window sync. Re-fetching here would race with it.
      return true;
    } catch (err) {
      console.error('Failed to archive instance:', err);
      // Roll back the optimistic move on failure.
      inflightArchive.current.delete(instanceId);
      setInstances(prev => [instance, ...prev.filter(i => i.id !== instanceId)]);
      setArchivedInstances(prev => prev.filter(i => i.id !== instanceId));
      alert((t ? t('chat.archiveFailed') : 'Failed to archive chat') + ': ' + err.message);
      return false;
    }
  }, [sendWSMessage]);

  const unarchiveInstance = useCallback(async (instance, t) => {
    if (!sendWSMessage || !instance) return false;
    const instanceId = instance.id;

    // Mark as in-flight so the bus echo is ignored.
    inflightUnarchive.current.add(instanceId);
    setTimeout(() => inflightUnarchive.current.delete(instanceId), INFLIGHT_TTL_MS);

    try {
      // Optimistic UI: move from archived to active. Don't auto-select —
      // the user has to click the card to open it.
      const restored = { ...instance, archived_at: null };
      setArchivedInstances(prev => prev.filter(i => i.id !== instanceId));
      setInstances(prev => [restored, ...prev.filter(i => i.id !== instanceId)]);

      await sendWSMessage('session_unarchive_instance', { instance_id: instanceId }, 5000);
      return true;
    } catch (err) {
      console.error('Failed to unarchive instance:', err);
      inflightUnarchive.current.delete(instanceId);
      setArchivedInstances(prev => [instance, ...prev.filter(i => i.id !== instanceId)]);
      setInstances(prev => prev.filter(i => i.id !== instanceId));
      alert((t ? t('chat.unarchiveFailed') : 'Failed to restore chat') + ': ' + err.message);
      return false;
    }
  }, [sendWSMessage]);

  // Subscribe to chat_instance_changed for cross-window reconciliation.
  const onActiveChangedRef = useRef(onActiveChanged);
  const onInstanceDeletedRef = useRef(onInstanceDeleted);
  useEffect(() => {
    onActiveChangedRef.current = onActiveChanged;
    onInstanceDeletedRef.current = onInstanceDeleted;
  }, [onActiveChanged, onInstanceDeleted]);

  useEffect(() => {
    if (typeof subscribe !== 'function') return;

    const handler = (data) => {
      const action = data?.action;
      const instanceId = data?.instance_id;
      if (!action || !instanceId) return;

      if (action === 'archived') {
        if (inflightArchive.current.has(instanceId)) {
          inflightArchive.current.delete(instanceId);
          return;
        }
        // Move from active to archived, picking up the row by id.
        let archivedCopy = null;
        setInstances(prev => {
          const target = prev.find(i => i.id === instanceId);
          if (!target) return prev;
          archivedCopy = {
            ...target,
            archived_at: data.archived_at || new Date().toISOString(),
          };
          return prev.filter(i => i.id !== instanceId);
        });
        if (archivedCopy) {
          setArchivedInstances(prev => [archivedCopy, ...prev.filter(i => i.id !== instanceId)]);
        }
      } else if (action === 'unarchived') {
        if (inflightUnarchive.current.has(instanceId)) {
          inflightUnarchive.current.delete(instanceId);
          return;
        }
        let restored = null;
        setArchivedInstances(prev => {
          const target = prev.find(i => i.id === instanceId);
          if (!target) return prev;
          restored = { ...target, archived_at: null };
          return prev.filter(i => i.id !== instanceId);
        });
        if (restored) {
          setInstances(prev => [restored, ...prev.filter(i => i.id !== instanceId)]);
        }
      } else if (action === 'deleted') {
        setInstances(prev => prev.filter(i => i.id !== instanceId));
        setArchivedInstances(prev => prev.filter(i => i.id !== instanceId));
        // Cross-window delete: if our currently-selected card is the one
        // that just got deleted, clear the right pane.
        onInstanceDeletedRef.current?.(instanceId);
      } else if (action === 'active_set') {
        // Two cases:
        //  1. The user archived the currently-selected card; the server
        //     auto-picked a replacement. Tell the caller to switch.
        //  2. The user clicked a different card; the caller already
        //     updated selectedInstance, so do nothing.
        if (inflightArchive.current.size > 0) {
          inflightArchive.current.clear();
          onActiveChangedRef.current?.(instanceId);
        }
      }
    };

    const unsub = subscribe('chat_instance_changed', handler);
    return () => {
      if (typeof unsub === 'function') unsub();
    };
  }, [subscribe]);

  useEffect(() => {
    isComponentMounted.current = true;
    return () => {
      isComponentMounted.current = false;
    };
  }, []);

  // Only fetch when WebSocket is actually connected
  useEffect(() => {
    if (sendWSMessage && connectionStatus === 'connected' && isComponentMounted.current) {
      fetchInstances(false, true);
      fetchArchivedInstances(false);
    }
  }, [sendWSMessage, connectionStatus, fetchInstances, fetchArchivedInstances]);

  // Retry if still empty after connected and loaded
  useEffect(() => {
    if (instances.length === 0 && !initialLoading && !error && sendWSMessage && connectionStatus === 'connected') {
      const retryTimer = setInterval(() => {
        if (isComponentMounted.current) {
          fetchInstances(false, true);
        }
      }, 2000);

      const stopTimer = setTimeout(() => {
        clearInterval(retryTimer);
      }, 10000);

      return () => {
        clearInterval(retryTimer);
        clearTimeout(stopTimer);
      };
    }
  }, [instances.length, initialLoading, error, sendWSMessage, connectionStatus, fetchInstances]);

  return {
    instances,
    loading,
    initialLoading,
    error,
    instancesHasMore,
    isLoadingMore,
    fetchInstances,
    loadMoreInstances,
    deleteInstance,
    archivedInstances,
    archivedExpanded,
    setArchivedExpanded,
    isLoadingArchived,
    fetchArchivedInstances,
    archiveInstance,
    unarchiveInstance,
  };
}
