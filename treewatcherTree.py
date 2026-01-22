import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import sys
import os
import threading
import treewatcher  # Import the original module to reuse classes and methods

class TreeNode:
    """
    A simple Tree Data Structure to hold directory information.
    """
    def __init__(self, name, depth):
        self.name = name
        self.depth = depth
        self.children = []  # List of TreeNode

    @property
    def is_folder(self):
        """
        Heuristic: If it has children, it's definitely a folder.
        If no children, it might be a file or an empty folder.
        """
        return len(self.children) > 0

    def add_child(self, node):
        self.children.append(node)

class PeekableIterator:
    """
    An iterator wrapper that allows peeking at the next item without consuming it.
    """
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.peeked_item = None
        self.has_peeked = False

    def peek(self):
        if not self.has_peeked:
            try:
                self.peeked_item = next(self.iterator)
                self.has_peeked = True
            except StopIteration:
                return None
        return self.peeked_item

    def next(self):
        if self.has_peeked:
            self.has_peeked = False
            return self.peeked_item
        return next(self.iterator)

    def __iter__(self):
        return self

class RecursiveTreeWatcherApp(treewatcher.TreeWatcherApp):
    """
    Refactored TreeWatcherApp using a Tree data structure and recursive building logic.
    """
    def __init__(self):
        # Initialize the parent class
        super().__init__()
        self.title("TreeWatcher (Recursive Tree Structure)")
        
        # --- UI Adjustment for Phase Label ---
        self.phase_label = tb.Label(self, text="Ready", font=("Helvetica", 8), bootstyle="secondary")
        self.phase_label.grid(row=1, column=0, sticky="ew", padx=10, pady=0)
        
        # Shift existing widgets down
        slaves = self.grid_slaves()
        for widget in slaves:
            info = widget.grid_info()
            row = int(info['row'])
            if widget == self.phase_label:
                continue
            if row >= 1:
                widget.grid(row=row + 1)
                
        # Configure row weights
        self.grid_rowconfigure(3, weight=0) # Reset old
        self.grid_rowconfigure(4, weight=1) # Set new

        # --- Lazy Loading Setup ---
        # Map item_id (str) -> TreeNode (obj)
        self.node_map = {}
        # Bind expand event
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        
    def safe_update_status(self, message, value=None, maximum=None):
        """Thread-safe helper to update status label and progress bar"""
        def _update():
            self.phase_label.config(text=message)
            if maximum is not None:
                self.progress['maximum'] = maximum
            if value is not None:
                self.progress['value'] = value
        self.after(0, _update)

    def parse_and_build_tree(self, lines):
        """
        Override the iterative parsing with a recursive approach, running in a background thread.
        """
        # Start background thread
        thread = threading.Thread(target=self._parse_and_build_tree_thread, args=(lines,))
        thread.daemon = True
        thread.start()

    def _parse_and_build_tree_thread(self, lines):
        """
        Background thread logic for parsing and building the tree.
        """
        # 1. Pre-process: Identify the start of the tree (Root)
        start_index = 0
        for i, line in enumerate(lines):
            if "PATH" in line and "listing" in line:
                continue
            if "Volume serial number" in line:
                continue
            start_index = i
            break
            
        if start_index >= len(lines):
            self.after(0, lambda: self.status_var.set("No tree structure found."))
            return

        # --- Phase 1: Parsing Lines ---
        total_lines = len(lines) - start_index
        self.safe_update_status(f"Phase 1/3: Reading and Parsing lines... 0/{total_lines}", 0, total_lines)
        
        parsed_items = []
        
        # Root handling
        root_line = lines[start_index].rstrip()
        parsed_items.append((0, root_line))
        
        for i in range(start_index + 1, len(lines)):
            # Update progress less frequently to reduce overhead
            if i % 1000 == 0:
                current = i - start_index
                self.safe_update_status(f"Phase 1/3: Reading and Parsing lines... {current}/{total_lines}", current)

            line = lines[i].rstrip()
            if not line:
                continue
            
            # Note: parse_line is pure logic, safe to run in thread
            depth, name, _ = self.parse_line(line)
            
            if name is not None:
                parsed_items.append((depth, name))

        self.safe_update_status(f"Phase 1/3: Reading and Parsing lines... {total_lines}/{total_lines}", total_lines)

        # --- Phase 2: Building Tree Structure ---
        total_items = len(parsed_items)
        self.safe_update_status("Phase 2/3: Building Tree Structure...", 0, total_items)
        
        iterator = PeekableIterator(parsed_items)
        
        # Counter for progress in recursion (mutable list)
        build_counter = [0]
        
        # We start building from depth 0. 
        roots = self._build_tree_recursive(iterator, min_depth=0, counter=build_counter, total=total_items)
        
        self.safe_update_status("Phase 2/3: Building Tree Structure... Done", total_items)
        
        # --- Schedule Phase 3 on Main Thread ---
        self.after(0, lambda: self._finalize_tree_population(roots, total_lines))

    def _build_tree_recursive(self, iterator, min_depth, counter=None, total=0):
        """
        Recursively consumes items from the iterator to build a list of sibling nodes.
        Running in background thread.
        """
        nodes = []
        
        while True:
            item = iterator.peek()
            if item is None:
                break
                
            depth, name = item
            
            if depth < min_depth:
                break
            
            iterator.next()
            node = TreeNode(name, depth)
            
            # Update progress
            if counter:
                counter[0] += 1
                if counter[0] % 2000 == 0: # Update less frequently for better performance
                     self.safe_update_status(f"Phase 2/3: Building Tree Structure... {counter[0]}/{total}", counter[0])
            
            node.children = self._build_tree_recursive(iterator, depth + 1, counter, total)
            
            nodes.append(node)
            
        return nodes

    def _finalize_tree_population(self, roots, total_lines):
        """
        Phase 3: Populating UI (Lazy Loading).
        Must run on Main Thread.
        """
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            self.node_map.clear() # Clear memory map
            
        self.phase_label.config(text=f"Phase 3/3: Initializing Root Nodes... 0/{len(roots)}")
        
        # Only insert top-level nodes (Roots)
        for i, root in enumerate(roots):
            self._insert_node_lazy(root, "")
            self.phase_label.config(text=f"Phase 3/3: Initializing Root Nodes... {i+1}/{len(roots)}")
            
        self.phase_label.config(text="Done")
        self.status_var.set(f"Loaded {total_lines} lines (Recursive, Lazy, Threaded).")
        self.progress['value'] = self.progress['maximum']

    def _insert_node_lazy(self, node, parent_id):
        """
        Inserts a single node into the treeview.
        If it has children, inserts a dummy child to enable the expand button.
        """
        # Determine icon
        if node.is_folder:
            icon = self.folder_icon
        else:
            icon = self.get_file_icon(node.name)
            
        display_text = f"{icon} {node.name}"
        
        # Insert item
        item_id = self.tree.insert(parent_id, "end", text=display_text, open=False)
        
        # Store in map
        self.node_map[item_id] = node
        
        # If folder, add dummy child to make it expandable
        if node.is_folder:
            # We use a special ID or text to identify it as dummy if needed, 
            # but usually just checking if children exist is enough.
            self.tree.insert(item_id, "end", text="Loading...", open=False)

    def on_tree_open(self, event):
        """
        Event handler for node expansion.
        Replaces dummy child with actual children.
        """
        item_id = self.tree.focus()
        if not item_id:
            # Sometimes focus is not set correctly on click, try selection
            selection = self.tree.selection()
            if selection:
                item_id = selection[0]
            else:
                return

        node = self.node_map.get(item_id)
        if not node:
            return

        # Check if we have a dummy child
        children_ids = self.tree.get_children(item_id)
        if len(children_ids) == 1:
            child_id = children_ids[0]
            child_text = self.tree.item(child_id, "text")
            if child_text == "Loading...":
                # Remove dummy
                self.tree.delete(child_id)
                
                # Insert actual children
                # This is fast because we only insert one level
                for child in node.children:
                    self._insert_node_lazy(child, item_id)

if __name__ == "__main__":
    app = RecursiveTreeWatcherApp()
    app.mainloop()
