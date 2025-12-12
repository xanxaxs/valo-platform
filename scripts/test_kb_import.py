"""
Test knowledge base import with real data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.knowledge_base import CoachingKnowledgeBase
from src.ai.knowledge_loader import load_markdown, import_to_knowledge_base

def main():
    """Test KB import."""
    # Initialize KB
    kb_dir = Path(__file__).parent.parent / "data" / "chroma"
    kb = CoachingKnowledgeBase(persist_directory=kb_dir)
    
    print(f"Current KB documents: {kb.document_count}")
    
    # Try to load knowledge.md
    knowledge_file = Path(__file__).parent.parent / "knowledge.md"
    
    if not knowledge_file.exists():
        print(f"Error: {knowledge_file} not found")
        return 1
    
    # Read file directly
    try:
        content = knowledge_file.read_text(encoding="utf-8")
        print(f"File size: {len(content)} chars")
        
        if len(content) == 0:
            print("Warning: File appears to be empty")
            return 1
        
        # Write to temp file and parse
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        sections = load_markdown(tmp_path)
        tmp_path.unlink()
        
        print(f"\nParsed {len(sections)} sections:")
        for s in sections[:5]:  # Show first 5
            print(f"  - {s['title']}")
            if s.get('parent'):
                print(f"    (parent: {s['parent']})")
        
        if len(sections) > 5:
            print(f"  ... and {len(sections) - 5} more")
        
        # Import
        if sections:
            print(f"\nImporting {len(sections)} sections...")
            count = import_to_knowledge_base(kb, sections, source_file="knowledge.md")
            print(f"Imported {count} sections")
            print(f"Total KB documents: {kb.document_count}")
        else:
            print("No sections to import")
            return 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

