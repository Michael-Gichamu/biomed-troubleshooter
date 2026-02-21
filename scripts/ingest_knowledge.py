"""
Knowledge Base Ingestion Script

Ingests documentation files into ChromaDB for RAG retrieval.
Supports: .md, .txt, .pdf (text extraction)

Usage:
    python scripts/ingest_knowledge.py
    python scripts/ingest_knowledge.py --folder data/knowledge/equipment
    python scripts/ingest_knowledge.py --file my_doc.md
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.rag_repository import RAGRepository


# =============================================================================
# Document Loaders
# =============================================================================

def load_text_file(filepath: Path) -> str:
    """Load content from a text/markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def load_pdf_file(filepath: Path) -> str:
    """Load text content from a PDF file."""
    try:
        import pypdf
        
        text = []
        with open(filepath, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text())
        
        return '\n'.join(text)
    
    except ImportError:
        print("  [WARN] pypdf not installed. Install with: pip install pypdf")
        return ""
    except Exception as e:
        print(f"  [ERROR] Failed to read PDF: {e}")
        return ""


def load_document(filepath: Path) -> Optional[str]:
    """
    Load document content based on file type.
    
    Args:
        filepath: Path to the document
        
    Returns:
        Document text content or None if unsupported
    """
    suffix = filepath.suffix.lower()
    
    if suffix in ['.md', '.txt', '.markdown']:
        return load_text_file(filepath)
    elif suffix == '.pdf':
        return load_pdf_file(filepath)
    else:
        print(f"  [SKIP] Unsupported file type: {suffix}")
        return None


# =============================================================================
# Chunking Strategies
# =============================================================================

def chunk_by_paragraphs(
    content: str,
    max_chunk_size: int = 1000,
    overlap: int = 100
) -> List[str]:
    """
    Split content into chunks by paragraphs.
    
    Args:
        content: Document text
        max_chunk_size: Maximum characters per chunk
        overlap: Characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    paragraphs = content.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def chunk_by_headers(content: str) -> List[Dict]:
    """
    Split markdown content by headers.
    Each chunk is a section with its header.
    
    Args:
        content: Markdown document text
        
    Returns:
        List of chunk dictionaries with header and content
    """
    lines = content.split('\n')
    chunks = []
    current_header = "Introduction"
    current_content = []
    
    for line in lines:
        # Check for markdown headers
        if line.startswith('#'):
            # Save previous section
            if current_content:
                chunk_text = '\n'.join(current_content).strip()
                if chunk_text:
                    chunks.append({
                        'header': current_header,
                        'content': chunk_text
                    })
            
            # Start new section
            current_header = line.lstrip('#').strip()
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_content:
        chunk_text = '\n'.join(current_content).strip()
        if chunk_text:
            chunks.append({
                'header': current_header,
                'content': chunk_text
            })
    
    return chunks


def smart_chunk(content: str, filepath: Path) -> List[Dict]:
    """
    Intelligently chunk document based on content type.
    
    Args:
        content: Document text
        filepath: Source file path
        
    Returns:
        List of chunk dictionaries
    """
    chunks = []
    
    # For markdown files, use header-based chunking
    if filepath.suffix.lower() in ['.md', '.markdown']:
        header_chunks = chunk_by_headers(content)
        for chunk in header_chunks:
            chunks.append({
                'text': f"# {chunk['header']}\n\n{chunk['content']}",
                'section': chunk['header']
            })
    else:
        # For other files, use paragraph chunking
        text_chunks = chunk_by_paragraphs(content)
        for i, chunk in enumerate(text_chunks):
            chunks.append({
                'text': chunk,
                'section': f"Part {i+1}"
            })
    
    return chunks


# =============================================================================
# Metadata Extraction
# =============================================================================

def extract_metadata(content: str, filepath: Path) -> Dict:
    """
    Extract metadata from document content.
    
    Args:
        content: Document text
        filepath: Source file path
        
    Returns:
        Metadata dictionary
    """
    metadata = {
        'source_file': str(filepath.name),
        'source_path': str(filepath),
        'ingested_at': datetime.utcnow().isoformat(),
        'file_type': filepath.suffix.lower(),
    }
    
    # Try to extract equipment model from content
    import re
    
    # Look for equipment model patterns
    model_patterns = [
        r'Equipment[:\s]+([A-Z0-9\-]+)',
        r'Model[:\s]+([A-Z0-9\-]+)',
        r'equipment_model[:\s]+([A-Z0-9\-]+)',
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            metadata['equipment_model'] = match.group(1)
            break
    
    # Look for component mentions
    component_keywords = ['power supply', 'psu', 'transformer', 'rectifier', 
                          'capacitor', 'resistor', 'diode', 'transistor']
    found_components = []
    for kw in component_keywords:
        if kw.lower() in content.lower():
            found_components.append(kw)
    
    if found_components:
        metadata['components'] = ', '.join(found_components)
    
    return metadata


# =============================================================================
# Main Ingestion Logic
# =============================================================================

def ingest_file(
    filepath: Path,
    rag: RAGRepository,
    verbose: bool = True
) -> int:
    """
    Ingest a single file into the knowledge base.
    
    Args:
        filepath: Path to the file
        rag: RAG repository instance
        verbose: Print progress messages
        
    Returns:
        Number of chunks ingested
    """
    if verbose:
        print(f"\n[FILE] {filepath}")
    
    # Load document
    content = load_document(filepath)
    if not content:
        return 0
    
    # Extract metadata
    base_metadata = extract_metadata(content, filepath)
    
    # Chunk document
    chunks = smart_chunk(content, filepath)
    
    if verbose:
        print(f"  [CHUNKS] {len(chunks)} sections")
    
    # Ingest each chunk
    ingested = 0
    for i, chunk in enumerate(chunks):
        chunk_metadata = {
            **base_metadata,
            'chunk_index': i,
            'section': chunk.get('section', f'Part {i+1}')
        }
        
        try:
            rag.add_document(
                content=chunk['text'],
                metadata=chunk_metadata
            )
            ingested += 1
        except Exception as e:
            if verbose:
                print(f"  [ERROR] Failed to ingest chunk {i}: {e}")
    
    return ingested


def ingest_folder(
    folder: Path,
    rag: RAGRepository,
    recursive: bool = True,
    verbose: bool = True
) -> int:
    """
    Ingest all documents in a folder.
    
    Args:
        folder: Path to the folder
        rag: RAG repository instance
        recursive: Search subfolders
        verbose: Print progress messages
        
    Returns:
        Total number of chunks ingested
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"INGESTING FOLDER: {folder}")
        print(f"{'='*60}")
    
    # Find all supported files
    extensions = ['.md', '.txt', '.markdown', '.pdf']
    
    if recursive:
        files = []
        for ext in extensions:
            files.extend(folder.rglob(f'*{ext}'))
    else:
        files = []
        for ext in extensions:
            files.extend(folder.glob(f'*{ext}'))
    
    # Filter out README files (optional)
    files = [f for f in files if f.name.lower() != 'readme.md']
    
    if verbose:
        print(f"Found {len(files)} document(s)")
    
    # Ingest each file
    total_ingested = 0
    for filepath in files:
        ingested = ingest_file(filepath, rag, verbose)
        total_ingested += ingested
    
    return total_ingested


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into the AI Agent knowledge base"
    )
    
    parser.add_argument(
        '--folder', '-f',
        type=str,
        default='data/knowledge',
        help='Folder containing documents (default: data/knowledge)'
    )
    
    parser.add_argument(
        '--file',
        type=str,
        help='Single file to ingest'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not search subfolders'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress output'
    )
    
    args = parser.parse_args()
    
    # Initialize RAG
    print("Initializing RAG repository...")
    rag = RAGRepository()
    
    try:
        rag.initialize()
    except Exception as e:
        print(f"[ERROR] Failed to initialize RAG: {e}")
        print("\nMake sure ChromaDB is running:")
        print("  docker run -p 8000:8000 chromadb/chroma")
        return 1
    
    # Ingest
    verbose = not args.quiet
    total = 0
    
    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"[ERROR] File not found: {filepath}")
            return 1
        total = ingest_file(filepath, rag, verbose)
    else:
        folder = Path(args.folder)
        if not folder.exists():
            print(f"[ERROR] Folder not found: {folder}")
            return 1
        total = ingest_folder(
            folder, 
            rag, 
            recursive=not args.no_recursive,
            verbose=verbose
        )
    
    # Summary
    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"Total chunks ingested: {total}")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())