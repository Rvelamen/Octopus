"""Memory system for persistent agent memory."""

import fcntl
import os
import re
import tempfile
from pathlib import Path

from backend.utils.helpers import ensure_dir


ENTRY_DELIMITER = "\n§\n"
LIMITS = {
    "memory": 3000,
    "user": 1500,
}
TARGET_NAMES = {
    "memory": "MEMORY (your personal notes)",
    "user": "USER PROFILE (who the user is)",
}


def _scan_memory_content(content: str) -> str | None:
    """Lightweight security scan for memory content. Returns error string if blocked, else None."""
    # Invisible Unicode characters
    invisible_chars = [
        "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
        *[chr(cp) for cp in range(0x202A, 0x202F)],
    ]
    for char in invisible_chars:
        if char in content:
            return f"Blocked invisible Unicode character U+{ord(char):04X} in memory content."

    # Prompt injection patterns (case-insensitive)
    injection_patterns = [
        r"ignore\s+(previous|all|above|prior)\s+instructions",
        r"you\s+are\s+now\s+",
        r"do\s+not\s+tell\s+the\s+user",
        r"system\s+prompt\s+override",
        r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)",
        r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions|limits|rules)",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return "Blocked prompt injection pattern in memory content."

    # Exfiltration patterns
    exfil_patterns = [
        r"curl\s+.*\$?(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
        r"wget\s+.*\$?(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
        r"cat\s+.*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)",
    ]
    for pattern in exfil_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return "Blocked potential exfiltration pattern in memory content."

    # Persistence patterns
    persistence_patterns = [
        r"authorized_keys",
        r"\$HOME/\.ssh",
        r"~/\.ssh",
        r"\$HOME/\.hermes/\.env",
        r"~/\.hermes/\.env",
    ]
    for pattern in persistence_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return "Blocked persistence pattern in memory content."

    return None


class MemoryStore:
    """
    Bounded, entry-based curated memory store.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self._entries = {
            "memory": [],
            "user": [],
        }

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #

    def _path_for(self, target: str) -> Path:
        if target == "memory":
            return self.memory_dir / "MEMORY.md"
        if target == "user":
            return self.memory_dir / "USER_PROFILE.md"
        raise ValueError(f"Unknown target: {target}")

    def _char_limit(self, target: str) -> int:
        return LIMITS[target]

    def _entries_for(self, target: str) -> list[str]:
        return self._entries[target]

    def _set_entries(self, target: str, entries: list[str]) -> None:
        self._entries[target] = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        return sum(len(e) for e in entries) + len(ENTRY_DELIMITER) * (len(entries) - 1)

    def _usage_str(self, target: str) -> str:
        limit = self._char_limit(target)
        count = self._char_count(target)
        pct = round(count / limit * 100) if limit else 0
        return f"{pct}% — {count:,}/{limit:,} chars"

    @staticmethod
    def _usage_str_for_target(target: str, entries: list[str]) -> str:
        limit = LIMITS[target]
        if not entries:
            count = 0
        else:
            count = sum(len(e) for e in entries) + len(ENTRY_DELIMITER) * (len(entries) - 1)
        pct = round(count / limit * 100) if limit else 0
        return f"{pct}% — {count:,}/{limit:,} chars"

    def _read_file(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return []
        raw = text.split(ENTRY_DELIMITER)
        seen = set()
        entries = []
        for entry in raw:
            e = entry.strip()
            if e and e not in seen:
                seen.add(e)
                entries.append(e)
        return entries

    def _write_file(self, path: Path, entries: list[str]) -> None:
        text = ENTRY_DELIMITER.join(entries) if entries else ""
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def load_from_disk(self) -> None:
        """Read both stores from disk and deduplicate."""
        for target in ("memory", "user"):
            path = self._path_for(target)
            entries = self._read_file(path)
            self._set_entries(target, entries)

    def _format_snapshot(self, target: str, entries: list[str]) -> str | None:
        if not entries:
            return None
        header = (
            f"{'═' * 46}\n"
            f"{TARGET_NAMES[target]} [{self._usage_str_for_target(target, entries)}]\n"
            f"{'═' * 46}"
        )
        body = ENTRY_DELIMITER.join(entries)
        return f"{header}\n{body}"

    def save_to_disk(self, target: str) -> None:
        """Persist entries for the given target atomically."""
        path = self._path_for(target)
        self._write_file(path, self._entries_for(target))

    def format_for_system_prompt(self, target: str) -> str | None:
        """Read live from disk and return formatted memory context."""
        path = self._path_for(target)
        entries = self._read_file(path)
        return self._format_snapshot(target, entries)

    def add(self, target: str, content: str) -> dict:
        scan = _scan_memory_content(content)
        if scan:
            return {
                "success": False,
                "target": target,
                "error": scan,
                "current_entries": self._entries_for(target),
                "entries": self._entries_for(target),
                "usage": self._usage_str(target),
                "entry_count": len(self._entries_for(target)),
            }

        path = self._path_for(target)
        lock_path = path.with_suffix(path.suffix + ".lock")

        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                entries = self._read_file(path)
                self._set_entries(target, entries)

                stripped = content.strip()
                if stripped in entries:
                    return {
                        "success": True,
                        "target": target,
                        "message": "Entry already exists.",
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                new_entries = entries + [stripped]
                new_count = (
                    sum(len(e) for e in new_entries)
                    + len(ENTRY_DELIMITER) * (len(new_entries) - 1)
                )
                limit = self._char_limit(target)
                if new_count > limit:
                    return {
                        "success": False,
                        "target": target,
                        "error": (
                            f"Character limit exceeded ({new_count:,}/{limit:,}). "
                            "Consolidate or remove entries first."
                        ),
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                self._write_file(path, new_entries)
                self._set_entries(target, new_entries)

                return {
                    "success": True,
                    "target": target,
                    "entries": new_entries,
                    "usage": self._usage_str(target),
                    "entry_count": len(new_entries),
                }
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def replace(self, target: str, old_text: str, new_content: str) -> dict:
        scan = _scan_memory_content(new_content)
        if scan:
            return {
                "success": False,
                "target": target,
                "error": scan,
                "current_entries": self._entries_for(target),
                "entries": self._entries_for(target),
                "usage": self._usage_str(target),
                "entry_count": len(self._entries_for(target)),
            }

        path = self._path_for(target)
        lock_path = path.with_suffix(path.suffix + ".lock")

        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                entries = self._read_file(path)
                self._set_entries(target, entries)

                matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

                if not matches:
                    return {
                        "success": False,
                        "target": target,
                        "error": f"No entry found containing '{old_text}'.",
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                if len(matches) > 1:
                    previews = [
                        f"- {e[:80]}..." if len(e) > 80 else f"- {e}"
                        for _, e in matches
                    ]
                    return {
                        "success": False,
                        "target": target,
                        "error": (
                            f"Multiple entries match '{old_text}'. Be more specific.\n"
                            + "\n".join(previews)
                        ),
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                idx, _ = matches[0]
                new_entries = entries.copy()
                new_entries[idx] = new_content.strip()

                new_count = (
                    sum(len(e) for e in new_entries)
                    + len(ENTRY_DELIMITER) * (len(new_entries) - 1)
                )
                limit = self._char_limit(target)
                if new_count > limit:
                    return {
                        "success": False,
                        "target": target,
                        "error": (
                            f"Character limit exceeded ({new_count:,}/{limit:,}). "
                            "Consolidate or remove entries first."
                        ),
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                self._write_file(path, new_entries)
                self._set_entries(target, new_entries)

                return {
                    "success": True,
                    "target": target,
                    "entries": new_entries,
                    "usage": self._usage_str(target),
                    "entry_count": len(new_entries),
                }
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def remove(self, target: str, old_text: str) -> dict:
        path = self._path_for(target)
        lock_path = path.with_suffix(path.suffix + ".lock")

        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                entries = self._read_file(path)
                self._set_entries(target, entries)

                matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

                if not matches:
                    return {
                        "success": False,
                        "target": target,
                        "error": f"No entry found containing '{old_text}'.",
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                if len(matches) > 1:
                    previews = [
                        f"- {e[:80]}..." if len(e) > 80 else f"- {e}"
                        for _, e in matches
                    ]
                    return {
                        "success": False,
                        "target": target,
                        "error": (
                            f"Multiple entries match '{old_text}'. Be more specific.\n"
                            + "\n".join(previews)
                        ),
                        "current_entries": entries,
                        "entries": entries,
                        "usage": self._usage_str(target),
                        "entry_count": len(entries),
                    }

                idx, _ = matches[0]
                new_entries = entries[:idx] + entries[idx + 1 :]

                self._write_file(path, new_entries)
                self._set_entries(target, new_entries)

                return {
                    "success": True,
                    "target": target,
                    "entries": new_entries,
                    "usage": self._usage_str(target),
                    "entry_count": len(new_entries),
                }
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
