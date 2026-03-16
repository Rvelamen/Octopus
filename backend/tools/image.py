"""Image understanding and generation tools."""

from pathlib import Path
from typing import Any

from backend.tools.base import Tool
from backend.services.image_service import ImageService


class ImageUnderstandTool(Tool):
    """Tool for understanding/analyzing images using vision models."""

    name = "image_understand"
    description = """Analyze and understand image content using AI vision models.
Use this tool when you need to:
- Describe what's in an image
- Extract text from images (OCR)
- Analyze charts, diagrams, or screenshots
- Answer specific questions about image content
- Understand UI elements or code screenshots

The tool supports multiple providers (Kimi, OpenAI, Anthropic) and will use the default configured provider."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the image file. Supported formats: png, jpg, jpeg, webp, gif"
                },
                "question": {
                    "type": "string",
                    "description": "Specific question about the image. If not provided, will return a general description. Examples: 'What does this chart show?', 'Extract all text from this image', 'What UI components are visible?'",
                    "default": ""
                },
                "provider_name": {
                    "type": "string",
                    "description": "Optional provider name to use (e.g., 'kimi', 'openai'). If not specified, uses the default provider.",
                    "default": ""
                }
            },
            "required": ["image_path"]
        }

    def __init__(self, image_service: ImageService | None = None):
        self.image_service = image_service or ImageService()

    async def execute(self, image_path: str, question: str = "", provider_name: str = "") -> str:
        """Execute image understanding.

        Args:
            image_path: Path to the image file
            question: Specific question about the image
            provider_name: Optional specific provider name to use

        Returns:
            Analysis result as string
        """
        try:
            from backend.utils.helpers import get_workspace_path
            workspace = get_workspace_path()

            # Try multiple path resolution strategies
            path = Path(image_path)

            # 1. If absolute path and exists, use it
            if path.is_absolute() and path.exists():
                pass
            # 2. If relative to workspace, use workspace as base
            elif not path.is_absolute():
                path = workspace / image_path
                if not path.exists():
                    # 3. Try images subdirectory
                    path = workspace / "images" / image_path
            # 4. If absolute path but doesn't exist, try relative to workspace
            else:
                # Try removing workspace prefix if present
                try:
                    rel_path = Path(image_path).relative_to(workspace)
                    path = workspace / rel_path
                except ValueError:
                    pass

            if not path.exists():
                # Try to find the file in workspace
                for f in workspace.rglob("*"):
                    if f.is_file() and (f.name == Path(image_path).name or f.name == Path(image_path).stem):
                        path = f
                        break

            if not path.exists():
                return f"Error: Image file not found: {image_path}\nTried paths: {path}"

            # Call image service
            result = await self.image_service.understand_image(
                image_path=str(path),
                question=question,
                provider_name=provider_name or None
            )

            return result

        except Exception as e:
            return f"Error analyzing image: {str(e)}"


class ImageGenerateTool(Tool):
    """Tool for generating images using AI models."""

    name = "image_generate"
    description = """Generate images from text descriptions using AI models like DALL-E.
Use this tool when you need to:
- Create illustrations or artwork
- Generate diagrams or mockups
- Create visual content based on descriptions

The tool supports multiple providers and will use the default configured provider."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of the image you want to generate. Be specific about style, colors, composition, and content."
                },
                "size": {
                    "type": "string",
                    "description": "Image size in format WIDTHxHEIGHT. Common sizes: 1024x1024 (square), 1024x1792 (portrait), 1792x1024 (landscape). Uses provider default if not specified.",
                    "default": ""
                },
                "quality": {
                    "type": "string",
                    "description": "Image quality. Options: 'standard' (faster, cheaper), 'hd' (higher quality). Uses provider default if not specified.",
                    "enum": ["", "standard", "hd"],
                    "default": ""
                },
                "save_path": {
                    "type": "string",
                    "description": "Optional path to save the generated image. If not provided, saves to workspace/generated/ with auto-generated filename.",
                    "default": ""
                },
                "provider_name": {
                    "type": "string",
                    "description": "Optional provider name to use (e.g., 'openai', 'stability'). If not specified, uses the default provider.",
                    "default": ""
                }
            },
            "required": ["prompt"]
        }

    def __init__(self, image_service: ImageService | None = None):
        self.image_service = image_service or ImageService()

    async def execute(self, prompt: str, size: str = "", quality: str = "",
                      save_path: str = "", provider_name: str = "") -> str:
        """Execute image generation.

        Args:
            prompt: Description of the image to generate
            size: Image size (e.g., "1024x1024")
            quality: Image quality ("standard" or "hd")
            save_path: Optional path to save the image
            provider_name: Optional specific provider name to use

        Returns:
            Result message with saved image path
        """
        try:
            # Generate image
            result = await self.image_service.generate_image(
                prompt=prompt,
                size=size or None,
                quality=quality or None,
                provider_name=provider_name or None
            )

            # Determine save path
            if save_path:
                output_path = Path(save_path)
            else:
                # Auto-generate path in workspace/generated/
                from backend.utils.helpers import get_workspace_path
                import uuid
                output_dir = get_workspace_path() / "generated"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"generated_{uuid.uuid4().hex[:8]}.png"

            # Save image
            if "image_data" in result:
                # Raw image data (e.g., from Stability AI)
                output_path.write_bytes(result["image_data"])
            elif "url" in result:
                # URL to download (e.g., from DALL-E)
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(result["url"], timeout=60.0)
                    response.raise_for_status()
                    output_path.write_bytes(response.content)

            # Get relative path for display
            from backend.utils.helpers import get_workspace_path
            try:
                rel_path = output_path.relative_to(get_workspace_path())
            except ValueError:
                rel_path = output_path

            return f"Image generated successfully and saved to: {rel_path}\n\nPrompt used: {result.get('revised_prompt', prompt)}"

        except Exception as e:
            return f"Error generating image: {str(e)}"
