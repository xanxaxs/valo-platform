"""
Import knowledge.md into the knowledge base.

Run this script to import the team knowledge document.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.knowledge_base import CoachingKnowledgeBase
from src.ai.knowledge_loader import import_markdown_file

def main():
    """Import knowledge.md into knowledge base."""
    # Path to knowledge.md
    knowledge_file = Path(__file__).parent.parent / "knowledge.md"
    
    if not knowledge_file.exists():
        print(f"Error: {knowledge_file} not found")
        return 1
    
    # Initialize knowledge base
    kb_dir = Path(__file__).parent.parent / "data" / "chroma"
    kb = CoachingKnowledgeBase(persist_directory=kb_dir)
    
    # Bootstrap default knowledge if empty
    if kb.document_count == 0:
        print("Bootstrapping default knowledge...")
        kb.bootstrap()
    
    # Import knowledge.md
    print(f"Importing {knowledge_file}...")
    count = import_markdown_file(kb, knowledge_file)
    
    if count > 0:
        print(f"Successfully imported {count} sections")
    else:
        print("Warning: No sections were imported")
    
    print(f"Total documents in KB: {kb.document_count}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

