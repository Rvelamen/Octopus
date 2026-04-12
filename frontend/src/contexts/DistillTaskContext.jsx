import React, { createContext, useContext, useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { message } from 'antd';

const DistillTaskContext = createContext(null);

export const useDistillTasks = () => {
  const context = useContext(DistillTaskContext);
  if (!context) {
    throw new Error('useDistillTasks must be used within DistillTaskProvider');
  }
  return context;
};

export function DistillTaskProvider({ children }) {
  const [tasks, setTasks] = useState([]);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const tasksRef = useRef(tasks);
  const syncTasksRef = useRef(null);

  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

  // 使用 useMemo 计算活跃任务数量，确保及时更新
  const activeTaskCount = useMemo(() => {
    return tasks.filter((task) => task.status === 'running' || task.status === 'queued').length;
  }, [tasks]);

  const addTask = useCallback((task) => {
    const newTask = {
      id: task.id || `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      sourceFile: task.sourceFile,
      template: task.template,
      prompt: task.prompt,
      status: 'queued',
      progress: 0,
      message: 'Queued...',
      result: null,
      createdAt: Date.now(),
      completedAt: null,
    };
    setTasks((prev) => [newTask, ...prev]);
    return newTask.id;
  }, []);

  const updateTask = useCallback((taskId, updates) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === taskId
          ? { ...task, ...updates }
          : task
      )
    );
  }, []);

  const removeTask = useCallback((taskId) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
  }, []);

  const removeCompletedTasks = useCallback(() => {
    setTasks((prev) => prev.filter((task) => task.status !== 'completed' && task.status !== 'failed'));
  }, []);

  const clearAllTasks = useCallback(() => {
    setTasks([]);
  }, []);

  // 从后端批量同步任务列表
  // 将时间字符串或时间戳转换为毫秒时间戳
  const parseTime = (timeValue) => {
    if (!timeValue) return null;
    if (typeof timeValue === 'number') return timeValue;
    // 解析 ISO 格式时间字符串
    const date = new Date(timeValue);
    return isNaN(date.getTime()) ? null : date.getTime();
  };

  const syncTasksFromBackend = useCallback((backendTasks) => {
    setTasks((prevTasks) => {
      // 创建一个 Map 存储现有任务
      const existingTasksMap = new Map(prevTasks.map(t => [t.id, t]));

      // 处理后端返回的任务
      const mergedTasks = backendTasks.map((backendTask) => {
        const existingTask = existingTasksMap.get(backendTask.id);

        // 解析后端返回的时间
        const backendCompletedAt = parseTime(backendTask.completed_at);

        if (existingTask) {
          // 如果任务已存在，合并更新（保留前端的本地状态如 createdAt）
          return {
            ...existingTask,
            status: backendTask.status || existingTask.status,
            progress: backendTask.progress !== undefined ? backendTask.progress : existingTask.progress,
            message: backendTask.message || existingTask.message,
            completedAt: backendCompletedAt || existingTask.completedAt,
            result: backendTask.result || existingTask.result,
          };
        } else {
          // 如果是新任务，创建新的任务对象
          return {
            id: backendTask.id,
            sourceFile: backendTask.source_path,
            template: backendTask.template || 'custom',
            prompt: backendTask.prompt || '',
            status: backendTask.status || 'queued',
            progress: backendTask.progress || 0,
            message: backendTask.message || 'Queued...',
            result: backendTask.result || null,
            createdAt: parseTime(backendTask.created_at) || Date.now(),
            completedAt: backendCompletedAt,
          };
        }
      });

      return mergedTasks;
    });
  }, []);

  // 使用 useMemo 计算已完成任务数量
  const completedTaskCount = useMemo(() => {
    return tasks.filter((task) => task.status === 'completed' || task.status === 'failed').length;
  }, [tasks]);

  // 1分钟 = 60000毫秒
  const ONE_MINUTE = 60 * 1000;

  // 使用 useMemo 计算显示范围内的任务数量（活跃任务 + 1分钟内完成的任务）
  const displayTaskCount = useMemo(() => {
    const now = Date.now();
    return tasks.filter((task) => {
      // 活跃任务始终显示
      if (task.status === 'running' || task.status === 'queued') {
        return true;
      }
      // 完成的任务只在1分钟内显示
      if ((task.status === 'completed' || task.status === 'failed') && task.completedAt) {
        return now - task.completedAt < ONE_MINUTE;
      }
      return false;
    }).length;
  }, [tasks]);

  // 注册同步函数（由 KnowledgePanel 提供）
  const registerSyncTasks = useCallback((syncFn) => {
    syncTasksRef.current = syncFn;
  }, []);

  // 主动同步后端任务
  const syncWithBackend = useCallback(async () => {
    if (syncTasksRef.current) {
      await syncTasksRef.current();
    }
  }, []);

  const handleProgressEvent = useCallback((e) => {
    const { request_id, job_id, stage, message: msg, progress, output_path, markdown, error } = e.detail;

    // 后端使用 request_id 作为任务标识
    const taskId = job_id || request_id;
    if (!taskId) return;

    const existingTask = tasksRef.current.find((t) => t.id === taskId);

    if (!existingTask) {
      return;
    }

    const updates = {
      status: stage,
      progress: progress || 0,
      message: msg || '',
    };

    if (stage === 'completed') {
      updates.completedAt = Date.now();
      updates.result = { output_path, markdown };
      message.success(`Distillation completed: ${existingTask.sourceFile}`);
    } else if (stage === 'failed') {
      updates.completedAt = Date.now();
      updates.result = { error };
      message.error(`Distillation failed: ${existingTask.sourceFile}`);
    }

    updateTask(taskId, updates);
  }, [updateTask]);

  useEffect(() => {
    window.addEventListener('knowledge-distill-progress', handleProgressEvent);
    return () => window.removeEventListener('knowledge-distill-progress', handleProgressEvent);
  }, [handleProgressEvent]);

  // 定期主动同步（每10秒）
  useEffect(() => {
    const timer = setInterval(() => {
      syncWithBackend();
    }, 10000);
    return () => clearInterval(timer);
  }, [syncWithBackend]);

  const value = {
    tasks,
    isMenuOpen,
    setIsMenuOpen,
    addTask,
    updateTask,
    removeTask,
    removeCompletedTasks,
    clearAllTasks,
    activeTaskCount,
    completedTaskCount,
    displayTaskCount,
    registerSyncTasks,
    syncWithBackend,
    syncTasksFromBackend,
  };

  return (
    <DistillTaskContext.Provider value={value}>
      {children}
    </DistillTaskContext.Provider>
  );
}

export default DistillTaskContext;
