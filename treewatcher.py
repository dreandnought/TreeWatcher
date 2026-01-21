import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import sys
import os
import json

class TreeWatcherApp(tb.Window):
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("TreeWatcher")
        self.geometry("800x600")
        
        # Set icon
        icon_path = self.resource_path("tree.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
            
        # Load configuration
        self.load_config()
        
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Progress Bar (very thin at top)
        # Configure a specific style for a thin blue progress bar
        # 'primary' is usually blue in Cosmo theme
        self.style.configure('Thin.primary.Horizontal.TProgressbar', thickness=3)
        
        self.progress = tb.Progressbar(self, orient=HORIZONTAL, mode='determinate', style='Thin.primary.Horizontal.TProgressbar')
        self.progress.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        # Usage Label
        usage_label = tb.Label(self, text='usage: tree /F > "D:\\tree_output.txt"', bootstyle="info")
        usage_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))

        # Header
        header_frame = tb.Frame(self)
        header_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        self.path_label = tb.Label(header_frame, text="File: Not loaded")
        self.path_label.pack(side=LEFT, fill=X, expand=YES)
        
        # Changed button from Reload to Load
        load_btn = tb.Button(header_frame, text="Load", bootstyle="primary", command=self.open_file_dialog)
        load_btn.pack(side=RIGHT)

        # Treeview
        tree_frame = tb.Frame(self)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        
        # Add scrollbars
        vsb = tb.Scrollbar(tree_frame, orient="vertical")
        hsb = tb.Scrollbar(tree_frame, orient="horizontal")
        
        self.tree = ttk.Treeview(
            tree_frame, 
            selectmode="browse", 
            yscrollcommand=vsb.set, 
            xscrollcommand=hsb.set
        )
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=YES)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tb.Label(self, textvariable=self.status_var, bootstyle="secondary")
        status_bar.grid(row=4, column=0, sticky="ew", padx=10, pady=2)

        # Load file immediately
        self.after(100, self.load_default_file)
        
    def load_config(self):
        # Determine config path
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            
        config_path = os.path.join(app_dir, "config.json")
        
        # Default icons
        self.file_icon = "📄"
        self.folder_icon = "📂"
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.file_icon = config.get("file_icon", self.file_icon)
                    self.folder_icon = config.get("folder_icon", self.folder_icon)
            except Exception as e:
                print(f"Error loading config: {e}")
        else:
            # Create default config
            try:
                default_config = {
                    "file_icon": self.file_icon,
                    "folder_icon": self.folder_icon
                }
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error creating config: {e}")

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def load_default_file(self):
        # Default path relative to script or executable
        if getattr(sys, 'frozen', False):
            # If frozen (exe), use the directory of the executable for the txt file
            script_dir = os.path.dirname(sys.executable)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
        file_path = os.path.join(script_dir, "tree_output.txt")
        
        # Only load if exists, otherwise do nothing (user can use Load button)
        if os.path.exists(file_path):
            self.load_tree_from_file(file_path)
        else:
            self.status_var.set("Default file not found. Please load manually.")

    def open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Select Tree Output File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.load_tree_from_file(file_path)

    def load_tree_from_file(self, file_path):
        self.status_var.set(f"Loading {file_path}...")
        self.path_label.config(text=f"File: {file_path}")
        
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # Try decoding with utf-8 first, then gbk (common for Windows cmd output)
            content = []
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.readlines()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.readlines()
            
            if not content:
                self.status_var.set("File is empty")
                return

            self.parse_and_build_tree(content)
            self.status_var.set(f"Loaded {len(content)} lines.")
            
        except Exception as e:
            self.status_var.set(f"Error loading file: {str(e)}")
            messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")



    def parse_line(self, line):
        # Calculate depth based on 4-char chunks
        # Standard tree output uses box-drawing characters:
        # "│   " (vertical bar + 3 spaces)
        # "    " (4 spaces)
        # "├── " (tee + 2 dashes + space)
        # "└── " (corner + 2 dashes + space)
        
        depth = 0
        idx = 0
        n = len(line)
        
        # Loop to consume indentation chunks.
        # We handle standard 4-char chunks but also robustly handle cases where
        # text might start earlier (e.g. malformed or compact tree output).
        while idx < n:
             # If near end, check remaining
             if idx + 4 > n:
                 break
                 
             chunk = line[idx:idx+4]
             
             # 1. Check if chunk STARTS with connector (start of name)
             if chunk.startswith("├") or chunk.startswith("└") or chunk.startswith("+") or chunk.startswith("\\"):
                 break
                 
             # 2. Check if chunk starts with spacer char
             if chunk.startswith("│") or chunk.startswith("|") or chunk.startswith(" "):
                 found_name_char = False
                 safe_len = 4
                 
                 compressed_indent = False
                 for i, char in enumerate(chunk):
                     if char in ["│", "|", " "]:
                         if i > 0 and char in ["│", "|"]:
                             # Compressed indentation detected (e.g. "│  │").
                             # The second bar starts a new level.
                             safe_len = i
                             compressed_indent = True
                             break
                         continue
                     elif char in ["├", "└", "+", "\\"]:
                        # Connector found inside chunk (e.g. "│ └─").
                        found_name_char = True
                        safe_len = i 
                        break
                     else:
                         # Found a char that is neither spacer nor connector (part of name)
                         found_name_char = True
                         safe_len = i 
                         break
                 
                 if compressed_indent:
                     depth += 1
                     idx += safe_len
                     # Continue parsing next chunk (don't break)
                 elif found_name_char:
                     depth += 1
                     idx += safe_len
                     break # Stop parsing indentation, name starts immediately
                 else:
                     # Standard spacer block
                     depth += 1
                     idx += 4
                         
             else:
                 # Not spacer, not connector -> Name starts here.
                 break

        # Extract name part
        name = line[idx:]
        
        # Check if the name part is actually just a spacer line or empty
        stripped_name = name.strip()
        if not stripped_name:
            return depth, None, False
        if stripped_name == "│" or stripped_name == "|":
            return depth, None, False
            
        # Common prefixes to strip
        # Note: Order matters. Longer prefixes first.
        prefixes = ["├── ", "└── ", "├──", "└──", "+---", "\\---", "└─ ", "├─ ", "└─", "├─"]
        found_prefix = False
        for p in prefixes:
            if name.startswith(p):
                name = name[len(p):]
                found_prefix = True
                break
        
        # If we didn't find a standard connector prefix, but the name starts with a vertical bar,
        # it's likely a spacer line that wasn't consumed by the chunk loop
        if not found_prefix:
            if name.startswith("│") or name.startswith("|"):
                 return depth, None, False
            # Check for potential malformed prefix remnants
            if name.startswith("─ "):
                name = name[2:]
            elif name.startswith("─"):
                 name = name[1:]

        return depth, name, False

    def parse_and_build_tree(self, lines):
        # Stack to keep track of (item_id, depth)
        # Root is assumed to be depth 0
        stack = [] 
        
        # Skip header lines if they are detected as non-tree lines
        # Heuristic: look for the first line that looks like a root (no indentation chars usually)
        # or standard "Folder PATH listing" header.
        
        start_index = 0
        for i, line in enumerate(lines):
            if "PATH" in line and "listing" in line:
                continue
            if "Volume serial number" in line:
                continue
            # Found potential root or first item
            start_index = i
            break
            
        # Process the root (first valid line)
        if start_index < len(lines):
            root_line = lines[start_index].rstrip()
            root_text = root_line
            # Root usually has no prefix in tree /F /A output, e.g. "D:."
            root_id = self.tree.insert("", "end", text=f"{self.folder_icon} {root_text}", open=True)
            stack.append({"id": root_id, "depth": 0})
            start_index += 1

        # Setup progress bar
        total_lines = len(lines) - start_index
        self.progress['maximum'] = total_lines
        self.progress['value'] = 0
        update_interval = max(1, total_lines // 100) # Update every 1% or at least every 1 line
        
        processed_count = 0

        for i in range(start_index, len(lines)):
            # Update progress
            processed_count += 1
            if processed_count % update_interval == 0:
                self.progress['value'] = processed_count
                self.update_idletasks() # Allow UI to update
            
            line = lines[i].rstrip()
            if not line:
                continue

            depth, name, is_last_child = self.parse_line(line)
            
            # If name is None, it's a spacer line, skip it
            if name is None:
                continue
            
            # Formatting text
            display_text = name
            
            # Find parent
            # We need to find the node in stack with depth == current_depth - 1
            # Pop stack until we find the parent
            while stack and stack[-1]["depth"] >= depth:
                stack.pop()
            
            if stack:
                parent_id = stack[-1]["id"]
            else:
                # Should not happen if root is parsed correctly, fallback to root
                parent_id = "" 
            
            # Insert item
            # We don't know if it's a folder or file yet, but we can guess or update later.
            # In tree /F, both files and folders are listed.
            # We can't distinguish purely by line content easily without lookahead.
            # But we can use a generic icon for now.
            # Or heuristic: if the name has an extension, maybe file? Not reliable.
            # We will default to "File" icon, and if it becomes a parent later (has children), update icon?
            # Treeview doesn't support updating text easily based on children existence during parse
            # unless we do 2 passes.
            # For now, let's use a generic node icon or assume file.
            # Better: Use "📄" for everything, then if we add a child to it, change it to "📂"?
            # Tkinter Treeview item update: tree.item(item_id, text="new text")
            
            item_id = self.tree.insert(parent_id, "end", text=f"{self.file_icon} {display_text}", open=False)
            stack.append({"id": item_id, "depth": depth})
            
            # Check if parent needs to be marked as folder
            if parent_id:
                parent_text = self.tree.item(parent_id, "text")
                if parent_text.startswith(self.file_icon):
                    new_text = parent_text.replace(self.file_icon, self.folder_icon, 1)
                    self.tree.item(parent_id, text=new_text)

        # Final progress update
        self.progress['value'] = total_lines
        self.update_idletasks()

if __name__ == "__main__":
    app = TreeWatcherApp()
    app.mainloop()
