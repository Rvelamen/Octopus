"""MCP Tool Registry module.

Manages MCP tool registration, dependency resolution, and lifecycle.
Provides tool enable/disable functionality and dependency conflict handling.
"""

import asyncio
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from loguru import logger

from backend.mcp.config import MCPToolConfig


class ToolState(Enum):
    """Tool state enumeration."""
    DISABLED = auto()
    ENABLED = auto()
    LOADING = auto()
    LOADED = auto()
    ERROR = auto()
    UNLOADING = auto()


@dataclass
class ToolInfo:
    """Tool information and state."""
    name: str
    config: MCPToolConfig
    state: ToolState = ToolState.DISABLED
    loaded_at: datetime | None = None
    last_used: datetime | None = None
    use_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    schema: dict[str, Any] = field(default_factory=dict)


class MCPToolRegistry:
    """Registry for MCP tools.
    
    Manages:
    - Tool registration and discovery
    - Tool enable/disable state
    - Dependency resolution
    - Tool lifecycle (load/unload)
    """
    
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._dependencies: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._state_callbacks: list[callable] = []
    
    def register_state_callback(self, callback: callable) -> None:
        """Register a callback for tool state changes."""
        self._state_callbacks.append(callback)
    
    def unregister_state_callback(self, callback: callable) -> None:
        """Unregister a state change callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def _notify_state_change(self, tool_name: str, old_state: ToolState, new_state: ToolState) -> None:
        """Notify all registered callbacks of state change."""
        for callback in self._state_callbacks:
            try:
                callback(tool_name, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def _set_tool_state(self, tool_name: str, new_state: ToolState, error_message: str | None = None) -> None:
        """Set tool state and notify listeners."""
        if tool_name not in self._tools:
            return
        
        tool = self._tools[tool_name]
        old_state = tool.state
        
        if old_state != new_state:
            tool.state = new_state
            if error_message:
                tool.error_message = error_message
            
            logger.info(f"Tool '{tool_name}' state: {old_state.name} -> {new_state.name}")
            self._notify_state_change(tool_name, old_state, new_state)
    
    async def register_tool(self, config: MCPToolConfig, metadata: dict[str, Any] | None = None) -> bool:
        """Register a new tool."""
        # 先检查是否已注册（不持有锁）
        if config.name in self._tools:
            logger.warning(f"Tool already registered: {config.name}")
            return False
        
        # 获取锁进行注册
        async with self._lock:
            # 双重检查
            if config.name in self._tools:
                logger.warning(f"Tool already registered: {config.name}")
                return False
            
            tool_info = ToolInfo(
                name=config.name,
                config=config,
                state=ToolState.DISABLED,
                metadata=metadata or {},
            )
            
            self._tools[config.name] = tool_info
            
            # Build dependency graph
            for dep in config.dependencies:
                if dep not in self._dependencies:
                    self._dependencies[dep] = set()
                self._dependencies[dep].add(config.name)
                
                if config.name not in self._dependents:
                    self._dependents[config.name] = set()
                self._dependents[config.name].add(dep)
            
            logger.info(f"Registered MCP tool: {config.name}")
        
        # 在锁外启用工具（避免死锁）
        if config.enabled:
            await self.enable_tool(config.name)
        
        return True
    
    async def unregister_tool(self, name: str, force: bool = False) -> bool:
        """Unregister a tool."""
        # 先检查状态和依赖（不持有锁）
        if name not in self._tools:
            return False
        
        tool = self._tools[name]
        
        # Check for dependents
        if name in self._dependents and self._dependents[name]:
            dependents = self._dependents[name]
            if not force:
                logger.error(f"Cannot unregister tool '{name}': has dependents {dependents}")
                return False
            
            # Disable dependents first (在锁外)
            for dependent in list(dependents):
                await self.disable_tool(dependent)
        
        # Disable and unload the tool (在锁外)
        if tool.state in (ToolState.ENABLED, ToolState.LOADED):
            await self.disable_tool(name)
        
        # 获取锁清理数据
        async with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools[name]
            
            # Clean up dependency graph
            for dep in tool.config.dependencies:
                if dep in self._dependencies and name in self._dependencies[dep]:
                    self._dependencies[dep].remove(name)
            
            if name in self._dependents:
                del self._dependents[name]
            
            del self._tools[name]
            logger.info(f"Unregistered MCP tool: {name}")
            return True
    
    async def enable_tool(self, name: str) -> bool:
        """Enable a tool."""
        # 使用锁保护整个操作
        async with self._lock:
            if name not in self._tools:
                logger.error(f"Cannot enable unknown tool: {name}")
                return False
            
            tool = self._tools[name]
            
            if tool.state in (ToolState.ENABLED, ToolState.LOADED, ToolState.LOADING):
                return True
            
            # Check dependencies (简单检查，不递归启用)
            for dep in tool.config.dependencies:
                if dep not in self._tools:
                    logger.error(f"Cannot enable tool '{name}': missing dependency '{dep}'")
                    self._set_tool_state(name, ToolState.ERROR, f"Missing dependency: {dep}")
                    return False
                
                dep_tool = self._tools[dep]
                if dep_tool.state not in (ToolState.ENABLED, ToolState.LOADED):
                    # 依赖未启用，记录错误但不递归
                    logger.error(f"Cannot enable tool '{name}': dependency '{dep}' is not enabled")
                    self._set_tool_state(name, ToolState.ERROR, f"Dependency not enabled: {dep}")
                    return False
            
            self._set_tool_state(name, ToolState.ENABLED)
        
        # Load the tool (在锁外执行)
        return await self._load_tool(name)
    
    async def disable_tool(self, name: str) -> bool:
        """Disable a tool."""
        # 使用锁保护整个操作
        async with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools[name]
            
            if tool.state == ToolState.DISABLED:
                return True
            
            # Check if any enabled tools depend on this one
            if name in self._dependencies:
                for dependent in self._dependencies[name]:
                    dep_tool = self._tools.get(dependent)
                    if dep_tool and dep_tool.state in (ToolState.ENABLED, ToolState.LOADED):
                        # 记录警告但不递归禁用
                        logger.warning(f"Tool '{dependent}' depends on '{name}' but will not be auto-disabled")
        
        # Unload the tool (在锁外执行)
        await self._unload_tool(name)
        
        # 获取锁更新状态
        async with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools[name]
            if tool.state == ToolState.DISABLED:
                return True
            
            self._set_tool_state(name, ToolState.DISABLED)
            return True
    
    async def _load_tool(self, name: str) -> bool:
        """Load a tool (internal)."""
        tool = self._tools[name]
        
        self._set_tool_state(name, ToolState.LOADING)
        
        try:
            # Simulate tool loading (in real implementation, this would load the actual tool)
            await asyncio.sleep(0.1)
            
            tool.loaded_at = datetime.now()
            self._set_tool_state(name, ToolState.LOADED)
            
            logger.info(f"Loaded MCP tool: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load tool '{name}': {e}")
            self._set_tool_state(name, ToolState.ERROR, str(e))
            return False
    
    async def _unload_tool(self, name: str) -> bool:
        """Unload a tool (internal)."""
        tool = self._tools[name]
        
        self._set_tool_state(name, ToolState.UNLOADING)
        
        try:
            # Simulate tool unloading
            await asyncio.sleep(0.05)
            
            tool.loaded_at = None
            self._set_tool_state(name, ToolState.DISABLED)
            
            logger.info(f"Unloaded MCP tool: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload tool '{name}': {e}")
            return False
    
    def get_tool(self, name: str) -> ToolInfo | None:
        """Get tool information."""
        return self._tools.get(name)
    
    def get_tool_state(self, name: str) -> ToolState | None:
        """Get tool state."""
        tool = self._tools.get(name)
        return tool.state if tool else None
    
    def is_tool_enabled(self, name: str) -> bool:
        """Check if a tool is enabled."""
        tool = self._tools.get(name)
        return tool is not None and tool.state in (ToolState.ENABLED, ToolState.LOADED)
    
    def is_tool_available(self, name: str) -> bool:
        """Check if a tool is available for use."""
        return self.is_tool_enabled(name)
    
    def list_tools(self, enabled_only: bool = False) -> list[ToolInfo]:
        """List all registered tools."""
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.state in (ToolState.ENABLED, ToolState.LOADED)]
        return tools
    
    def get_enabled_tools(self) -> list[ToolInfo]:
        """Get all enabled tools."""
        return self.list_tools(enabled_only=True)
    
    def get_tool_dependencies(self, name: str) -> list[str]:
        """Get dependencies for a tool."""
        tool = self._tools.get(name)
        return list(tool.config.dependencies) if tool else []
    
    def get_tool_dependents(self, name: str) -> list[str]:
        """Get tools that depend on this tool."""
        return list(self._dependencies.get(name, set()))
    
    def check_dependency_conflicts(self, name: str) -> list[str]:
        """Check for dependency conflicts."""
        conflicts = []
        tool = self._tools.get(name)
        
        if not tool:
            return conflicts
        
        for dep in tool.config.dependencies:
            if dep not in self._tools:
                conflicts.append(f"Missing dependency: {dep}")
            elif self._tools[dep].state == ToolState.ERROR:
                conflicts.append(f"Dependency '{dep}' is in error state")
        
        return conflicts
    
    async def update_tool_config(self, name: str, config: MCPToolConfig) -> bool:
        """Update tool configuration."""
        async with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools[name]
            was_enabled = tool.state in (ToolState.ENABLED, ToolState.LOADED)
            
            # Disable if enabled
            if was_enabled:
                await self.disable_tool(name)
            
            # Update config
            tool.config = config
            
            # Re-enable if it was enabled
            if was_enabled and config.enabled:
                await self.enable_tool(name)
            
            logger.info(f"Updated MCP tool config: {name}")
            return True
    
    def record_tool_use(self, name: str) -> None:
        """Record tool usage."""
        tool = self._tools.get(name)
        if tool:
            tool.use_count += 1
            tool.last_used = datetime.now()
    
    def get_tool_stats(self, name: str) -> dict[str, Any] | None:
        """Get tool usage statistics."""
        tool = self._tools.get(name)
        if not tool:
            return None
        
        return {
            "name": tool.name,
            "state": tool.state.name,
            "use_count": tool.use_count,
            "loaded_at": tool.loaded_at.isoformat() if tool.loaded_at else None,
            "last_used": tool.last_used.isoformat() if tool.last_used else None,
            "error_message": tool.error_message,
        }
    
    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tools."""
        return {name: self.get_tool_stats(name) for name in self._tools}
    
    def get_tools_info(self) -> list[dict[str, Any]]:
        """Get information about all tools for API response."""
        return [
            {
                "name": tool.name,
                "description": tool.config.description,
                "enabled": tool.config.enabled,
                "state": tool.state.name,
                "dependencies": tool.config.dependencies,
                "capabilities": tool.capabilities,
                "use_count": tool.use_count,
                "last_used": tool.last_used.isoformat() if tool.last_used else None,
            }
            for tool in self._tools.values()
        ]
    
    async def enable_all_tools(self) -> dict[str, bool]:
        """Enable all tools that are configured as enabled."""
        results = {}
        for name, tool in self._tools.items():
            if tool.config.enabled:
                results[name] = await self.enable_tool(name)
            else:
                results[name] = True
        return results
    
    async def disable_all_tools(self) -> dict[str, bool]:
        """Disable all tools."""
        results = {}
        for name in list(self._tools.keys()):
            results[name] = await self.disable_tool(name)
        return results
    
    def resolve_load_order(self) -> list[str]:
        """Resolve the correct load order based on dependencies."""
        # Topological sort
        visited = set()
        temp_mark = set()
        order = []
        
        def visit(name: str) -> None:
            if name in temp_mark:
                raise ValueError(f"Circular dependency detected involving {name}")
            if name in visited:
                return
            
            temp_mark.add(name)
            tool = self._tools.get(name)
            if tool:
                for dep in tool.config.dependencies:
                    if dep in self._tools:
                        visit(dep)
            temp_mark.remove(name)
            visited.add(name)
            order.append(name)
        
        for name in self._tools:
            if name not in visited:
                visit(name)
        
        return order