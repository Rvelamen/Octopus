#!/usr/bin/env python3
"""Send a WeChat message directly using stored tokens.

Usage:
    python scripts/send_wechat.py "消息内容"
    python scripts/send_wechat.py "消息内容" --to user_id
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data import Database
from backend.data.provider_store import ChannelConfigRepository


WECHAT_API_BASE = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "3.2.0.109"


def markdown_to_plain_text(text: str) -> str:
    """Convert markdown-formatted text to plain text for WeChat delivery."""
    if not text:
        return text
    
    result = text
    result = re.sub(r'```[^\n]*\n?([\s\S]*?)```', lambda m: m.group(1).strip(), result)
    result = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', result)
    result = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', result)
    result = re.sub(r'^\|[\s:|-]+\|$', '', result, flags=re.MULTILINE)
    result = re.sub(r'^\|(.+)\|$', lambda m: '  '.join(cell.strip() for cell in m.group(1).split('|')), result, flags=re.MULTILINE)
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    result = re.sub(r'__([^_]+)__', r'\1', result)
    result = re.sub(r'_([^_]+)_', r'\1', result)
    result = re.sub(r'~~([^~]+)~~', r'\1', result)
    result = re.sub(r'`([^`]+)`', r'\1', result)
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)
    result = re.sub(r'^[-*+]\s+', '• ', result, flags=re.MULTILINE)
    result = re.sub(r'^\d+\.\s+', '', result, flags=re.MULTILINE)
    result = re.sub(r'^---+\s*$', '──────────', result, flags=re.MULTILINE)
    result = re.sub(r'^\*\*\*+\s*$', '──────────', result, flags=re.MULTILINE)
    
    return result


def get_wechat_config() -> dict:
    """Get WeChat config from database."""
    db = Database()
    repo = ChannelConfigRepository(db)
    config = repo.get_channel_config("wechat")
    
    if not config:
        raise ValueError("WeChat channel not configured")
    
    config_json = config.config_json if isinstance(config.config_json, dict) else json.loads(config.config_json or "{}")
    
    bot_token = config.app_secret
    context_tokens = config_json.get("contextTokens", {})
    
    if not bot_token:
        raise ValueError("bot_token not found in WeChat config (app_secret field)")
    
    return {
        "bot_token": bot_token,
        "context_tokens": context_tokens,
    }


def random_wechat_uin() -> str:
    """Generate a random WeChat UIN (base64 encoded uint32)."""
    import random
    import base64
    uint32 = random.randint(0, 4294967295)
    return base64.b64encode(str(uint32).encode('utf-8')).decode('utf-8')


async def send_wechat_message(to_user_id: str, content: str, bot_token: str, context_token: str) -> dict:
    """Send a message to a WeChat user."""
    plain_content = markdown_to_plain_text(content)
    
    import uuid
    client_id = f"openclaw-weixin-{uuid.uuid4().hex[:8]}"
    
    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": client_id,
            "message_type": 2,
            "message_state": 2,
            "context_token": context_token,
            "item_list": [
                {
                    "type": 1,
                    "text_item": {
                        "text": plain_content
                    }
                }
            ]
        },
        "base_info": {"channel_version": CHANNEL_VERSION}
    }
    
    body_str = json.dumps(payload, ensure_ascii=False)
    
    import base64
    uint32 = __import__('random').randint(0, 4294967295)
    wechat_uin = base64.b64encode(str(uint32).encode('utf-8')).decode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {bot_token.strip()}",
        "X-WECHAT-UIN": wechat_uin,
    }
    
    print(f"\n--- Request Details ---")
    print(f"URL: {WECHAT_API_BASE}/ilink/bot/sendmessage")
    print(f"to_user_id: {to_user_id}")
    print(f"client_id: {client_id}")
    print(f"bot_token: {bot_token[:30]}...")
    print(f"context_token: {context_token[:30]}...")
    print(f"content: {plain_content[:50]}...")
    print(f"X-WECHAT-UIN: {wechat_uin}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{WECHAT_API_BASE}/ilink/bot/sendmessage",
            content=body_str,
            headers=headers
        )
        
        print(f"\n--- Response ---")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        return response.json()


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Send WeChat message")
    parser.add_argument("content", help="Message content to send")
    parser.add_argument("--to", dest="to_user_id", help="Target user ID (default: first available)")
    parser.add_argument("--list-users", action="store_true", help="List available users")
    args = parser.parse_args()
    
    try:
        config = get_wechat_config()
        bot_token = config["bot_token"]
        context_tokens = config["context_tokens"]
        
        if args.list_users:
            print("Available users with context tokens:")
            for user_id in context_tokens:
                print(f"  - {user_id}")
            return
        
        if not context_tokens:
            print("No context tokens found. Send a message first to establish a session.")
            return
        
        if args.to_user_id:
            if args.to_user_id not in context_tokens:
                print(f"User {args.to_user_id} not found in context tokens")
                print("Available users:", list(context_tokens.keys()))
                return
            to_user_id = args.to_user_id
        else:
            to_user_id = list(context_tokens.keys())[0]
            print(f"Using first available user: {to_user_id}")
        
        context_token = context_tokens[to_user_id]
        
        print(f"Sending message to {to_user_id}...")
        print(f"Context token: {context_token[:20]}...")
        result = await send_wechat_message(to_user_id, args.content, bot_token, context_token)
        
        print(f"API Response: {result}")
        
        ret = result.get("ret")
        errcode = result.get("errcode")
        
        if (ret is not None and ret != 0) or (errcode is not None and errcode != 0):
            print(f"Failed to send: {result}")
        else:
            print("Message sent successfully!")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
