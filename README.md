# Songs Metadata Changer

A Python application with a table-based GUI for viewing, editing, and managing MP3 file metadata.

## Features

- **Table-based UI**: View all MP3 files in a folder with their metadata in an easy-to-read table
- **Metadata Display**: Shows filename, path, title, artist, album, track number, genre, date, and more
- **Inline Editing**: Double-click any metadata cell to edit it directly
- **Auto-parse from Filename**: Automatically extract metadata from filenames using pattern matching
- **Bulk Operations**: Create metadata for all files or remove all metadata at once
- **Recursive Folder Scanning**: Scans subdirectories to find all MP3 files

## Requirements

- Python 3.12+
- tkinter (usually included with Python)
- mutagen

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd songs-metadata-changer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

1. Click "Selecionar Pasta" to choose a folder containing MP3 files
2. The table will populate with all MP3 files and their current metadata
3. Double-click any metadata cell to edit it inline
4. Use "Criar Metadados do Nome do Arquivo" to parse filenames and create metadata
5. Use "Remover Todos os Metadados" to clear all metadata from all files

## Filename Formats Supported

The application can parse the following filename formats:
- `01 - Title - Artist.mp3`
- `03a - Title - Artist.mp3`
- `50 - Title   Artist.mp3` (wide spaces)
- `40- Title.mp3` (no artist)
- `Title - Artist.mp3` (no track number)

## Building Windows Executable

See [BUILD_WINDOWS.md](BUILD_WINDOWS.md) for instructions on building a Windows executable.

## License

[Add your license here]

