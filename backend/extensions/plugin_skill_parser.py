"""Parser for SKILL.md files - similar to channel skills."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class ActionDef:
    """Action definition parsed from SKILL.md."""
    name: str
    description: str
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    returns: str = ""


@dataclass
class PluginSkill:
    """Parsed plugin skill from SKILL.md."""
    name: str
    description: str
    always: bool = False
    actions: list[ActionDef] = field(default_factory=list)
    parameters: dict[str, dict] = field(default_factory=dict)
    examples: list[dict] = field(default_factory=list)
    raw_content: str = ""
    
    # octopus configuration
    plugin_name: str = ""
    capabilities: list[str] = field(default_factory=list)


class SkillParser:
    """Parse SKILL.md files to extract plugin capabilities."""
    
    @classmethod
    def parse(cls, skill_path: Path) -> PluginSkill | None:
        """Parse a SKILL.md file.
        
        Args:
            skill_path: Path to SKILL.md file
            
        Returns:
            Parsed PluginSkill or None if parsing fails
        """
        if not skill_path.exists():
            return None
        
        content = skill_path.read_text(encoding="utf-8")
        
        # Parse frontmatter
        frontmatter, body = cls._extract_frontmatter(content)
        
        # Parse actions table
        actions = cls._parse_actions(body)
        
        # Parse parameter reference
        parameters = cls._parse_parameters(body)
        
        # Parse examples
        examples = cls._parse_examples(body)
        
        # Extract octopus config
        octopus_config = frontmatter.get("octopus", {})
        
        return PluginSkill(
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", "").strip(),
            always=frontmatter.get("always", False),
            actions=actions,
            parameters=parameters,
            examples=examples,
            raw_content=content,
            plugin_name=octopus_config.get("plugin", ""),
            capabilities=octopus_config.get("capabilities", []),
        )
    
    @classmethod
    def _extract_frontmatter(cls, content: str) -> tuple[dict, str]:
        """Extract YAML frontmatter from markdown content."""
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        
        if match and YAML_AVAILABLE:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                return frontmatter or {}, match.group(2)
            except yaml.YAMLError:
                pass
        
        return {}, content
    
    @classmethod
    def _parse_actions(cls, body: str) -> list[ActionDef]:
        """Parse Available Actions table from markdown."""
        actions = []
        
        # Find Available Actions section
        pattern = r'## Available Actions.*?\n(.*?)(?:\n## |\n# |\Z)'
        match = re.search(pattern, body, re.DOTALL)
        if not match:
            return actions
        
        table_content = match.group(1)
        lines = table_content.strip().split('\n')
        
        # Skip header and separator lines
        for line in lines[2:]:
            if '|' not in line:
                continue
            
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 4:
                # Parse required params
                required = [p.strip() for p in cells[2].split(',') if p.strip()]
                # Filter out common params that are always required
                required = [p for p in required if p not in ['action', 'channel', 'plugin']]
                
                # Parse optional params
                optional = [p.strip() for p in cells[3].split(',') if p.strip()]
                
                actions.append(ActionDef(
                    name=cells[0].strip().strip('`'),
                    description=cells[1],
                    required_params=required,
                    optional_params=optional,
                ))
        
        return actions
    
    @classmethod
    def _parse_parameters(cls, body: str) -> dict[str, dict]:
        """Parse Parameter Reference table from markdown."""
        params = {}
        
        pattern = r'## Parameter Reference.*?\n(.*?)(?:\n## |\n# |\Z)'
        match = re.search(pattern, body, re.DOTALL)
        if not match:
            return params
        
        table_content = match.group(1)
        lines = table_content.strip().split('\n')
        
        for line in lines[2:]:
            if '|' not in line:
                continue
            
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 2:
                param_name = cells[0].strip().strip('`')
                params[param_name] = {
                    "description": cells[1],
                    "example": cells[2].strip('`') if len(cells) > 2 else "",
                }
        
        return params
    
    @classmethod
    def _parse_examples(cls, body: str) -> list[dict]:
        """Parse Usage Examples from markdown."""
        examples = []
        
        # Find json code blocks after ### headers
        pattern = r'### (.*?)\n```json\s*\n(.*?)\n```'
        matches = re.findall(pattern, body, re.DOTALL)
        
        for title, json_str in matches:
            try:
                # Use yaml.safe_load as it can parse JSON too
                if YAML_AVAILABLE:
                    data = yaml.safe_load(json_str)
                else:
                    import json
                    data = json.loads(json_str)
                
                examples.append({
                    "title": title.strip(),
                    "request": data,
                })
            except Exception:
                # Skip invalid JSON
                pass
        
        return examples
