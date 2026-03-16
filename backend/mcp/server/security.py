"""MCP Security module.

Provides security features including:
- Access control and permissions
- Rate limiting
- Request validation
- Encryption support
"""

import time
import hashlib
import secrets
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from loguru import logger

from backend.mcp.config import MCPSecurityConfig


class PermissionLevel(Enum):
    """Permission levels for MCP access."""
    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry."""
    count: int = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: float | None = None


@dataclass
class AccessToken:
    """Access token for MCP authentication."""
    token: str
    permissions: PermissionLevel
    created_at: datetime
    expires_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class MCPPermissionManager:
    """Manages permissions and access control for MCP.
    
    Features:
    - Token-based authentication
    - Permission levels
    - Rate limiting
    - Origin validation
    """
    
    def __init__(self, config: MCPSecurityConfig | None = None):
        self.config = config or MCPSecurityConfig()
        self._tokens: dict[str, AccessToken] = {}
        self._rate_limits: dict[str, RateLimitEntry] = {}
        self._permission_cache: dict[str, PermissionLevel] = {}
        self._cleanup_task = None
    
    def generate_token(
        self,
        permissions: PermissionLevel = PermissionLevel.READ,
        expires_in_hours: int = 24,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """Generate a new access token."""
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        
        access_token = AccessToken(
            token=token,
            permissions=permissions,
            created_at=now,
            expires_at=now + timedelta(hours=expires_in_hours),
            metadata=metadata or {},
        )
        
        self._tokens[token] = access_token
        logger.info(f"Generated MCP access token with {permissions.name} permissions")
        
        return token
    
    def revoke_token(self, token: str) -> bool:
        """Revoke an access token."""
        if token in self._tokens:
            del self._tokens[token]
            logger.info("Revoked MCP access token")
            return True
        return False
    
    def validate_token(self, token: str) -> AccessToken | None:
        """Validate an access token."""
        if not self.config.require_auth:
            # Auth disabled, return admin level
            return AccessToken(
                token="anonymous",
                permissions=PermissionLevel.ADMIN,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=365),
            )
        
        access_token = self._tokens.get(token)
        if not access_token:
            return None
        
        # Check expiration
        if datetime.now() > access_token.expires_at:
            del self._tokens[token]
            return None
        
        return access_token
    
    def check_permission(self, token: str, required_level: PermissionLevel) -> bool:
        """Check if token has required permission level."""
        access_token = self.validate_token(token)
        if not access_token:
            return False
        
        return access_token.permissions.value >= required_level.value
    
    def validate_origin(self, origin: str) -> bool:
        """Validate if origin is allowed."""
        if not self.config.security.enabled:
            return True
        
        if "*" in self.config.allowed_origins:
            return True
        
        # Extract host from origin
        try:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            host = parsed.hostname or origin
        except:
            host = origin
        
        return host in self.config.allowed_origins or origin in self.config.allowed_origins
    
    def check_rate_limit(self, identifier: str) -> tuple[bool, dict[str, Any]]:
        """Check and update rate limit for an identifier.
        
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        if not self.config.enabled:
            return True, {"limit": float('inf'), "remaining": float('inf'), "reset": 0}
        
        now = time.time()
        entry = self._rate_limits.get(identifier)
        
        if entry is None:
            entry = RateLimitEntry()
            self._rate_limits[identifier] = entry
        
        # Check if blocked
        if entry.blocked_until and now < entry.blocked_until:
            return False, {
                "limit": self.config.rate_limit_requests,
                "remaining": 0,
                "reset": entry.blocked_until,
                "retry_after": int(entry.blocked_until - now),
            }
        
        # Reset window if expired
        window_duration = self.config.rate_limit_window
        if now - entry.window_start > window_duration:
            entry.count = 0
            entry.window_start = now
            entry.blocked_until = None
        
        # Increment count
        entry.count += 1
        
        # Check if limit exceeded
        if entry.count > self.config.rate_limit_requests:
            # Block for the window duration
            entry.blocked_until = now + window_duration
            logger.warning(f"Rate limit exceeded for {identifier}")
            return False, {
                "limit": self.config.rate_limit_requests,
                "remaining": 0,
                "reset": entry.blocked_until,
                "retry_after": window_duration,
            }
        
        remaining = self.config.rate_limit_requests - entry.count
        reset_time = entry.window_start + window_duration
        
        return True, {
            "limit": self.config.rate_limit_requests,
            "remaining": remaining,
            "reset": reset_time,
        }
    
    def validate_request_size(self, size_bytes: int) -> bool:
        """Validate request size."""
        if not self.config.enabled:
            return True
        return size_bytes <= self.config.max_request_size
    
    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging/storage."""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def sanitize_log_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize data for logging (remove sensitive fields)."""
        sensitive_fields = {"token", "api_key", "password", "secret", "auth"}
        sanitized = {}
        
        for key, value in data.items():
            if any(sf in key.lower() for sf in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_log_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_log_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def create_secure_context(self) -> dict[str, Any]:
        """Create a secure context for MCP operations."""
        return {
            "encryption_enabled": self.config.encryption_enabled,
            "require_auth": self.config.require_auth,
            "max_request_size": self.config.max_request_size,
            "rate_limit": {
                "requests": self.config.rate_limit_requests,
                "window": self.config.rate_limit_window,
            },
        }
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens. Returns count of removed tokens."""
        now = datetime.now()
        expired = [
            token for token, access_token in self._tokens.items()
            if now > access_token.expires_at
        ]
        
        for token in expired:
            del self._tokens[token]
        
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired tokens")
        
        return len(expired)
    
    def cleanup_rate_limits(self) -> int:
        """Clean up old rate limit entries. Returns count of removed entries."""
        now = time.time()
        window_duration = self.config.rate_limit_window * 2  # Keep for 2 windows
        
        expired = [
            identifier for identifier, entry in self._rate_limits.items()
            if now - entry.window_start > window_duration
        ]
        
        for identifier in expired:
            del self._rate_limits[identifier]
        
        return len(expired)
    
    def get_security_status(self) -> dict[str, Any]:
        """Get current security status."""
        return {
            "enabled": self.config.enabled,
            "require_auth": self.config.require_auth,
            "encryption_enabled": self.config.encryption_enabled,
            "active_tokens": len(self._tokens),
            "rate_limit_entries": len(self._rate_limits),
            "allowed_origins_count": len(self.config.allowed_origins),
            "max_request_size": self.config.max_request_size,
            "rate_limit": {
                "requests": self.config.rate_limit_requests,
                "window_seconds": self.config.rate_limit_window,
            },
        }
    
    def encrypt_data(self, data: str, key: str | None = None) -> str:
        """Encrypt sensitive data."""
        if not self.config.encryption_enabled:
            return data
        
        # In production, use proper encryption (e.g., Fernet from cryptography)
        # This is a placeholder implementation
        try:
            from cryptography.fernet import Fernet
            
            if key is None:
                key = Fernet.generate_key()
            
            f = Fernet(key)
            encrypted = f.encrypt(data.encode())
            return encrypted.decode()
        except ImportError:
            logger.warning("cryptography not installed, encryption disabled")
            return data
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return data
    
    def decrypt_data(self, encrypted_data: str, key: str) -> str:
        """Decrypt encrypted data."""
        if not self.config.encryption_enabled:
            return encrypted_data
        
        try:
            from cryptography.fernet import Fernet
            
            f = Fernet(key.encode())
            decrypted = f.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except ImportError:
            return encrypted_data
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return encrypted_data


class MCPAccessControl:
    """Fine-grained access control for MCP resources."""
    
    def __init__(self):
        self._resource_permissions: dict[str, dict[str, PermissionLevel]] = {}
        self._default_permissions: PermissionLevel = PermissionLevel.NONE
    
    def set_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        token: str,
        level: PermissionLevel
    ) -> None:
        """Set permission for a specific resource."""
        key = f"{resource_type}:{resource_id}"
        if key not in self._resource_permissions:
            self._resource_permissions[key] = {}
        self._resource_permissions[key][token] = level
    
    def check_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        token: str,
        required_level: PermissionLevel
    ) -> bool:
        """Check permission for a specific resource."""
        key = f"{resource_type}:{resource_id}"
        permissions = self._resource_permissions.get(key, {})
        level = permissions.get(token, self._default_permissions)
        return level.value >= required_level.value
    
    def revoke_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        token: str
    ) -> bool:
        """Revoke permission for a specific resource."""
        key = f"{resource_type}:{resource_id}"
        if key in self._resource_permissions and token in self._resource_permissions[key]:
            del self._resource_permissions[key][token]
            return True
        return False
    
    def list_resource_permissions(self, resource_type: str, resource_id: str) -> dict[str, str]:
        """List all permissions for a resource."""
        key = f"{resource_type}:{resource_id}"
        permissions = self._resource_permissions.get(key, {})
        return {token: level.name for token, level in permissions.items()}