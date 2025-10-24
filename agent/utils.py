import re
from typing import Iterable, Optional, Union


def normalize_label(value: str) -> str:
    """Normalize labels to snake_case-like keys for mapping."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def first_non_empty(values: Iterable[Optional[str]]) -> Optional[str]:
    for val in values:
        if val:
            return val
    return None


RichTextNode = Union[str, dict, list]


def rich_text_to_plain(node: RichTextNode) -> str:
    """Convert Luma's rich-text JSON (ProseMirror style) into plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        parts = [rich_text_to_plain(item) for item in node]
        return "".join(parts)
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "text":
            return node.get("text", "")
        if node_type == "hard_break":
            return "\n"
        content = node.get("content")
        if node_type == "paragraph":
            text = "".join(rich_text_to_plain(part) for part in content or [])
            return text + ("\n" if text and not text.endswith("\n") else "")
        if node_type == "bullet_list":
            lines = []
            for item in content or []:
                item_text = rich_text_to_plain(item).strip()
                if item_text:
                    lines.append(f"- {item_text}")
            return "\n".join(lines) + ("\n" if lines else "")
        if node_type == "ordered_list":
            lines = []
            for idx, item in enumerate(content or [], start=1):
                item_text = rich_text_to_plain(item).strip()
                if item_text:
                    lines.append(f"{idx}. {item_text}")
            return "\n".join(lines) + ("\n" if lines else "")
        if node_type == "list_item":
            return "".join(rich_text_to_plain(part) for part in content or [])
        text = rich_text_to_plain(content)
        return text
    return ""
