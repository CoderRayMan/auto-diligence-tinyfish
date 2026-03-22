"""
Stateful Token Vault - Centralized session management for Site Agents.

This module implements the critical complexity of maintaining session state
across multiple concurrent agents accessing government and court portals.
"""

import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import redis


@dataclass
class SessionToken:
    """Represents a cached session with metadata."""
    site_id: str
    cookies: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    refresh_token: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now() > self.expires_at
    
    def ttl_seconds(self) -> int:
        """Return remaining time to live in seconds."""
        return int((self.expires_at - datetime.now()).total_seconds())
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "site_id": self.site_id,
            "cookies": self.cookies,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "refresh_token": self.refresh_token,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionToken":
        """Deserialize from dictionary."""
        return cls(
            site_id=data["site_id"],
            cookies=data["cookies"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            refresh_token=data.get("refresh_token"),
            metadata=data.get("metadata")
        )


class TokenVault:
    """
    Centralized token vault for managing sessions across Site Agents.
    
    The vault ensures that when Agent A logs into a site, Agent B can
    reuse that session without re-authenticating, dramatically improving
    efficiency and reliability.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, default_ttl: int = 3600):
        """
        Initialize the token vault.
        
        Args:
            redis_client: Optional Redis client for distributed storage
            default_ttl: Default time-to-live for tokens in seconds
        """
        self._redis = redis_client
        self._local_cache: Dict[str, SessionToken] = {}
        self._default_ttl = default_ttl
        
    def _get_key(self, site_id: str) -> str:
        """Generate storage key for a site."""
        return f"autodiligence:token:{site_id}"
    
    def save(self, site_id: str, cookies: Dict[str, Any], 
             ttl: Optional[int] = None, refresh_token: Optional[str] = None,
             metadata: Optional[Dict[str, Any]] = None) -> SessionToken:
        """
        Save a session token to the vault.
        
        Args:
            site_id: Unique identifier for the site
            cookies: Playwright cookies from successful login
            ttl: Time to live in seconds (defaults to 3600)
            refresh_token: Optional refresh token for renewal
            metadata: Additional metadata (user agent, IP, etc.)
            
        Returns:
            The saved SessionToken
        """
        now = datetime.now()
        expires = now + timedelta(seconds=ttl or self._default_ttl)
        
        token = SessionToken(
            site_id=site_id,
            cookies=cookies,
            created_at=now,
            expires_at=expires,
            refresh_token=refresh_token,
            metadata=metadata
        )
        
        # Save to Redis if available
        if self._redis:
            key = self._get_key(site_id)
            self._redis.setex(
                key,
                ttl or self._default_ttl,
                json.dumps(token.to_dict())
            )
        else:
            # Fall back to local cache
            self._local_cache[site_id] = token
            
        return token
    
    def get(self, site_id: str) -> Optional[SessionToken]:
        """
        Retrieve a session token from the vault.
        
        Args:
            site_id: Unique identifier for the site
            
        Returns:
            SessionToken if found and valid, None otherwise
        """
        # Try Redis first
        if self._redis:
            key = self._get_key(site_id)
            data = self._redis.get(key)
            if data:
                return SessionToken.from_dict(json.loads(data))
            return None
        
        # Fall back to local cache
        token = self._local_cache.get(site_id)
        if token and not token.is_expired():
            return token
        elif token and token.is_expired():
            # Clean up expired token
            del self._local_cache[site_id]
            
        return None
    
    def refresh(self, site_id: str, new_cookies: Dict[str, Any]) -> Optional[SessionToken]:
        """
        Refresh an existing token with new cookies.
        
        Args:
            site_id: Site identifier
            new_cookies: Updated cookies
            
        Returns:
            Updated SessionToken or None if original doesn't exist
        """
        existing = self.get(site_id)
        if not existing:
            return None
            
        # Update with new cookies, keep same expiry window
        ttl = existing.ttl_seconds()
        if ttl > 0:
            return self.save(
                site_id=site_id,
                cookies=new_cookies,
                ttl=ttl,
                refresh_token=existing.refresh_token,
                metadata=existing.metadata
            )
        
        # Token expired, need full re-login
        return None
    
    def invalidate(self, site_id: str) -> bool:
        """
        Invalidate (delete) a token from the vault.
        
        Args:
            site_id: Site identifier to invalidate
            
        Returns:
            True if token was found and removed
        """
        if self._redis:
            key = self._get_key(site_id)
            result = self._redis.delete(key)
            return result > 0
        else:
            if site_id in self._local_cache:
                del self._local_cache[site_id]
                return True
        return False
    
    def is_valid(self, site_id: str) -> bool:
        """
        Check if a valid token exists for a site.
        
        Args:
            site_id: Site identifier
            
        Returns:
            True if valid token exists
        """
        token = self.get(site_id)
        return token is not None and not token.is_expired()
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired tokens from local cache.
        
        Returns:
            Number of tokens removed
        """
        if self._redis:
            # Redis handles expiration automatically
            return 0
            
        expired = [
            site_id for site_id, token in self._local_cache.items()
            if token.is_expired()
        ]
        
        for site_id in expired:
            del self._local_cache[site_id]
            
        return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vault statistics."""
        if self._redis:
            # Count keys matching our pattern
            keys = self._redis.keys("autodiligence:token:*")
            return {
                "total_tokens": len(keys),
                "storage": "redis",
                "default_ttl": self._default_ttl
            }
        else:
            return {
                "total_tokens": len(self._local_cache),
                "storage": "local",
                "default_ttl": self._default_ttl
            }


# Singleton instance for application-wide use
_vault_instance: Optional[TokenVault] = None


def get_token_vault(redis_client: Optional[redis.Redis] = None, 
                    default_ttl: int = 3600) -> TokenVault:
    """
    Get or create the singleton token vault instance.
    
    Args:
        redis_client: Optional Redis client
        default_ttl: Default token TTL
        
    Returns:
        TokenVault instance
    """
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = TokenVault(redis_client, default_ttl)
    return _vault_instance
