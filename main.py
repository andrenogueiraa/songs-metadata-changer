import os
import re
import threading
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError

# Try to import tkinter, fallback to CLI if not available
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

    GUI_AVAILABLE = False


class LogicMixin:
    def parse_filename(self, filename):
        # Remove extension
        name, _ = os.path.splitext(filename)

        # Regex patterns to try
        # Pattern 1: Track - Title - Artist (Standard)
        # Handles: "01 - DE LADINHO - IVETE SANGALO", "03a - MUSICA - ARTISTA"
        # Also handles loose spacing around hyphens
        pattern1 = r"^(\d+[a-zA-Z]?)\s*-\s*(.+?)\s*-\s*(.+)$"

        # Pattern 2: Track - Title   Artist (Missing second hyphen, wide spaces)
        # Handles: "50 - SERTANEJA   DINO FRANCO E MOURAÍ"
        pattern2 = r"^(\d+[a-zA-Z]?)\s*-\s*(.+?)\s{2,}(.+)$"

        # Pattern 3: Track - Title (No Artist)
        # Handles: "40- Footloose"
        pattern3 = r"^(\d+[a-zA-Z]?)\s*-\s*(.+)$"

        # Pattern 4: Title - Artist (No Track Number)
        # Handles: "SANTANA O CANTADOR - XOTE PÉ DE SERRA"
        # Assumption: Title comes first based on user's other files
        pattern4 = r"^(.+?)\s*-\s*(.+)$"

        # Try patterns in order of specificity
        for i, pattern in enumerate([pattern1, pattern2, pattern3, pattern4]):
            match = re.match(pattern, name)
            if match:
                groups = match.groups()
                if i == 0 or i == 1: # Patterns with Track, Title, Artist
                    return {
                        "track": groups[0].strip(),
                        "title": groups[1].strip(),
                        "artist": groups[2].strip()
                    }
                elif i == 2: # Pattern with Track, Title (No Artist)
                    return {
                        "track": groups[0].strip(),
                        "title": groups[1].strip(),
                        "artist": None
                    }
                elif i == 3: # Pattern with Title, Artist (No Track)
                    return {
                        "track": None,
                        "title": groups[0].strip(),
                        "artist": groups[1].strip()
                    }
        return None

class MusicMetadataEditor(LogicMixin):
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de Músicas")
        self.root.geometry("1400x700")

        # Store file paths and metadata
        self.file_data = {}  # Maps file_path to metadata dict

        # Metadata fields to display
        self.metadata_fields = ['title', 'artist', 'album', 'tracknumber', 'genre', 'date',
                               'albumartist', 'composer', 'performer']

        # Styles
        style = ttk.Style()
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=6, font=("Helvetica", 10))

        # Main Frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Folder Selection
        self.folder_path = tk.StringVar()

        frame_select = ttk.Frame(main_frame)
        frame_select.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame_select, text="Pasta:").pack(side=tk.LEFT, padx=(0, 5))
        entry_path = ttk.Entry(frame_select, textvariable=self.folder_path, width=60)
        entry_path.pack(side=tk.LEFT, padx=(0, 10), expand=True, fill=tk.X)

        btn_browse = ttk.Button(frame_select, text="Selecionar Pasta", command=self.browse_folder)
        btn_browse.pack(side=tk.LEFT)

        # Table Frame with scrollbars
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Define columns
        columns = ['filename', 'path'] + self.metadata_fields
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='browse')

        # Configure column headings and widths
        self.tree.heading('filename', text='Nome do Arquivo')
        self.tree.column('filename', width=200, minwidth=150)

        self.tree.heading('path', text='Caminho')
        self.tree.column('path', width=300, minwidth=200)

        for field in self.metadata_fields:
            display_name = field.replace('tracknumber', 'Track #').title()
            self.tree.heading(field, text=display_name)
            self.tree.column(field, width=120, minwidth=80)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack scrollbars and tree
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bind double-click for editing
        self.tree.bind('<Double-1>', self.on_cell_double_click)

        # Store editing state
        self.editing_item = None
        self.editing_column = None
        self.edit_entry = None

        # Action Buttons Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.btn_create_metadata = ttk.Button(button_frame, text="Criar Metadados do Nome do Arquivo",
                                             command=self.create_metadata_for_all)
        self.btn_create_metadata.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_remove_metadata = ttk.Button(button_frame, text="Remover Todos os Metadados",
                                             command=self.remove_metadata_for_all)
        self.btn_remove_metadata.pack(side=tk.LEFT)

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path.set(folder_selected)
            self.load_songs_from_folder(folder_selected)

    def read_metadata(self, file_path):
        """Read metadata from an MP3 file and return as dictionary."""
        metadata = {}
        try:
            try:
                audio = MP3(file_path, ID3=EasyID3)
            except ID3NoHeaderError:
                # File has no ID3 tags
                return metadata

            # Read all available metadata fields
            for field in self.metadata_fields:
                try:
                    value = audio.get(field)
                    if value:
                        # EasyID3 returns lists, join them with semicolons
                        if isinstance(value, list):
                            metadata[field] = '; '.join(str(v) for v in value)
                        else:
                            metadata[field] = str(value)
                    else:
                        metadata[field] = ''
                except (KeyError, AttributeError):
                    metadata[field] = ''
        except Exception as e:
            # Return empty metadata on error
            pass
        return metadata

    def load_songs_from_folder(self, path):
        """Scan folder recursively and populate table with all MP3 files."""
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.file_data.clear()

        # Disable buttons during loading
        self.btn_create_metadata.config(state='disabled')
        self.btn_remove_metadata.config(state='disabled')

        def load_in_thread():
            files_to_process = []

            # Walk through directory
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.mp3'):
                        files_to_process.append(os.path.join(root, file))

            # Update UI in main thread
            self.root.after(0, lambda: self._populate_table(files_to_process))

        threading.Thread(target=load_in_thread, daemon=True).start()

    def _populate_table(self, file_paths):
        """Populate table with files and their metadata."""
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            metadata = self.read_metadata(file_path)

            # Store file data
            self.file_data[file_path] = metadata

            # Prepare row values
            values = [filename, file_path]
            for field in self.metadata_fields:
                values.append(metadata.get(field, ''))

            # Insert row
            self.tree.insert('', 'end', iid=file_path, values=values)

        # Re-enable buttons
        self.btn_create_metadata.config(state='normal')
        self.btn_remove_metadata.config(state='normal')

    def on_cell_double_click(self, event):
        """Handle double-click on table cell to enable editing."""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return

        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)

        if not item:
            return

        # Get column index
        col_index = int(column.replace('#', '')) - 1
        columns = ['filename', 'path'] + self.metadata_fields

        if col_index < 0 or col_index >= len(columns):
            return

        col_name = columns[col_index]

        # Don't allow editing filename or path
        if col_name in ['filename', 'path']:
            return

        # Get current value
        current_values = list(self.tree.item(item, 'values'))
        current_value = current_values[col_index] if col_index < len(current_values) else ''

        # Get cell bounding box
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return

        # Create entry widget for editing
        self.editing_item = item
        self.editing_column = col_name
        self.edit_entry = ttk.Entry(self.tree)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()

        # Place entry over cell
        self.edit_entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])

        # Bind events
        self.edit_entry.bind('<Return>', self.on_edit_commit)
        self.edit_entry.bind('<Escape>', self.on_edit_cancel)
        self.edit_entry.bind('<FocusOut>', self.on_edit_commit)

    def on_edit_commit(self, event=None):
        """Commit the edit and update the table and file data."""
        if not self.editing_item or not self.edit_entry:
            return

        new_value = self.edit_entry.get()
        file_path = self.editing_item
        column = self.editing_column

        # Update file data
        if file_path in self.file_data:
            self.file_data[file_path][column] = new_value

        # Update table
        current_values = list(self.tree.item(self.editing_item, 'values'))
        columns = ['filename', 'path'] + self.metadata_fields
        col_index = columns.index(column)
        if col_index < len(current_values):
            current_values[col_index] = new_value
            self.tree.item(self.editing_item, values=current_values)

        # Save to file
        self.save_metadata(file_path, self.file_data[file_path])

        # Clean up
        self.edit_entry.destroy()
        self.editing_item = None
        self.editing_column = None
        self.edit_entry = None

    def on_edit_cancel(self, event=None):
        """Cancel the edit."""
        if self.edit_entry:
            self.edit_entry.destroy()
        self.editing_item = None
        self.editing_column = None
        self.edit_entry = None

    def save_metadata(self, file_path, metadata_dict):
        """Save metadata dictionary to MP3 file."""
        try:
            try:
                audio = MP3(file_path, ID3=EasyID3)
            except ID3NoHeaderError:
                audio = MP3(file_path)
                audio.add_tags()
                audio = MP3(file_path, ID3=EasyID3)

            # Update metadata fields
            for field, value in metadata_dict.items():
                if field in self.metadata_fields:
                    if value and value.strip():
                        audio[field] = value.strip()
                    elif field in audio:
                        del audio[field]

            audio.save()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar metadados para {os.path.basename(file_path)}:\n{str(e)}")

    def create_metadata_for_all(self):
        """Apply filename parsing to all rows in the table."""
        if not self.file_data:
            messagebox.showinfo("Info", "Nenhum arquivo carregado.")
            return

        # Disable buttons during processing
        self.btn_create_metadata.config(state='disabled')
        self.btn_remove_metadata.config(state='disabled')

        def process_in_thread():
            updated_count = 0
            error_count = 0

            for file_path in list(self.file_data.keys()):
                filename = os.path.basename(file_path)
                parsed = self.parse_filename(filename)

                if parsed:
                    # Update metadata dict
                    metadata = self.file_data[file_path].copy()

                    if parsed.get('title'):
                        metadata['title'] = parsed['title']
                    if parsed.get('artist'):
                        metadata['artist'] = parsed['artist']
                    if parsed.get('track'):
                        metadata['tracknumber'] = parsed['track']

                    # Set album from folder name
                    folder_name = os.path.basename(os.path.dirname(file_path))
                    metadata['album'] = folder_name

                    # Save to file
                    try:
                        self.save_metadata(file_path, metadata)
                        self.file_data[file_path] = metadata
                        updated_count += 1
                    except Exception:
                        error_count += 1

                    # Update table in main thread
                    self.root.after(0, lambda fp=file_path, md=metadata: self._update_table_row(fp, md))
                else:
                    error_count += 1

            # Show completion message
            self.root.after(0, lambda: messagebox.showinfo("Concluído",
                f"Metadados criados para {updated_count} arquivo(s).\n{error_count} arquivo(s) com formato não reconhecido."))
            self.root.after(0, lambda: self.btn_create_metadata.config(state='normal'))
            self.root.after(0, lambda: self.btn_remove_metadata.config(state='normal'))

        threading.Thread(target=process_in_thread, daemon=True).start()

    def _update_table_row(self, file_path, metadata):
        """Update a single row in the table."""
        filename = os.path.basename(file_path)
        values = [filename, file_path]
        for field in self.metadata_fields:
            values.append(metadata.get(field, ''))
        self.tree.item(file_path, values=values)

    def remove_metadata_for_all(self):
        """Remove all metadata from all files."""
        if not self.file_data:
            messagebox.showinfo("Info", "Nenhum arquivo carregado.")
            return

        # Confirm action
        result = messagebox.askyesno("Confirmar",
            f"Tem certeza que deseja remover TODOS os metadados de {len(self.file_data)} arquivo(s)?\n\nEsta ação não pode ser desfeita!")
        if not result:
            return

        # Disable buttons during processing
        self.btn_create_metadata.config(state='disabled')
        self.btn_remove_metadata.config(state='disabled')

        def process_in_thread():
            success_count = 0
            error_count = 0

            for file_path in list(self.file_data.keys()):
                try:
                    # Load with ID3 (not EasyID3) to delete all tags
                    try:
                        audio = MP3(file_path, ID3=ID3)
                    except ID3NoHeaderError:
                        # No tags to remove
                        success_count += 1
                        self.root.after(0, lambda fp=file_path: self._clear_table_row(fp))
                        continue

                    # Delete all tags
                    audio.delete()
                    audio.save()

                    # Clear metadata dict
                    self.file_data[file_path] = {field: '' for field in self.metadata_fields}
                    success_count += 1

                    # Update table in main thread
                    self.root.after(0, lambda fp=file_path: self._clear_table_row(fp))
                except Exception as e:
                    error_count += 1

            # Show completion message
            self.root.after(0, lambda: messagebox.showinfo("Concluído",
                f"Metadados removidos de {success_count} arquivo(s).\n{error_count} erro(s)."))
            self.root.after(0, lambda: self.btn_create_metadata.config(state='normal'))
            self.root.after(0, lambda: self.btn_remove_metadata.config(state='normal'))

        threading.Thread(target=process_in_thread, daemon=True).start()

    def _clear_table_row(self, file_path):
        """Clear metadata columns for a row in the table."""
        filename = os.path.basename(file_path)
        values = [filename, file_path] + [''] * len(self.metadata_fields)
        self.tree.item(file_path, values=values)

class CLIEditor(LogicMixin):
    def log(self, msg):
        print(msg)

    def process(self, path):
        self.log(f"Processando pasta: {path}")
        files_to_process = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith('.mp3'):
                    files_to_process.append(os.path.join(root, file))

        self.log(f"Encontrados {len(files_to_process)} arquivos.")

        if not files_to_process:
            self.log("Nenhum arquivo MP3 encontrado para processar.")
            return

        success_count = 0
        error_count = 0

        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            metadata = self.parse_filename(filename)
            if metadata:
                try:
                    try:
                        audio = MP3(file_path, ID3=EasyID3)
                    except ID3NoHeaderError:
                        audio = MP3(file_path)
                        audio.add_tags()
                        audio = MP3(file_path, ID3=EasyID3)

                    if metadata['title']:
                        audio['title'] = metadata['title']
                    if metadata['artist']:
                        audio['artist'] = metadata['artist']
                    if metadata['track']:
                        audio['tracknumber'] = metadata['track']
                    audio['album'] = os.path.basename(os.path.dirname(file_path))
                    audio.save()

                    log_msg = f"[OK] {filename} -> T: {metadata['title']}"
                    if metadata['artist']:
                        log_msg += f", A: {metadata['artist']}"
                    self.log(log_msg)
                    success_count += 1
                except Exception as e:
                    self.log(f"[ERRO] Falha ao salvar {filename}: {e}")
                    error_count += 1
            else:
                self.log(f"[PULAR] Formato não reconhecido: {filename}")
                error_count += 1
        self.log(f"\nConcluído! Sucesso: {success_count}, Erros/Pulados: {error_count}")

def run_cli():
    print("=== Organizador de Músicas (Modo CLI) ===")
    print("Interface gráfica não disponível neste ambiente.")
    path = input("Digite o caminho da pasta com as músicas: ").strip()

    if not os.path.isdir(path):
        print("Pasta inválida ou não encontrada.")
        return

    cli_editor = CLIEditor()
    cli_editor.process(path)
    print("\nProcessamento CLI finalizado!")

if __name__ == "__main__":
    if GUI_AVAILABLE:
        root = tk.Tk()
        app = MusicMetadataEditor(root)
        root.mainloop()
    else:
        run_cli()
