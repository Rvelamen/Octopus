"""Extension handlers for WebSocket messages (renamed from Skill handlers).

This module now handles Extension installation/removal using the new
Extension system. Kept as 'skills/registry.py' for backward compatibility
with Desktop client, but internally uses Extension system.
"""

import asyncio
import os
import uuid
import shutil
import re
import zipfile
import httpx
import yaml
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.core.events.types import InboundMessage
from backend.utils import get_extensions_path, get_plugins_path
from pydantic import ValidationError
from backend.channels.desktop.schemas import MESSAGE_TYPE_TO_SCHEMA

if TYPE_CHECKING:
    from backend.core.events.bus import MessageBus


# Extension Market API configuration
# Can be overridden by environment variable MARKET_API_BASE
EXTENSION_MARKET_API_BASE = os.environ.get("MARKET_API_BASE", "https://fanquanpintuan.cn/octopus")


class SkillInstallHandler:
    """Handle extension installation requests from Extension Market API.

    Note: Kept as 'SkillInstallHandler' for backward compatibility with Desktop client.
    Internally handles Extension installation.
    """

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Install an extension from Extension Market API."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_id = message.data.get("skill_id") or message.data.get("extension_id")
            extension_name = message.data.get("name")  # extension name from frontend
            request_id = message.request_id or str(uuid.uuid4())

            if not extension_id:
                await self._send_error(websocket, request_id, "Extension ID is required")
                return

            # Send installing status
            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_INSTALLING,
                request_id=request_id,
                data={"skill_id": extension_id, "extension_id": extension_id}
            ))

            # Ensure extensions directory exists
            get_extensions_path().mkdir(parents=True, exist_ok=True)

            # Execute installation in background
            asyncio.create_task(self._execute_install(
                websocket, request_id, extension_id, extension_name
            ))

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "installing", "extension_id": extension_id}
            ))

        except Exception as e:
            logger.error(f"Failed to start extension installation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to start installation: {e}")

    async def _execute_install(self, websocket: WebSocket, request_id: str,
                               extension_id: str, extension_name: str | None):
        """Execute the installation by downloading from API and extracting."""
        temp_zip_path = None
        try:
            # Step 1: Get extension details from API
            extension_detail = await self._fetch_extension_detail(extension_id)
            if not extension_detail:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.SKILL_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "skill_id": extension_id,
                        "extension_id": extension_id,
                        "error": f"Extension '{extension_id}' not found in market"
                    }
                ))
                return

            # Use provided name or fallback to extension name from API
            if not extension_name:
                extension_name = extension_detail.get("name", extension_id)

            # Sanitize extension name for directory
            extension_name = self._sanitize_extension_name(extension_name)

            # Step 2: Download ZIP file from API
            download_url = f"{EXTENSION_MARKET_API_BASE}/api/extensions/{extension_id}/download"
            temp_zip_path = get_extensions_path() / f"{extension_id}_{uuid.uuid4()}.zip"

            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_INSTALLING,
                request_id=request_id,
                data={"skill_id": extension_id, "extension_id": extension_id, "name": extension_name, "status": "downloading"}
            ))

            download_success = await self._download_zip(download_url, temp_zip_path)
            if not download_success:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.SKILL_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "skill_id": extension_id,
                        "extension_id": extension_id,
                        "name": extension_name,
                        "error": "Failed to download extension ZIP file"
                    }
                ))
                return

            # Step 3: Extract ZIP file
            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_INSTALLING,
                request_id=request_id,
                data={"skill_id": extension_id, "extension_id": extension_id, "name": extension_name, "status": "extracting"}
            ))

            extension_dir = get_extensions_path() / extension_name

            # Remove existing extension directory if exists
            if extension_dir.exists():
                shutil.rmtree(extension_dir)

            # Extract ZIP file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extension_dir)

            # Step 4: Verify installation (check for manifest.yaml or SKILL.md)
            manifest_path = extension_dir / "manifest.yaml"
            skill_md_path = extension_dir / "SKILL.md"

            if not manifest_path.exists() and not skill_md_path.exists():
                # Try to find files in subdirectories (in case ZIP has nested structure)
                for subdir in extension_dir.iterdir():
                    if subdir.is_dir():
                        nested_manifest = subdir / "manifest.yaml"
                        nested_skill_md = subdir / "SKILL.md"
                        if nested_manifest.exists() or nested_skill_md.exists():
                            # Move contents from subdirectory to extension_dir
                            for item in subdir.iterdir():
                                shutil.move(str(item), str(extension_dir / item.name))
                            shutil.rmtree(subdir)
                            break

            # Final verification
            if not manifest_path.exists() and not skill_md_path.exists():
                # Clean up and report error
                if extension_dir.exists():
                    shutil.rmtree(extension_dir)
                await self._send_response(websocket, WSMessage(
                    type=MessageType.SKILL_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "skill_id": extension_id,
                        "extension_id": extension_id,
                        "name": extension_name,
                        "error": "Invalid extension package: manifest.yaml or SKILL.md not found"
                    }
                ))
                return

            # Step 5: Auto-generate manifest.yaml if missing (for backward compatibility)
            if not manifest_path.exists() and skill_md_path.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.SKILL_INSTALLING,
                    request_id=request_id,
                    data={"skill_id": extension_id, "extension_id": extension_id, "name": extension_name, "status": "generating_manifest"}
                ))
                self._generate_manifest_from_skill(extension_dir, extension_name, skill_md_path)

            # Step 6: Install dependencies if requirements.txt exists
            requirements_file = extension_dir / "requirements.txt"
            if requirements_file.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.SKILL_INSTALLING,
                    request_id=request_id,
                    data={"skill_id": extension_id, "extension_id": extension_id, "name": extension_name, "status": "installing_deps"}
                ))
                try:
                    from backend.extensions.plugin_dependency import DependencyManager
                    dep_manager = DependencyManager(extension_dir)
                    await dep_manager.install(requirements_file)
                except Exception as e:
                    logger.warning(f"Failed to install dependencies for '{extension_name}': {e}")

            # Installation successful
            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_INSTALLED,
                request_id=request_id,
                data={
                    "success": True,
                    "skill_id": extension_id,
                    "extension_id": extension_id,
                    "name": extension_name,
                    "path": str(extension_dir)
                }
            ))
            logger.info(f"Extension '{extension_name}' (ID: {extension_id}) installed successfully from market API")

        except Exception as e:
            logger.error(f"Exception during extension installation: {e}")
            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_INSTALL_ERROR,
                request_id=request_id,
                data={
                    "success": False,
                    "skill_id": extension_id,
                    "extension_id": extension_id,
                    "name": extension_name,
                    "error": str(e)
                }
            ))
        finally:
            # Clean up temp ZIP file
            if temp_zip_path and temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove temp ZIP file: {e}")

    async def _fetch_extension_detail(self, extension_id: str) -> dict | None:
        """Fetch extension details from Extension Market API."""
        try:
            url = f"{EXTENSION_MARKET_API_BASE}/api/extensions/{extension_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # Handle API response wrapper format
                    if isinstance(data, dict) and 'data' in data:
                        return data['data']
                    return data
                else:
                    logger.error(f"Failed to fetch extension detail: HTTP {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching extension detail: {e}")
            return None

    async def _download_zip(self, url: str, dest_path: Path) -> bool:
        """Download ZIP file from URL to destination path."""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", url) as response:
                    if response.status_code == 200:
                        with open(dest_path, 'wb') as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                        return True
                    else:
                        logger.error(f"Failed to download ZIP: HTTP {response.status_code}")
                        return False
        except Exception as e:
            logger.error(f"Error downloading ZIP: {e}")
            return False

    def _sanitize_extension_name(self, name: str) -> str:
        """Sanitize extension name for use as directory name."""
        # Replace unsafe characters
        unsafe = '<>:"/\\|?*'
        for char in unsafe:
            name = name.replace(char, "_")
        # Remove leading/trailing whitespace and dots
        name = name.strip().strip(".")
        # Ensure not empty
        if not name:
            name = "unnamed_extension"
        return name

    def _generate_manifest_from_skill(self, extension_dir: Path, extension_name: str, skill_md_path: Path) -> None:
        """Generate manifest.yaml from SKILL.md for backward compatibility.

        Parses the SKILL.md frontmatter and creates a manifest.yaml with
        appropriate type detection (skill, worker, or hybrid).
        """
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            manifest = {
                "name": extension_name,
                "description": "",
                "version": "1.0.0",
                "author": "unknown",
                "type": "skill",
                "capabilities": []
            }

            # Parse YAML frontmatter if present
            if content.startswith("---"):
                match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if match:
                    try:
                        frontmatter = yaml.safe_load(match.group(1)) or {}

                        # Extract basic fields
                        if "name" in frontmatter:
                            manifest["name"] = frontmatter["name"]
                        if "description" in frontmatter:
                            desc = frontmatter["description"]
                            # Handle multiline descriptions (fold to single line)
                            if isinstance(desc, str):
                                manifest["description"] = " ".join(desc.split())

                        # Extract octopus metadata
                        octopus_meta = frontmatter.get("octopus", {})
                        if octopus_meta:
                            if "capabilities" in octopus_meta:
                                manifest["capabilities"] = octopus_meta["capabilities"]
                    except yaml.YAMLError as e:
                        logger.warning(f"Failed to parse SKILL.md frontmatter: {e}")

            # Detect extension type based on files present
            has_worker = (extension_dir / "worker.py").exists()
            has_skill = (extension_dir / "SKILL.md").exists()
            has_plugin_handlers = (extension_dir / "handlers.py").exists()

            if has_worker and has_plugin_handlers:
                manifest["type"] = "hybrid"
            elif has_worker:
                manifest["type"] = "worker"
            elif has_plugin_handlers:
                manifest["type"] = "plugin"
            else:
                manifest["type"] = "skill"

            # Write manifest.yaml
            manifest_path = extension_dir / "manifest.yaml"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            logger.info(f"Generated manifest.yaml for extension '{extension_name}' (type: {manifest['type']})")

        except Exception as e:
            logger.error(f"Failed to generate manifest.yaml for '{extension_name}': {e}")
            # Don't raise - installation should still succeed even if manifest generation fails

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


# =============================================================================
# Unified Extension Handlers (New)
# These handlers replace Skill/Plugin handlers with unified Extension system
# =============================================================================


class ExtensionGetListHandler:
    """Handle get extensions list requests (market or installed)."""

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of extensions (installed or from market)."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            list_type = message.data.get("type", "installed")  # "installed" or "market"
            extension_type = message.data.get("extension_type")  # "skill", "plugin", "worker", or None for all

            if list_type == "market":
                extensions = await self._fetch_market_extensions(extension_type)
            else:
                extensions = self._get_installed_extensions(extension_type)

            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_LIST,
                request_id=message.request_id,
                data={
                    "extensions": extensions,
                    "type": list_type,
                    "extension_type": extension_type
                }
            ))

        except Exception as e:
            logger.error(f"Failed to get extensions list: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get extensions list: {e}")

    async def _fetch_market_extensions(self, extension_type: str | None) -> list[dict]:
        """Fetch extensions from Market API."""
        try:
            url = f"{EXTENSION_MARKET_API_BASE}/api/extensions"
            params = {}
            if extension_type:
                params["type"] = extension_type

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # Handle API response wrapper format
                    if isinstance(data, dict):
                        # Try to get extensions from data.list or data.extensions
                        if 'data' in data:
                            inner_data = data['data']
                            if isinstance(inner_data, dict):
                                return inner_data.get("list", []) or inner_data.get("extensions", [])
                        return data.get("extensions", []) or data.get("list", [])
                    return []
                return []
        except Exception as e:
            logger.error(f"Error fetching market extensions: {e}")
            return []

    def _get_installed_extensions(self, extension_type: str | None) -> list[dict]:
        """Get installed extensions from local directory."""
        extensions = []

        if get_extensions_path().exists():
            for ext_dir in get_extensions_path().iterdir():
                if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                    # Read extension_id from .extension_id file
                    ext_id = self._read_extension_id(ext_dir)
                    if not ext_id:
                        continue

                    metadata = self._parse_extension_metadata(ext_dir)

                    # Filter by type if specified
                    ext_type = metadata.get("type", "skill")
                    if extension_type and ext_type != extension_type:
                        continue

                    # Use manifest name if available, otherwise use directory name
                    ext_name = metadata.get("name", ext_dir.name)

                    extensions.append({
                        "id": ext_id,
                        "name": ext_name,
                        "path": str(ext_dir),
                        "type": ext_type,
                        "metadata": metadata,
                        "installed_at": ext_dir.stat().st_mtime
                    })

        return extensions

    def _read_extension_id(self, ext_dir: Path) -> str | None:
        """Read extension ID from .extension_id file."""
        extension_id_file = ext_dir / ".extension_id"
        if extension_id_file.exists():
            try:
                return extension_id_file.read_text(encoding='utf-8').strip()
            except Exception as e:
                logger.warning(f"Failed to read .extension_id from {ext_dir}: {e}")
        return None

    def _parse_extension_metadata(self, ext_dir: Path) -> dict:
        """Parse metadata from manifest.yaml or SKILL.md."""
        manifest_file = ext_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to parse manifest.yaml from {ext_dir}: {e}")

        skill_file = ext_dir / "SKILL.md"
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                if content.startswith("---"):
                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                    if match:
                        metadata = {}
                        for line in match.group(1).split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip().strip('"\'')
                        return metadata
            except Exception as e:
                logger.warning(f"Failed to parse SKILL.md from {ext_dir}: {e}")

        return {}

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ExtensionInstallHandler:
    """Handle extension installation requests from Extension Market API."""

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Install an extension from Extension Market API."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_id = message.data.get("extension_id")
            extension_name = message.data.get("name")
            env_vars = message.data.get("env_vars", {})  # Environment variables for plugins
            request_id = message.request_id or str(uuid.uuid4())

            if not extension_id:
                await self._send_error(websocket, request_id, "Extension ID is required")
                return

            # Send installing status
            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_INSTALLING,
                request_id=request_id,
                data={"extension_id": extension_id, "name": extension_name}
            ))

            # Ensure extensions directory exists
            get_extensions_path().mkdir(parents=True, exist_ok=True)

            # Execute installation in background
            asyncio.create_task(self._execute_install(
                websocket, request_id, extension_id, extension_name, env_vars
            ))

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "installing", "extension_id": extension_id}
            ))

        except Exception as e:
            logger.error(f"Failed to start extension installation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to start installation: {e}")

    async def _execute_install(self, websocket: WebSocket, request_id: str,
                               extension_id: str, extension_name: str | None, env_vars: dict):
        """Execute the installation by downloading from API and extracting."""
        temp_zip_path = None
        try:
            # Step 1: Get extension details from API
            extension_detail = await self._fetch_extension_detail(extension_id)
            if not extension_detail:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.EXTENSION_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "extension_id": extension_id,
                        "error": f"Extension '{extension_id}' not found in market"
                    }
                ))
                return

            # Use provided name or fallback to extension name from API
            if not extension_name:
                extension_name = extension_detail.get("name", extension_id)

            # Sanitize extension name for directory
            extension_name = self._sanitize_extension_name(extension_name)

            # Get extension type
            ext_type = extension_detail.get("type", "skill")

            # Step 2: Download ZIP file from API
            download_url = f"{EXTENSION_MARKET_API_BASE}/api/extensions/{extension_id}/download"
            temp_zip_path = get_extensions_path() / f"{extension_id}_{uuid.uuid4()}.zip"

            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_INSTALLING,
                request_id=request_id,
                data={"extension_id": extension_id, "name": extension_name, "status": "downloading"}
            ))

            download_success = await self._download_zip(download_url, temp_zip_path)
            if not download_success:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.EXTENSION_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "extension_id": extension_id,
                        "name": extension_name,
                        "error": "Failed to download extension ZIP file"
                    }
                ))
                return

            # Step 3: Extract ZIP file
            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_INSTALLING,
                request_id=request_id,
                data={"extension_id": extension_id, "name": extension_name, "status": "extracting"}
            ))

            # Use sanitized extension name as directory name
            extension_dir = get_extensions_path() / extension_name

            # Remove existing extension directory if exists
            if extension_dir.exists():
                shutil.rmtree(extension_dir)

            # Extract ZIP file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extension_dir)

            # Step 4: Handle nested structure
            manifest_path = extension_dir / "manifest.yaml"
            skill_md_path = extension_dir / "SKILL.md"

            if not manifest_path.exists() and not skill_md_path.exists():
                for subdir in extension_dir.iterdir():
                    if subdir.is_dir():
                        nested_manifest = subdir / "manifest.yaml"
                        nested_skill_md = subdir / "SKILL.md"
                        if nested_manifest.exists() or nested_skill_md.exists():
                            for item in subdir.iterdir():
                                shutil.move(str(item), str(extension_dir / item.name))
                            shutil.rmtree(subdir)
                            break

            # Step 5: Generate manifest.yaml if missing
            if not manifest_path.exists() and skill_md_path.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.EXTENSION_INSTALLING,
                    request_id=request_id,
                    data={"extension_id": extension_id, "name": extension_name, "status": "generating_manifest"}
                ))
                self._generate_manifest_from_skill(extension_dir, extension_name, skill_md_path, ext_type)

            # Step 6: Save environment variables for plugin type
            if ext_type == "plugin" and env_vars:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.EXTENSION_INSTALLING,
                    request_id=request_id,
                    data={"extension_id": extension_id, "name": extension_name, "status": "saving_config"}
                ))
                self._save_env_vars(extension_dir, env_vars)

            # Step 7: Install dependencies (for all extension types)
            requirements_file = extension_dir / "requirements.txt"
            if requirements_file.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.EXTENSION_INSTALLING,
                    request_id=request_id,
                    data={"extension_id": extension_id, "name": extension_name, "status": "installing_deps"}
                ))
                try:
                    from backend.extensions.plugin_dependency import DependencyManager
                    dep_manager = DependencyManager(extension_dir)
                    await dep_manager.install(requirements_file)
                except Exception as e:
                    logger.warning(f"Failed to install dependencies for '{extension_name}': {e}")

            # Step 8: Create .extension_id file to store the real extension ID
            extension_id_file = extension_dir / ".extension_id"
            try:
                extension_id_file.write_text(extension_id, encoding='utf-8')
                logger.info(f"Created .extension_id file for extension '{extension_name}' with ID: {extension_id}")
            except Exception as e:
                logger.warning(f"Failed to create .extension_id file for '{extension_name}': {e}")

            # Step 9: Check if configuration is needed
            config_params = self._check_required_config(extension_dir, extension_name)

            # Installation successful
            response_data = {
                "success": True,
                "extension_id": extension_id,
                "name": extension_name,
                "type": ext_type,
                "path": str(extension_dir)
            }

            # If configuration is needed, include config params
            if config_params:
                response_data["requires_config"] = True
                response_data["config_params"] = config_params
                logger.info(f"Extension '{extension_name}' installed but requires configuration")
            else:
                response_data["requires_config"] = False

            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_INSTALLED,
                request_id=request_id,
                data=response_data
            ))
            logger.info(f"Extension '{extension_name}' (ID: {extension_id}, type: {ext_type}) installed successfully")

        except Exception as e:
            logger.error(f"Exception during extension installation: {e}")
            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_INSTALL_ERROR,
                request_id=request_id,
                data={
                    "success": False,
                    "extension_id": extension_id,
                    "name": extension_name,
                    "error": str(e)
                }
            ))
        finally:
            if temp_zip_path and temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove temp ZIP file: {e}")

    async def _fetch_extension_detail(self, extension_id: str) -> dict | None:
        """Fetch extension details from Extension Market API."""
        try:
            url = f"{EXTENSION_MARKET_API_BASE}/api/extensions/{extension_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # Handle API response wrapper format
                    if isinstance(data, dict) and 'data' in data:
                        return data['data']
                    return data
                return None
        except Exception as e:
            logger.error(f"Error fetching extension detail: {e}")
            return None

    async def _download_zip(self, url: str, dest_path: Path) -> bool:
        """Download ZIP file from URL to destination path."""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", url) as response:
                    if response.status_code == 200:
                        with open(dest_path, 'wb') as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error downloading ZIP: {e}")
            return False

    def _sanitize_extension_name(self, name: str) -> str:
        """Sanitize extension name for use as directory name."""
        unsafe = '<>:"/\\|?*'
        for char in unsafe:
            name = name.replace(char, "_")
        name = name.strip().strip(".")
        if not name:
            name = "unnamed_extension"
        return name

    def _generate_manifest_from_skill(self, extension_dir: Path, extension_name: str,
                                       skill_md_path: Path, ext_type: str = "skill") -> None:
        """Generate manifest.yaml from SKILL.md."""
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            manifest = {
                "name": extension_name,
                "description": "",
                "version": "1.0.0",
                "author": "unknown",
                "type": ext_type,
                "capabilities": []
            }

            if content.startswith("---"):
                match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if match:
                    try:
                        frontmatter = yaml.safe_load(match.group(1)) or {}
                        if "name" in frontmatter:
                            manifest["name"] = frontmatter["name"]
                        if "description" in frontmatter:
                            desc = frontmatter["description"]
                            if isinstance(desc, str):
                                manifest["description"] = " ".join(desc.split())
                        octopus_meta = frontmatter.get("octopus", {})
                        if octopus_meta:
                            if "capabilities" in octopus_meta:
                                manifest["capabilities"] = octopus_meta["capabilities"]
                    except yaml.YAMLError:
                        pass

            manifest_path = extension_dir / "manifest.yaml"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            logger.info(f"Generated manifest.yaml for extension '{extension_name}'")
        except Exception as e:
            logger.error(f"Failed to generate manifest.yaml: {e}")

    def _save_env_vars(self, extension_dir: Path, env_vars: dict) -> None:
        """Save environment variables to .env file in extension directory."""
        try:
            env_file = extension_dir / ".env"
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("# Auto-generated environment variables\n")
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            logger.info(f"Saved environment variables to {env_file}")
        except Exception as e:
            logger.error(f"Failed to save environment variables: {e}")

    def _check_required_config(self, extension_dir: Path, extension_name: str) -> dict | None:
        """Check if extension requires configuration and return config params.

        Returns:
            Dict with config page params or None if no config needed.
        """
        try:
            # Read manifest.yaml
            manifest_path = extension_dir / "manifest.yaml"
            if not manifest_path.exists():
                return None

            import yaml
            manifest = yaml.safe_load(manifest_path.read_text()) or {}

            # Get environment config
            config = manifest.get("config", {})
            env_config = config.get("environment", {})
            fields = env_config.get("fields", [])

            if not fields:
                return None

            # Check which required fields are missing
            env_file = extension_dir / ".env"
            existing_vars = {}
            if env_file.exists():
                content = env_file.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        existing_vars[key.strip()] = value.strip()

            missing_fields = []
            for field in fields:
                field_name = field.get("name")
                is_required = field.get("required", False)

                if field_name and is_required and not existing_vars.get(field_name):
                    missing_fields.append(field)

            if not missing_fields:
                return None

            # Build config page params
            config_page = env_config.get("config_page", {})
            return {
                "title": config_page.get("title", f"{extension_name} 配置"),
                "description": config_page.get(
                    "description",
                    f"请配置 {extension_name} 扩展所需的以下信息"
                ),
                "fields": missing_fields,
                "expires_in_minutes": config_page.get("expires_in_minutes", 30),
                "extension": extension_name
            }

        except Exception as e:
            logger.warning(f"Failed to check required config for '{extension_name}': {e}")
            return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ExtensionUninstallHandler:
    """Handle extension uninstallation requests."""

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Remove an installed extension."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_id = message.data.get("extension_id")
            extension_name = message.data.get("name")

            if not extension_id and not extension_name:
                await self._send_error(websocket, message.request_id, "Extension ID or name is required")
                return

            if not extension_id:
                await self._send_error(websocket, message.request_id, "Extension ID is required")
                return

            # Find extension directory by .extension_id file
            extensions_path = get_extensions_path()
            extension_dir = self._find_extension_dir_by_id(extensions_path, extension_id)

            if not extension_dir or not extension_dir.exists():
                await self._send_error(websocket, message.request_id, f"Extension '{extension_id}' not found")
                return

            # Get extension name for response
            actual_name = extension_dir.name
            manifest_file = extension_dir / "manifest.yaml"
            if manifest_file.exists():
                try:
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = yaml.safe_load(f) or {}
                        actual_name = manifest.get("name", extension_dir.name)
                except Exception:
                    pass

            # Remove the extension directory
            shutil.rmtree(extension_dir)

            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_UNINSTALLED,
                request_id=message.request_id,
                data={"success": True, "extension_id": extension_id or extension_dir.name, "name": actual_name}
            ))
            logger.info(f"Extension '{actual_name}' uninstalled successfully")

        except Exception as e:
            logger.error(f"Failed to uninstall extension: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to uninstall extension: {e}")

    def _find_extension_dir_by_id(self, extensions_path: Path, extension_id: str) -> Path | None:
        """Find extension directory by reading .extension_id files."""
        for ext_dir in extensions_path.iterdir():
            if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                ext_id_file = ext_dir / ".extension_id"
                if ext_id_file.exists():
                    try:
                        stored_id = ext_id_file.read_text(encoding='utf-8').strip()
                        if stored_id == extension_id:
                            return ext_dir
                    except Exception:
                        continue
        return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ExtensionRunHandler:
    """Handle extension run requests - sends extension content to agent."""

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Run an extension by sending its documentation to the agent."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_id = message.data.get("extension_id") or message.data.get("name")
            user_query = message.data.get("query", "")
            request_id = message.request_id or str(uuid.uuid4())

            if not extension_id:
                await self._send_error(websocket, request_id, "Extension ID is required")
                return

            # Find the extension by .extension_id file
            user_ext_dir = self._find_extension_dir_by_id(get_extensions_path(), extension_id)
            if not user_ext_dir:
                await self._send_error(websocket, request_id, f"Extension '{extension_id}' not found")
                return

            ext_content = self._load_extension_content(user_ext_dir)
            if not ext_content:
                await self._send_error(websocket, request_id, f"Extension '{extension_id}' has no content")
                return

            # Get extension name from manifest or directory
            manifest_file = user_ext_dir / "manifest.yaml"
            extension_name = user_ext_dir.name
            if manifest_file.exists():
                try:
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = yaml.safe_load(f) or {}
                        extension_name = manifest.get("name", user_ext_dir.name)
                except Exception:
                    pass

            # Send running status
            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_RUNNING,
                request_id=request_id,
                data={"extension_id": extension_id, "name": extension_name}
            ))

            # Create message for agent with extension context
            content = f"""Please use the following extension to help with the user's request:

{ext_content}

User request: {user_query}"""

            # Forward to message bus
            msg = InboundMessage(
                channel="desktop",
                sender_id="user",
                chat_id="desktop_session",
                content=content,
                metadata={
                    "request_id": request_id,
                    "extension_name": extension_name,
                    "websocket_client": id(websocket)
                }
            )

            await self.bus.publish_inbound(msg)

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "running", "extension_id": extension_name, "name": extension_name}
            ))

        except Exception as e:
            logger.error(f"Failed to run extension: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to run extension: {e}")

    def _load_extension_content(self, ext_dir: Path) -> str | None:
        """Load extension content from directory."""
        # Try SKILL.md first
        skill_file = ext_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")

        # Fallback to manifest.yaml description
        manifest_file = ext_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = yaml.safe_load(f) or {}
                    desc = manifest.get("description", "")
                    if desc:
                        return f"# {manifest.get('name', ext_dir.name)}\n\n{desc}"
            except Exception:
                pass

        return None

    def _find_extension_dir_by_id(self, extensions_path: Path, extension_id: str) -> Path | None:
        """Find extension directory by reading .extension_id files."""
        for ext_dir in extensions_path.iterdir():
            if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                ext_id_file = ext_dir / ".extension_id"
                if ext_id_file.exists():
                    try:
                        stored_id = ext_id_file.read_text(encoding='utf-8').strip()
                        if stored_id == extension_id:
                            return ext_dir
                    except Exception:
                        continue
        return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SkillGetInstalledHandler:
    """Handle get installed extensions requests.

    Note: Kept as 'SkillGetInstalledHandler' for backward compatibility.
    """

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of installed extensions."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extensions = []

            if get_extensions_path().exists():
                for ext_dir in get_extensions_path().iterdir():
                    if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                        # Check for manifest.yaml first, then SKILL.md
                        manifest_file = ext_dir / "manifest.yaml"
                        skill_file = ext_dir / "SKILL.md"

                        if manifest_file.exists() or skill_file.exists():
                            # Parse metadata from manifest.yaml or SKILL.md
                            metadata = self._parse_extension_metadata(ext_dir)
                            extensions.append({
                                "name": ext_dir.name,
                                "path": str(ext_dir),
                                "metadata": metadata,
                                "installed_at": ext_dir.stat().st_mtime
                            })

            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_LIST,
                request_id=message.request_id,
                data={"skills": extensions, "extensions": extensions}  # Both keys for compatibility
            ))

        except Exception as e:
            logger.error(f"Failed to get installed extensions: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get installed extensions: {e}")

    def _parse_extension_metadata(self, ext_dir: Path) -> dict:
        """Parse metadata from manifest.yaml or SKILL.md."""
        # Try manifest.yaml first
        manifest_file = ext_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to parse manifest.yaml from {ext_dir}: {e}")

        # Fallback to SKILL.md
        skill_file = ext_dir / "SKILL.md"
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                if content.startswith("---"):
                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                    if match:
                        metadata = {}
                        for line in match.group(1).split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip().strip('"\'')
                        return metadata
            except Exception as e:
                logger.warning(f"Failed to parse SKILL.md from {ext_dir}: {e}")

        return {}

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SkillRemoveHandler:
    """Handle extension removal requests.

    Note: Kept as 'SkillRemoveHandler' for backward compatibility.
    """

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Remove an installed extension."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            # Support both 'name' and 'skill_id'/'extension_id' for backward compatibility
            extension_name = message.data.get("name") or message.data.get("skill_id") or message.data.get("extension_id")
            if not extension_name:
                await self._send_error(websocket, message.request_id, "Extension name is required")
                return

            extension_dir = get_extensions_path() / extension_name
            if not extension_dir.exists():
                await self._send_error(websocket, message.request_id, f"Extension '{extension_name}' not found")
                return

            # Remove the extension directory
            shutil.rmtree(extension_dir)

            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_REMOVED,
                request_id=message.request_id,
                data={"success": True, "name": extension_name}
            ))
            logger.info(f"Extension '{extension_name}' removed successfully")

        except Exception as e:
            logger.error(f"Failed to remove extension: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to remove extension: {e}")

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class SkillRunHandler:
    """Handle extension run requests - sends extension content to agent.

    Note: Kept as 'SkillRunHandler' for backward compatibility.
    """

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Run an extension by sending its documentation to the agent."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_name = message.data.get("name")
            user_query = message.data.get("query", "")
            request_id = message.request_id or str(uuid.uuid4())

            if not extension_name:
                await self._send_error(websocket, request_id, "Extension name is required")
                return

            # Find the extension
            ext_content = None

            # Check user installed extensions first
            user_ext_dir = get_extensions_path() / extension_name
            if user_ext_dir.exists():
                ext_content = self._load_extension_content(user_ext_dir)
            else:
                # Check built-in extensions
                builtin_dir = Path(__file__).parent.parent / "extensions" / "builtin" / extension_name
                if builtin_dir.exists():
                    ext_content = self._load_extension_content(builtin_dir)

            if not ext_content:
                await self._send_error(websocket, request_id, f"Extension '{extension_name}' not found")
                return

            # Send running status
            await self._send_response(websocket, WSMessage(
                type=MessageType.SKILL_RUNNING,
                request_id=request_id,
                data={"skill_name": extension_name, "extension_name": extension_name}
            ))

            # Create message for agent with extension context
            content = f"""Please use the following skill/extension to help with the user's request:

{ext_content}

User request: {user_query}"""

            # Forward to message bus
            msg = InboundMessage(
                channel="desktop",
                sender_id="user",
                chat_id="desktop_session",
                content=content,
                metadata={
                    "request_id": request_id,
                    "skill_name": extension_name,
                    "extension_name": extension_name,
                    "websocket_client": id(websocket)
                }
            )

            await self.bus.publish_inbound(msg)

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "running", "skill_name": extension_name, "extension_name": extension_name}
            ))

        except Exception as e:
            logger.error(f"Failed to run extension: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to run extension: {e}")

    def _load_extension_content(self, ext_dir: Path) -> str | None:
        """Load extension content from directory."""
        # Try SKILL.md first
        skill_file = ext_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")

        # Fallback to manifest.yaml description
        manifest_file = ext_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = yaml.safe_load(f) or {}
                    desc = manifest.get("description", "")
                    if desc:
                        return f"# {manifest.get('name', ext_dir.name)}\n\n{desc}"
            except Exception:
                pass

        return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


# =============================================================================
# Plugin Handlers (for backward compatibility with Desktop client)
# These handlers work with workspace/extensions/ directory (plugins are extensions)
# =============================================================================


class PluginInstallHandler:
    """Handle plugin installation requests from Plugin Market API.

    Note: This mirrors SkillInstallHandler but works with plugins directory.
    """

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Install a plugin from Plugin Market API."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            plugin_id = message.data.get("plugin_id") or message.data.get("skill_id")
            plugin_name = message.data.get("name")
            request_id = message.request_id or str(uuid.uuid4())

            if not plugin_id:
                await self._send_error(websocket, request_id, "Plugin ID is required")
                return

            # Send installing status
            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_INSTALLING,
                request_id=request_id,
                data={"plugin_id": plugin_id, "name": plugin_name}
            ))

            # Ensure extensions directory exists (plugins are now extensions)
            get_extensions_path().mkdir(parents=True, exist_ok=True)

            # Execute installation in background
            asyncio.create_task(self._execute_install(
                websocket, request_id, plugin_id, plugin_name
            ))

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "installing", "plugin_id": plugin_id}
            ))

        except Exception as e:
            logger.error(f"Failed to start plugin installation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to start installation: {e}")

    async def _execute_install(self, websocket: WebSocket, request_id: str,
                               plugin_id: str, plugin_name: str | None):
        """Execute the installation by downloading from API and extracting."""
        temp_zip_path = None
        try:
            # Step 1: Get plugin details from API
            plugin_detail = await self._fetch_plugin_detail(plugin_id)
            if not plugin_detail:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.PLUGIN_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "plugin_id": plugin_id,
                        "error": f"Plugin '{plugin_id}' not found in market"
                    }
                ))
                return

            # Use provided name or fallback
            if not plugin_name:
                plugin_name = plugin_detail.get("name", plugin_id)

            # Sanitize plugin name
            plugin_name = self._sanitize_plugin_name(plugin_name)

            # Step 2: Download ZIP (use unified /api/extensions endpoint)
            download_url = f"{EXTENSION_MARKET_API_BASE}/api/extensions/{plugin_id}/download"
            temp_zip_path = get_extensions_path() / f"{plugin_id}_{uuid.uuid4()}.zip"

            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_INSTALLING,
                request_id=request_id,
                data={"plugin_id": plugin_id, "name": plugin_name, "status": "downloading"}
            ))

            download_success = await self._download_zip(download_url, temp_zip_path)
            if not download_success:
                await self._send_response(websocket, WSMessage(
                    type=MessageType.PLUGIN_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "plugin_id": plugin_id,
                        "name": plugin_name,
                        "error": "Failed to download plugin ZIP file"
                    }
                ))
                return

            # Step 3: Extract
            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_INSTALLING,
                request_id=request_id,
                data={"plugin_id": plugin_id, "name": plugin_name, "status": "extracting"}
            ))

            plugin_dir = get_extensions_path() / plugin_name

            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(plugin_dir)

            # Step 4: Verify (check for SKILL.md and handler.py)
            skill_md_path = plugin_dir / "SKILL.md"
            handler_path = plugin_dir / "handler.py"

            if not skill_md_path.exists() or not handler_path.exists():
                # Try nested structure
                for subdir in plugin_dir.iterdir():
                    if subdir.is_dir():
                        nested_skill = subdir / "SKILL.md"
                        nested_handler = subdir / "handler.py"
                        if nested_skill.exists() and nested_handler.exists():
                            for item in subdir.iterdir():
                                shutil.move(str(item), str(plugin_dir / item.name))
                            shutil.rmtree(subdir)
                            break

            # Final verification
            if not skill_md_path.exists() or not handler_path.exists():
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                await self._send_response(websocket, WSMessage(
                    type=MessageType.PLUGIN_INSTALL_ERROR,
                    request_id=request_id,
                    data={
                        "success": False,
                        "plugin_id": plugin_id,
                        "name": plugin_name,
                        "error": "Invalid plugin package: SKILL.md or handler.py not found"
                    }
                ))
                return

            # Step 5: Generate manifest.yaml
            manifest_path = plugin_dir / "manifest.yaml"
            if not manifest_path.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.PLUGIN_INSTALLING,
                    request_id=request_id,
                    data={"plugin_id": plugin_id, "name": plugin_name, "status": "generating_manifest"}
                ))
                self._generate_manifest_from_skill(plugin_dir, plugin_name, skill_md_path)

            # Step 6: Install dependencies
            requirements_file = plugin_dir / "requirements.txt"
            if requirements_file.exists():
                await self._send_response(websocket, WSMessage(
                    type=MessageType.PLUGIN_INSTALLING,
                    request_id=request_id,
                    data={"plugin_id": plugin_id, "name": plugin_name, "status": "installing_deps"}
                ))
                from backend.extensions.plugin_dependency import DependencyManager
                dep_manager = DependencyManager(plugin_dir)
                deps_success = await dep_manager.install(requirements_file)
                if not deps_success:
                    logger.warning(f"Failed to install dependencies for plugin '{plugin_name}'")
                    # Continue anyway, plugin might work without deps

            # Success
            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_INSTALLED,
                request_id=request_id,
                data={
                    "success": True,
                    "plugin_id": plugin_id,
                    "name": plugin_name,
                    "path": str(plugin_dir)
                }
            ))
            logger.info(f"Plugin '{plugin_name}' (ID: {plugin_id}) installed successfully")

        except Exception as e:
            logger.error(f"Exception during plugin installation: {e}")
            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_INSTALL_ERROR,
                request_id=request_id,
                data={
                    "success": False,
                    "plugin_id": plugin_id,
                    "name": plugin_name,
                    "error": str(e)
                }
            ))
        finally:
            if temp_zip_path and temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove temp ZIP: {e}")

    async def _fetch_plugin_detail(self, plugin_id: str) -> dict | None:
        """Fetch plugin details from Market API."""
        try:
            url = f"{EXTENSION_MARKET_API_BASE}/api/plugins/{plugin_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching plugin detail: {e}")
            return None

    async def _download_zip(self, url: str, dest_path: Path) -> bool:
        """Download ZIP file."""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", url) as response:
                    if response.status_code == 200:
                        with open(dest_path, 'wb') as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error downloading ZIP: {e}")
            return False

    def _sanitize_plugin_name(self, name: str) -> str:
        """Sanitize plugin name for directory."""
        unsafe = '<>:"/\\|?*'
        for char in unsafe:
            name = name.replace(char, "_")
        name = name.strip().strip(".")
        if not name:
            name = "unnamed_plugin"
        return name

    def _generate_manifest_from_skill(self, plugin_dir: Path, plugin_name: str, skill_md_path: Path) -> None:
        """Generate manifest.yaml from SKILL.md."""
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            manifest = {
                "name": plugin_name,
                "description": "",
                "version": "1.0.0",
                "author": "unknown",
                "type": "plugin",
                "capabilities": [],
                "plugin": {
                    "handler": f"workspace.plugins.{plugin_name}.handler.Handler"
                }
            }

            if content.startswith("---"):
                match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if match:
                    try:
                        frontmatter = yaml.safe_load(match.group(1)) or {}
                        if "name" in frontmatter:
                            manifest["name"] = frontmatter["name"]
                        if "description" in frontmatter:
                            desc = frontmatter["description"]
                            if isinstance(desc, str):
                                manifest["description"] = " ".join(desc.split())
                        octopus_meta = frontmatter.get("octopus", {})
                        if octopus_meta:
                            if "capabilities" in octopus_meta:
                                manifest["capabilities"] = octopus_meta["capabilities"]
                    except yaml.YAMLError:
                        pass

            manifest_path = plugin_dir / "manifest.yaml"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            logger.info(f"Generated manifest.yaml for plugin '{plugin_name}'")
        except Exception as e:
            logger.error(f"Failed to generate manifest.yaml: {e}")

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class PluginGetInstalledHandler:
    """Handle get installed plugins requests."""

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return list of installed plugins."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            plugins = []

            # Scan extensions directory for plugin-type extensions
            if get_extensions_path().exists():
                for plugin_dir in get_extensions_path().iterdir():
                    if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                        skill_file = plugin_dir / "SKILL.md"
                        manifest_file = plugin_dir / "manifest.yaml"

                        if skill_file.exists() or manifest_file.exists():
                            metadata = self._parse_plugin_metadata(plugin_dir)
                            # Only include plugins (type: plugin or hybrid)
                            ext_type = metadata.get("type", "")
                            if ext_type in ("plugin", "hybrid"):
                                plugins.append({
                                    "name": plugin_dir.name,
                                    "path": str(plugin_dir),
                                    "metadata": metadata,
                                    "installed_at": plugin_dir.stat().st_mtime
                                })

            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_LIST,
                request_id=message.request_id,
                data={"plugins": plugins}
            ))

        except Exception as e:
            logger.error(f"Failed to get installed plugins: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    def _parse_plugin_metadata(self, plugin_dir: Path) -> dict:
        """Parse metadata from manifest.yaml or SKILL.md."""
        manifest_file = plugin_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass

        skill_file = plugin_dir / "SKILL.md"
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                if content.startswith("---"):
                    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                    if match:
                        metadata = {}
                        for line in match.group(1).split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip().strip('"\'')
                        return metadata
            except Exception:
                pass

        return {}

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class PluginRemoveHandler:
    """Handle plugin removal requests."""

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Remove an installed plugin."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            # Support both 'name' and 'plugin_id' for backward compatibility
            plugin_name = message.data.get("name") or message.data.get("plugin_id")
            if not plugin_name:
                await self._send_error(websocket, message.request_id, "Plugin name is required")
                return

            # Check both plugins/ and extensions/ directories (backward compatibility)
            plugin_dir = get_plugins_path() / plugin_name
            ext_dir = get_extensions_path() / plugin_name

            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            elif ext_dir.exists():
                shutil.rmtree(ext_dir)
            else:
                await self._send_error(websocket, message.request_id, f"Plugin '{plugin_name}' not found")
                return

            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_UNINSTALLED,
                request_id=message.request_id,
                data={"success": True, "name": plugin_name}
            ))
            logger.info(f"Plugin '{plugin_name}' removed successfully")

        except Exception as e:
            logger.error(f"Failed to remove plugin: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ExtensionConfigHandler:
    """Handle extension configuration requests (save environment variables)."""

    def __init__(self, bus: "MessageBus"):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save extension configuration (environment variables)."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            extension_id = message.data.get("extension_id")
            extension_name = message.data.get("name")
            env_vars = message.data.get("env_vars", {})
            request_id = message.request_id or str(uuid.uuid4())

            if not extension_id:
                await self._send_error(websocket, request_id, "Extension ID is required")
                return

            # Find extension directory by .extension_id file
            extensions_path = get_extensions_path()
            extension_dir = self._find_extension_dir_by_id(extensions_path, extension_id)

            if not extension_dir or not extension_dir.exists():
                await self._send_error(websocket, request_id, f"Extension '{extension_id}' not found")
                return

            # Get extension name from manifest
            extension_name = extension_dir.name
            manifest_file = extension_dir / "manifest.yaml"
            if manifest_file.exists():
                try:
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = yaml.safe_load(f) or {}
                        extension_name = manifest.get("name", extension_dir.name)
                except Exception:
                    pass

            # Save environment variables
            if env_vars:
                self._save_env_vars(extension_dir, env_vars)

            await self._send_response(websocket, WSMessage(
                type=MessageType.EXTENSION_CONFIG_SAVED,
                request_id=request_id,
                data={
                    "success": True,
                    "extension_id": extension_id,
                    "name": extension_name
                }
            ))
            logger.info(f"Configuration saved for extension '{extension_id}'")

        except Exception as e:
            logger.error(f"Failed to save extension config: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    def _save_env_vars(self, extension_dir: Path, env_vars: dict) -> None:
        """Save environment variables to .env file in extension directory."""
        try:
            env_file = extension_dir / ".env"
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("# Auto-generated environment variables\n")
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            logger.info(f"Saved environment variables to {env_file}")
        except Exception as e:
            logger.error(f"Failed to save environment variables: {e}")
            raise

    def _find_extension_dir_by_id(self, extensions_path: Path, extension_id: str) -> Path | None:
        """Find extension directory by reading .extension_id files."""
        for ext_dir in extensions_path.iterdir():
            if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                ext_id_file = ext_dir / ".extension_id"
                if ext_id_file.exists():
                    try:
                        stored_id = ext_id_file.read_text(encoding='utf-8').strip()
                        if stored_id == extension_id:
                            return ext_dir
                    except Exception:
                        continue
        return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class PluginRunHandler:
    """Handle plugin run requests - sends plugin content to agent."""

    def __init__(self, bus: "MessageBus", pending_responses: dict[str, asyncio.Queue]):
        self.bus = bus
        self.pending_responses = pending_responses

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Run a plugin by sending its documentation to the agent."""
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                schema.model_validate(message.data)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        try:
            plugin_name = message.data.get("name")
            user_query = message.data.get("query", "")
            request_id = message.request_id or str(uuid.uuid4())

            if not plugin_name:
                await self._send_error(websocket, request_id, "Plugin name is required")
                return

            # Find plugin in extensions directory
            plugin_content = None
            plugin_dir = get_extensions_path() / plugin_name

            if plugin_dir.exists():
                plugin_content = self._load_plugin_content(plugin_dir)

            if not plugin_content:
                await self._send_error(websocket, request_id, f"Plugin '{plugin_name}' not found")
                return

            # Send running status
            await self._send_response(websocket, WSMessage(
                type=MessageType.PLUGIN_RUNNING,
                request_id=request_id,
                data={"plugin_name": plugin_name}
            ))

            # Create message for agent
            content = f"""Please use the following plugin to help with the user's request:

{plugin_content}

User request: {user_query}"""

            # Forward to message bus
            msg = InboundMessage(
                channel="desktop",
                sender_id="user",
                chat_id="desktop_session",
                content=content,
                metadata={
                    "request_id": request_id,
                    "plugin_name": plugin_name,
                    "websocket_client": id(websocket)
                }
            )

            await self.bus.publish_inbound(msg)

            # Send acknowledgment
            await self._send_response(websocket, WSMessage(
                type=MessageType.ACK,
                request_id=request_id,
                data={"status": "running", "plugin_name": plugin_name}
            ))

        except Exception as e:
            logger.error(f"Failed to run plugin: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    def _load_plugin_content(self, plugin_dir: Path) -> str | None:
        """Load plugin content from directory."""
        skill_file = plugin_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")

        manifest_file = plugin_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = yaml.safe_load(f) or {}
                    desc = manifest.get("description", "")
                    if desc:
                        return f"# {manifest.get('name', plugin_dir.name)}\n\n{desc}"
            except Exception:
                pass

        return None

    async def _send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self._send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
