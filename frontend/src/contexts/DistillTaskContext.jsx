import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
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

  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

