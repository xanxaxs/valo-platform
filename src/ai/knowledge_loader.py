"""
Knowledge Loader.

Loads markdown files and imports them into the knowledge base.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_markdown(file_path: Path) -> list[dict]:
    """
    Load and parse a markdown file into sections.
    
    Splits by ## headings (level 2) to create separate documents.
    Preserves hierarchy by including parent headings in context.
    
    Args:
        file_path: Path to markdown file
        
    Returns:
        List of document dicts with:
        - id: Unique identifier
        - title: Section title
        - content: Section content
        - parent: Parent section title (if any)
    """
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return []
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return []
    
    # Split by ## headings
    sections = []
    lines = content.split("\n")
    
    current_section = None
    current_content = []
    current_parent = None
    
    # Track top-level sections (# headings)
    top_level_section = None
    
    for line in lines:
        # Check for # heading (top level)
        if line.startswith("# ") and not line.startswith("##"):
            # Save previous section if exists
            if current_section:
                sections.append({
                    "id": _generate_id(current_section, top_level_section),
                    "title": current_section,
                    "content": "\n".join(current_content).strip(),
                    "parent": top_level_section,
                })
            elif top_level_section and current_content:
                # Save top-level section content if no ## section exists
                sections.append({
                    "id": _generate_id(top_level_section),
                    "title": top_level_section,
                    "content": "\n".join(current_content).strip(),
                    "parent": None,
                })
            
            top_level_section = line[2:].strip()
            current_section = None
            current_content = []
            current_parent = top_level_section
        
        # Check for ## heading (section level)
        elif line.startswith("## "):
            if current_section:
                # Save previous section
                sections.append({
                    "id": _generate_id(current_section, top_level_section),
                    "title": current_section,
                    "content": "\n".join(current_content).strip(),
                    "parent": top_level_section,
                })
            
            current_section = line[3:].strip()
            current_content = []
        
        # Check for ### heading (subsection - include in content)
        elif line.startswith("### "):
            current_content.append(line)
        
        # Regular content
        else:
            if current_section or top_level_section:
                current_content.append(line)
    
    # Save last section
    if current_section:
        sections.append({
            "id": _generate_id(current_section, top_level_section),
            "title": current_section,
            "content": "\n".join(current_content).strip(),
            "parent": top_level_section,
        })
    elif top_level_section and current_content:
        # Save top-level section if no ## section exists
        sections.append({
            "id": _generate_id(top_level_section),
            "title": top_level_section,
            "content": "\n".join(current_content).strip(),
            "parent": None,
        })
    
    # Filter out empty sections
    sections = [s for s in sections if s["content"].strip()]
    
    logger.info(f"Parsed {len(sections)} sections from {file_path}")
    return sections


def _generate_id(title: str, parent: Optional[str] = None) -> str:
    """
    Generate a unique ID from title and parent.
    
    Args:
        title: Section title
        parent: Parent section title
        
    Returns:
        Unique identifier string
    """
    # Clean title for ID
    clean_title = re.sub(r'[^\w\s-]', '', title)
    clean_title = re.sub(r'[-\s]+', '_', clean_title)
    clean_title = clean_title.lower()
    
    if parent:
        clean_parent = re.sub(r'[^\w\s-]', '', parent)
        clean_parent = re.sub(r'[-\s]+', '_', clean_parent)
        clean_parent = clean_parent.lower()
        return f"{clean_parent}_{clean_title}"
    
    return clean_title


def format_section_content(section: dict) -> str:
    """
    Format a section dict into a readable document string.
    
    Args:
        section: Section dict with title, content, parent
        
    Returns:
        Formatted content string
    """
    parts = []
    
    if section.get("parent"):
        parts.append(f"# {section['parent']}")
    
    parts.append(f"## {section['title']}")
    parts.append("")
    parts.append(section['content'])
    
    return "\n".join(parts)


def import_to_knowledge_base(kb, sections: list[dict], source_file: Optional[str] = None) -> int:
    """
    Import sections into a knowledge base.
    
    Args:
        kb: CoachingKnowledgeBase instance
        sections: List of section dicts from load_markdown
        source_file: Optional source file name for metadata
        
    Returns:
        Number of documents successfully added
    """
    added = 0
    
    for section in sections:
        # Format content with context
        content = format_section_content(section)
        
        # Add metadata
        metadata = {
            "source": source_file or "unknown",
            "title": section["title"],
        }
        if section.get("parent"):
            metadata["parent"] = section["parent"]
        
        # Add to knowledge base
        if kb.add_document(
            doc_id=section["id"],
            content=content,
            tags=[],  # No tags - semantic search will handle relevance
        ):
            added += 1
        else:
            logger.warning(f"Failed to add section: {section['title']}")
    
    logger.info(f"Imported {added}/{len(sections)} sections to knowledge base")
    return added


def import_markdown_file(kb, file_path: Path) -> int:
    """
    Convenience function to load and import a markdown file.
    
    Args:
        kb: CoachingKnowledgeBase instance
        file_path: Path to markdown file
        
    Returns:
        Number of documents added
    """
    sections = load_markdown(file_path)
    
    if not sections:
        logger.warning(f"No sections found in {file_path}")
        return 0
    
    return import_to_knowledge_base(kb, sections, source_file=file_path.name)

