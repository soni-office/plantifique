"""
Reads the operational policy doc and splits it into semantic chunks for indexing.
Chunks are split on section headers (lines starting with all-caps or "---" separators).
"""
import re
import os
from typing import List, Dict

DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "sample_requests_plantifique_doc.txt"
)


def load_chunks(filepath: str = DOC_PATH) -> List[Dict[str, str]]:
    """
    Returns a list of dicts: {"id": str, "text": str, "section": str}
    Each chunk is a logical section of the policy document.
    """
    with open(filepath, "r") as f:
        raw = f.read()

    # Split on "---" horizontal rules which separate major sections
    sections = re.split(r"\n---+\n", raw)

    chunks = []
    chunk_id = 0

    for section in sections:
        section = section.strip()
        if not section or len(section) < 40:
            continue

        # Each section may contain sub-sections separated by blank lines.
        # Keep each top-level section as one chunk (they are already concise).
        first_line = section.split("\n")[0].strip()
        label = first_line[:80] if first_line else f"section_{chunk_id}"

        chunks.append({
            "id": f"chunk_{chunk_id:03d}",
            "text": section,
            "section": label,
        })
        chunk_id += 1

    return chunks
