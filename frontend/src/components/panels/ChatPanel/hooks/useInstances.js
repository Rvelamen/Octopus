import { useState, useCallback, useEffect, useRef } from 'react';

const PAGE_SIZE = 20;

export function useInstances(sendWSMessage) {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState(null);
  const [instancesPage, setInstancesPage] = useState(0);
  const [instancesHasMore, setInstancesHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  
  const isComponentMounted = useRef(true);

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

  const loadMoreInstances = useCallback(() => {
    if (!instancesHasMore || isLoadingMore || loading) return;
    fetchInstances(false, false, true);
  }, [instancesHasMore, isLoadingMore, loading, fetchInstances]);

  const deleteInstance = useCallback(async (instanceId) => {
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

  useEffect(() => {
    isComponentMounted.current = true;
    fetchInstances(false, true);
    return () => {
      isComponentMounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (sendWSMessage && isComponentMounted.current && initialLoading) {
      fetchInstances(false, false);
    }
  }, [sendWSMessage]);

  useEffect(() => {
    if (instances.length === 0 && !initialLoading && !error && sendWSMessage) {
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
  }, [instances.length, initialLoading, error, sendWSMessage, fetchInstances]);

  return {
    instances,
    loading,
    initialLoading,
    error,
    instancesHasMore,
    isLoadingMore,
    fetchInstances,
    loadMoreInstances,
    deleteInstance
  };
}
