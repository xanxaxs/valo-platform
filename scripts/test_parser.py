"""
Test markdown parser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.knowledge_loader import load_markdown

def main():
    knowledge_file = Path(__file__).parent.parent / "knowledge.md"
    
    print(f"Loading: {knowledge_file}")
    print(f"Exists: {knowledge_file.exists()}")
    
    if not knowledge_file.exists():
        print("File not found!")
        return 1
    
    sections = load_markdown(knowledge_file)
    
    print(f"\nFound {len(sections)} sections:")
    for i, s in enumerate(sections, 1):
        print(f"\n{i}. {s['title']}")
        print(f"   ID: {s['id']}")
        print(f"   Parent: {s.get('parent', 'None')}")
        print(f"   Content length: {len(s['content'])} chars")
        print(f"   Preview: {s['content'][:100]}...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

