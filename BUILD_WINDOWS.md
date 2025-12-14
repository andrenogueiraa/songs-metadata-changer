# Building Windows Executable

## Prerequisites

To build a Windows executable, you need to run PyInstaller on a Windows machine (or use Wine on Linux, though this is less reliable).

### Option 1: Build on Windows (Recommended)

1. **Install Python on Windows**
   - Download Python 3.12+ from python.org
   - Make sure to check "Add Python to PATH" during installation

2. **Install dependencies**
   ```cmd
   pip install -r requirements.txt
   ```

3. **Build the executable**
   ```cmd
   pyinstaller OrganizadorMusicas.spec
   ```

4. **Find the executable**
   - The executable will be in the `dist/` folder
   - File: `dist/OrganizadorMusicas.exe`

### Option 2: Build on Linux using Wine (Advanced)

This is more complex and may have issues. You'll need:
- Wine installed
- Windows Python installed in Wine
- PyInstaller installed in Wine Python

**Note:** This method is not recommended as it's error-prone.

## Building Instructions

### Using the spec file (recommended):
```bash
pyinstaller OrganizadorMusicas.spec
```

### Using command line directly:
```bash
pyinstaller --name=OrganizadorMusicas --windowed --onefile --hidden-import=mutagen --hidden-import=mutagen.mp3 --hidden-import=mutagen.easyid3 --hidden-import=mutagen.id3 main.py
```

## Output

After building, you'll find:
- `dist/OrganizadorMusicas.exe` - The standalone executable (this is what you distribute)
- `build/` - Temporary build files (can be deleted)

## Testing

Before distributing:
1. Test the executable on a Windows machine without Python installed
2. Test with various MP3 files
3. Verify all functionality works (folder selection, metadata editing, etc.)

## Distribution

The `OrganizadorMusicas.exe` file is standalone and includes all dependencies. You can distribute just this single file.

## Troubleshooting

- **If the executable doesn't start**: Try building with `console=True` in the spec file to see error messages
- **If mutagen errors occur**: Make sure all hidden imports are included in the spec file
- **If tkinter errors occur**: Make sure tkinter is available (it's usually included with Python on Windows)

