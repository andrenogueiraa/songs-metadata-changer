import os
import re
import threading
import threading
import sys
import sys
import pygame # pygame-ce
import sv_ttk
from PIL import Image, ImageTk
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

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def on_closing(self):
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except:
            pass
        self.root.destroy()
        sys.exit()

class MusicMetadataEditor(LogicMixin):
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de Músicas")
        self.root.geometry("1400x900")
        
        # Apply Theme
        sv_ttk.set_theme("dark")
        
        # Load Icons
        self.icons = {}
        self._load_icons()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Store file paths and metadata
        self.file_data = {}  # Maps file_path to metadata dict
        self.shown_file_paths = [] # List of file paths currently in the table (for sorting/filtering)
        self.sort_column_active = None
        self.sort_reverse = False

        # Metadata fields to display

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

        # Filter Frame
        frame_filter = ttk.Frame(main_frame)
        frame_filter.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(frame_filter, text="Filtrar por:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.filter_col_var = tk.StringVar(value="Todos")
        filter_options = ["Todos", "Nome do Arquivo"] + [f.capitalize() for f in self.metadata_fields]
        self.combo_filter = ttk.Combobox(frame_filter, textvariable=self.filter_col_var, values=filter_options, state="readonly", width=15)
        self.combo_filter.pack(side=tk.LEFT, padx=(0, 10))
        
        self.filter_text = tk.StringVar()
        self.filter_text.trace("w", self._on_filter_change)
        entry_filter = ttk.Entry(frame_filter, textvariable=self.filter_text, width=40)
        entry_filter.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(frame_filter, text="Limpar", command=lambda: self.filter_text.set("")).pack(side=tk.LEFT)

        # Table Frame with scrollbars
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Define columns
        columns = ['filename', 'path'] + self.metadata_fields
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='browse')

        # Configure column headings and widths
        self.tree.heading('filename', text='Nome do Arquivo', command=lambda: self.sort_column('filename'))
        self.tree.column('filename', width=200, minwidth=150)

        self.tree.heading('path', text='Caminho', command=lambda: self.sort_column('path'))
        self.tree.column('path', width=300, minwidth=200)

        for field in self.metadata_fields:
            display_name = field.replace('tracknumber', 'Track #').title()
            self.tree.heading(field, text=display_name, command=lambda f=field: self.sort_column(f))
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

        # Progress Bar and Status Label
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.lbl_status = ttk.Label(self.progress_frame, text="")
        self.lbl_status.pack(side=tk.LEFT)

        # Action Buttons Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.btn_create_metadata = ttk.Button(button_frame, text="Criar Metadados do Nome do Arquivo",
                                             command=self.create_metadata_for_all)
        self.btn_create_metadata.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_remove_metadata = ttk.Button(button_frame, text="Remover Todos os Metadados",
                                             command=self.remove_metadata_for_all)
        self.btn_remove_metadata.pack(side=tk.LEFT)

        # Music Player Frame (Bottom)
        self.dataset_player_ui(main_frame)
    
    def _load_icons(self):
        # Load PNG icons using Pillow for scaling and stability
        icon_size = (24, 24)
        control_size = (32, 32)
        try:
            self.icons['play'] = ImageTk.PhotoImage(Image.open(self.resource_path("icons/play.png")).resize(control_size, Image.Resampling.LANCZOS))
            self.icons['pause'] = ImageTk.PhotoImage(Image.open(self.resource_path("icons/pause.png")).resize(control_size, Image.Resampling.LANCZOS))
            self.icons['next'] = ImageTk.PhotoImage(Image.open(self.resource_path("icons/next.png")).resize(control_size, Image.Resampling.LANCZOS))
            self.icons['prev'] = ImageTk.PhotoImage(Image.open(self.resource_path("icons/prev.png")).resize(control_size, Image.Resampling.LANCZOS))
            self.icons['volume'] = ImageTk.PhotoImage(Image.open(self.resource_path("icons/volume.png")).resize((20, 20), Image.Resampling.LANCZOS))
            
            # Additional icons if available
            shuffle_path = self.resource_path("icons/shuffle.png")
            if os.path.exists(shuffle_path):
                 self.icons['shuffle'] = ImageTk.PhotoImage(Image.open(shuffle_path).resize(control_size, Image.Resampling.LANCZOS))
            
            repeat_path = self.resource_path("icons/repeat.png")
            if os.path.exists(repeat_path):
                 self.icons['repeat'] = ImageTk.PhotoImage(Image.open(repeat_path).resize(control_size, Image.Resampling.LANCZOS))
                 
        except Exception as e:
            print(f"Error loading icons: {e}")

    def dataset_player_ui(self, parent):
        pygame.mixer.init()
        
        player_frame = ttk.Frame(parent, padding=15, style="Card.TFrame") # Style implied by sv_ttk usually
        player_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        # Song Info (Left)
        info_frame = ttk.Frame(player_frame, width=250)
        info_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        
        self.lbl_player_title = ttk.Label(info_frame, text="Nenhuma música selecionada", font=("Segoe UI", 11, "bold"))
        self.lbl_player_title.pack(anchor="w")
        self.lbl_player_artist = ttk.Label(info_frame, text="--", font=("Segoe UI", 9))
        self.lbl_player_artist.pack(anchor="w")
        
        # Controls (Center)
        controls_frame = ttk.Frame(player_frame)
        controls_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=20)
        
        btns_frame = ttk.Frame(controls_frame)
        btns_frame.pack(pady=(0, 10))
        
        # Previous
        btn_prev = ttk.Button(btns_frame, image=self.icons.get('prev'), command=self.play_prev, style="Icon.TButton")
        btn_prev.pack(side=tk.LEFT, padx=10)
        
        # Play/Pause
        self.btn_play = ttk.Button(btns_frame, image=self.icons.get('play'), command=self.toggle_play, style="Icon.TButton")
        self.btn_play.pack(side=tk.LEFT, padx=10)
        
        # Next
        btn_next = ttk.Button(btns_frame, image=self.icons.get('next'), command=self.play_next, style="Icon.TButton")
        btn_next.pack(side=tk.LEFT, padx=10)
        
        self.progress_var = tk.DoubleVar()
        self.scale_progress = ttk.Scale(controls_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.progress_var, command=self.seek_song)
        self.scale_progress.pack(fill=tk.X)
        
        # Volume (Right)
        vol_frame = ttk.Frame(player_frame)
        vol_frame.pack(side=tk.RIGHT, padx=(20, 0))
        
        if self.icons.get('volume'):
            ttk.Label(vol_frame, image=self.icons['volume']).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Label(vol_frame, text="Vol").pack(side=tk.LEFT)
            
        self.vol_var = tk.DoubleVar(value=50)
        scale_vol = ttk.Scale(vol_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.vol_var, command=self.set_volume, length=100)
        scale_vol.pack(side=tk.LEFT)
        
        self.current_song_path = None
        self.is_playing = False
        self.song_length = 0
        
        # Update timer
        self.root.after(1000, self.update_player_progress)

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
        
        # Reset progress
        self.lbl_status.config(text="Procurando arquivos...")
        self.progress['value'] = 0
        self.root.update_idletasks()

        def load_in_thread():
            files_to_process = []
            
            # Walk through directory
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.mp3'):
                        files_to_process.append(os.path.join(root, file))
            
            total_files = len(files_to_process)
            if total_files == 0:
                self.root.after(0, lambda: self.lbl_status.config(text="Nenhum arquivo encontrado."))
                self.root.after(0, lambda: self._populate_completed())
                return

            prepared_data = []
            
            for i, file_path in enumerate(files_to_process):
                # Read metadata
                metadata = self.read_metadata(file_path)
                prepared_data.append((file_path, metadata))
                
                # Update progress periodically (every 10 files or last one)
                if i % 10 == 0 or i == total_files - 1:
                    progress_val = ((i + 1) / total_files) * 100
                    msg = f"Carregando {i + 1} de {total_files} músicas"
                    self.root.after(0, lambda v=progress_val, m=msg: self._update_progress(v, m))

            # Update UI in main thread with all data
            self.root.after(0, lambda: self._populate_table_bulk(prepared_data))

        threading.Thread(target=load_in_thread, daemon=True).start()

    def _update_progress(self, value, message):
        self.progress['value'] = value
        self.lbl_status.config(text=message)

    def _populate_table_bulk(self, prepared_data):
        """Populate table with pre-loaded data."""
        self.shown_file_paths = []
        for file_path, metadata in prepared_data:
            filename = os.path.basename(file_path)
            
            # Store file data
            self.file_data[file_path] = metadata
            self.shown_file_paths.append(file_path) # Add to displayed list
            
            # Prepare row values
            values = [filename, file_path]
            for field in self.metadata_fields:
                values.append(metadata.get(field, ''))
            
            # Insert row (only if matching filter - though usually empty on load)
            self.tree.insert('', 'end', iid=file_path, values=values)
            
        self._populate_completed()
        
        # If there's a filter/sort active, re-apply it?
        # For now, just load as is.

    def _populate_completed(self):
        """Restore UI state after population."""
        self.lbl_status.config(text=f"Total: {len(self.file_data)} músicas carregadas.")
        self.progress['value'] = 100
        
        # Re-enable buttons
        self.btn_create_metadata.config(state='normal')
        self.btn_remove_metadata.config(state='normal')
        
    def _on_filter_change(self, *args):
        """Filter the table rows based on input."""
        filter_txt = self.filter_text.get().lower()
        col_mode = self.filter_col_var.get()
        
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.shown_file_paths = []
        
        for file_path, metadata in self.file_data.items():
            match = False
            filename = os.path.basename(file_path)
            
            if not filter_txt:
                match = True
            elif col_mode == "Todos":
                # Search everywhere
                if filter_txt in filename.lower():
                    match = True
                else:
                    for v in metadata.values():
                        if filter_txt in str(v).lower():
                            match = True
                            break
            elif col_mode == "Nome do Arquivo":
                if filter_txt in filename.lower():
                    match = True
            else:
                # Specific column
                col_key = col_mode.lower() # Metadata keys are lower
                if col_key in metadata and filter_txt in str(metadata[col_key]).lower():
                    match = True
            
            if match:
                self.shown_file_paths.append(file_path)
                values = [filename, file_path]
                for field in self.metadata_fields:
                    values.append(metadata.get(field, ''))
                self.tree.insert('', 'end', iid=file_path, values=values)

    def sort_column(self, col):
        """Sort table by column."""
        if self.sort_column_active == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
            self.sort_column_active = col
            
        # Sort shown_file_paths based on data
        def sort_key(file_path):
            if col == 'filename':
                return os.path.basename(file_path).lower()
            elif col == 'path':
                return file_path.lower()
            else:
                return self.file_data[file_path].get(col, '').lower()
        
        self.shown_file_paths.sort(key=sort_key, reverse=self.sort_reverse)
        
        # Refresh table
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for file_path in self.shown_file_paths:
            filename = os.path.basename(file_path)
            metadata = self.file_data[file_path]
            values = [filename, file_path]
            for field in self.metadata_fields:
                values.append(metadata.get(field, ''))
            self.tree.insert('', 'end', iid=file_path, values=values)
            
        # Update header arrow (visual only - simplified)
        heading_text = self.tree.heading(col, "text")
        # Strip existing arrow
        heading_text = heading_text.replace(" ▲", "").replace(" ▼", "")
        arrow = " ▼" if self.sort_reverse else " ▲"
        self.tree.heading(col, text=heading_text + arrow)

    def _populate_table(self, file_paths):
        # Legacy
        pass

    def on_cell_double_click(self, event):
        """Handle double-click on table cell to enable editing or play song."""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        
        item = self.tree.identify_row(event.y)
        if not item: return
        
        # If user double clicks the filename, start playing
        column = self.tree.identify_column(event.x)
        if column == '#1': # Filename column
             self.play_song_from_id(item)
             return

        # Editing logic...
        col_index = int(column.replace('#', '')) - 1
        columns = ['filename', 'path'] + self.metadata_fields
        if col_index < 0 or col_index >= len(columns): return
        col_name = columns[col_index]
        if col_name in ['filename', 'path']: return

        # ... existing edit logic ...
        current_values = list(self.tree.item(item, 'values'))
        current_value = current_values[col_index] if col_index < len(current_values) else ''
        bbox = self.tree.bbox(item, column)
        if not bbox: return
        self.editing_item = item
        self.editing_column = col_name
        self.edit_entry = ttk.Entry(self.tree)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        self.edit_entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        self.edit_entry.bind('<Return>', self.on_edit_commit)
        self.edit_entry.bind('<Escape>', self.on_edit_cancel)
        self.edit_entry.bind('<FocusOut>', self.on_edit_commit)

    # --- Player Functions ---
    def play_song_from_id(self, item_id):
        file_path = item_id # iid is file_path
        if file_path and os.path.exists(file_path):
            self.load_and_play(file_path)

    def load_and_play(self, path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self.is_playing = True
            self.current_song_path = path
            self.btn_play.config(image=self.icons.get('pause')) # Use icon
            
            # Update info
            filename = os.path.basename(path)
            metadata = self.file_data.get(path, {})
            title = metadata.get('title', filename)
            artist = metadata.get('artist', 'Desconhecido')
            self.lbl_player_title.config(text=title)
            self.lbl_player_artist.config(text=artist)
            
            # Get length
            audio = MP3(path)
            self.song_length = audio.info.length
            self.scale_progress.config(to=self.song_length)
            
        except Exception as e:
            messagebox.showerror("Erro de Reprodução", str(e))

    def toggle_play(self):
        if not self.current_song_path:
            # Play first selected
            selected = self.tree.selection()
            if selected:
                self.play_song_from_id(selected[0])
            elif self.shown_file_paths:
                self.play_song_from_id(self.shown_file_paths[0])
            return

        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.btn_play.config(image=self.icons.get('play')) # Use icon
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True
            self.btn_play.config(image=self.icons.get('pause')) # Use icon

    def play_next(self):
        if not self.current_song_path or not self.shown_file_paths:
            return
        try:
            curr_idx = self.shown_file_paths.index(self.current_song_path)
            next_idx = (curr_idx + 1) % len(self.shown_file_paths)
            self.load_and_play(self.shown_file_paths[next_idx])
            self.tree.selection_set(self.shown_file_paths[next_idx])
            self.tree.see(self.shown_file_paths[next_idx])
        except ValueError:
            pass

    def play_prev(self):
        if not self.current_song_path or not self.shown_file_paths:
            return
        try:
            curr_idx = self.shown_file_paths.index(self.current_song_path)
            prev_idx = (curr_idx - 1) % len(self.shown_file_paths)
            self.load_and_play(self.shown_file_paths[prev_idx])
            self.tree.selection_set(self.shown_file_paths[prev_idx])
            self.tree.see(self.shown_file_paths[prev_idx])
        except ValueError:
            pass

    def seek_song(self, value):
        if self.current_song_path:
            pygame.mixer.music.set_pos(float(value))

    def set_volume(self, value):
        vol = float(value) / 100
        pygame.mixer.music.set_volume(vol)

    def update_player_progress(self):
        if self.is_playing and pygame.mixer.music.get_busy():
            # Note: get_pos returns millis played since start/play, not absolute pos if seeked on some platforms,
            # but it is decent for display. Accuracy in pygame seek can be tricky.
            # Ideally: internal_timer + delta
            pass
            # Pygame get_pos is notoriously unreliable for seeking.
            # Simplified: just auto-advance if not dragging? 
            # Tkinter scale update might conflict with drag.
            # For now, let's just create a basic incrementer or rely on user dragging.
            pass
        self.root.after(1000, self.update_player_progress)


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
        
        # Reset progress
        self.lbl_status.config(text="Processando metadados...")
        self.progress['value'] = 0
        self.root.update_idletasks()

        def process_in_thread():
            updated_count = 0
            error_count = 0
            file_list = list(self.file_data.keys())
            total_files = len(file_list)

            for i, file_path in enumerate(file_list):
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
                
                # Update progress periodically
                if i % 5 == 0 or i == total_files - 1:
                    progress_val = ((i + 1) / total_files) * 100
                    msg = f"Processando {i + 1} de {total_files}..."
                    self.root.after(0, lambda v=progress_val, m=msg: self._update_progress(v, m))

            # Show completion message
            self.root.after(0, lambda: self._populate_completed())
            self.root.after(0, lambda: messagebox.showinfo("Concluído",
                f"Metadados criados para {updated_count} arquivo(s).\n{error_count} arquivo(s) com formato não reconhecido."))

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
        
        # Reset progress
        self.lbl_status.config(text="Removendo metadados...")
        self.progress['value'] = 0
        self.root.update_idletasks()

        def process_in_thread():
            success_count = 0
            error_count = 0
            file_list = list(self.file_data.keys())
            total_files = len(file_list)

            for i, file_path in enumerate(file_list):
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
                
                # Update progress
                if i % 10 == 0 or i == total_files - 1:
                    progress_val = ((i + 1) / total_files) * 100
                    msg = f"Removendo {i + 1} de {total_files}..."
                    self.root.after(0, lambda v=progress_val, m=msg: self._update_progress(v, m))

            # Show completion message
            self.root.after(0, lambda: self._populate_completed())
            self.root.after(0, lambda: messagebox.showinfo("Concluído",
                f"Metadados removidos de {success_count} arquivo(s).\n{error_count} erro(s)."))

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
