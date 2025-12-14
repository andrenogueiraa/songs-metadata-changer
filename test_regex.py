import re

def parse_filename(filename):
    # Remove extension
    if '.' in filename:
        name = filename.rsplit('.', 1)[0]
    else:
        name = filename

    # Regex patterns to try
    # Pattern 1: Track - Title - Artist (Standard)
    # Handles: "01 - DE LADINHO - IVETE SANGALO", "03a - MUSICA - ARTISTA"
    # Also handles loose spacing around hyphens
    pattern1 = r"^(\d+[a-zA-Z]?)\s*-\s*(.+?)\s*-\s*(.+)$"

    match = re.match(pattern1, name)
    if match:
        return {
            "track": match.group(1).strip(),
            "title": match.group(2).strip(),
            "artist": match.group(3).strip()
        }
    return None

test_cases = [
    "01 - DE LADINHO - IVETE SANGALO.mp3",
    "03 - MUSICA- ARTISTA.mp3",
    "03a - MUSICA - ARTISTA.mp3",
    "04 - MUSICA - ARTISTA", # No extension
    "10 - Title With - Dash - Artist", # Tricky one
    "Invalid Format - Artist"
]

for test in test_cases:
    print(f"Testing: '{test}' -> {parse_filename(test)}")
