#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
 
from PIL import Image, ImageOps, ImageTk
from send2trash import send2trash
 
# HEIC because I hate this format
try:
    from pillow_heif import register_heif_opener
 
    register_heif_opener()
    HEIF_EXTS = {".heic", ".heif"}
except ImportError:
    HEIF_EXTS = set()
 
IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
} | HEIF_EXTS
 
BG = "#1e1e1e"
FG = "#e6e6e6"
KEEP_COLOR = "#00ff0d"
DELETE_COLOR = "#ff0000"
 
 
def find_images(folder, recursive):
    """Return list of image file paths in folder."""
    results = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                    results.append(os.path.join(root, name))
    else:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                results.append(path)
    return sorted(results, key=lambda p: p.lower())
 
 
def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return (
                f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
            )
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
 
 
class ImageSorter:
    def __init__(self, root, start_folder=None):
        self.root = root
        self.root.title("Image Sorter")
        self.root.geometry("1000x750")
        self.root.minsize(500, 400)
        self.root.configure(bg=BG)
 
        self.folder = None
        self.images = []
        self.index = 0
        self.history = []  # list of ("keep" | "delete", path)
        self.pending_delete = []
        self.kept = 0
        self.deleted = 0
        self.current_pil = None
        self.current_tk = None
        self._resize_job = None
 
        self.recursive = tk.BooleanVar(value=False)
 
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
 
        if start_folder:
            self.load_folder(start_folder)
        else:
            self.show_message("Open folder to start")
 
    # ui
    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 0))
 
        tk.Button(top, text="Open Folder", command=self.choose_folder).pack(side="left")
        tk.Checkbutton(
            top,
            text="Include subfolders",
            variable=self.recursive,
            command=self.reload_folder,
            bg=BG,
            fg=FG,
            selectcolor=BG,
            activebackground=BG,
            activeforeground=FG,
        ).pack(side="left", padx=10)
 
        self.progress_label = tk.Label(
            top, text="", bg=BG, fg=FG, font=("Times New Roman", 11)
        )
        self.progress_label.pack(side="right")
 
        self.canvas = tk.Label(self.root, bg=BG, fg=FG, font=("Times New Roman", 14))
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", self._on_resize)
 
        self.info_label = tk.Label(
            self.root, text="", bg=BG, fg="#aaaaaa", font=("Times New Roman", 10)
        )
        self.info_label.pack(fill="x", padx=10)
 
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(pady=10)
 
        btn_opts = dict(
            width=14, height=2, font=("Times New Roman", 13, "bold"), fg="white", bd=0
        )
        self.delete_btn = tk.Button(
            bottom,
            text="Delete",
            bg=DELETE_COLOR,
            activebackground=DELETE_COLOR,
            command=self.delete,
            **btn_opts,
        )
        self.delete_btn.pack(side="left", padx=10)
 
        self.undo_btn = tk.Button(
            bottom, text="Undo", command=self.undo, width=10, height=2
        )
        self.undo_btn.pack(side="left", padx=10)
 
        self.keep_btn = tk.Button(
            bottom,
            text="Keep",
            bg=KEEP_COLOR,
            activebackground=KEEP_COLOR,
            command=self.keep,
            **{**btn_opts, "fg": "black"},
        )
        self.keep_btn.pack(side="left", padx=10)
 
        self.status_label = tk.Label(
            self.root, text="", bg=BG, fg=FG, font=("Times New Roman", 10)
        )
        self.status_label.pack(pady=(0, 8))
 
        self._set_buttons(False)
        self._update_undo()
 
    def _update_undo(self):
        self.undo_btn.config(state="normal" if self.history else "disabled")
 
    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        self.keep_btn.config(state=state)
        self.delete_btn.config(state=state)
 
    def show_message(self, text):
        self.current_pil = None
        self.canvas.config(image="", text=text)
        self.info_label.config(text="")
        self._set_buttons(False)
 
    def set_status(self, text):
        self.status_label.config(text=text)
 
    # folder loading
    def choose_folder(self):
        folder = filedialog.askdirectory(title="Choose folder of images")
        if folder:
            self.load_folder(folder)
 
    def reload_folder(self):
        if self.folder:
            self.load_folder(self.folder)
 
    def load_folder(self, folder):
        if not os.path.isdir(folder):
            messagebox.showerror("Not folder", f"{folder} is not a folder.")
            return
        self.commit_deletes()
        self.folder = folder
        self.images = find_images(folder, self.recursive.get())
        self.index = 0
        self.history.clear()
        self._update_undo()
        self.kept = self.deleted = 0
        self.set_status(f"Loaded {len(self.images)} images from {folder}")
        if not self.images:
            self.show_message("No images in folder.")
            self.progress_label.config(text="")
            return
        self.show_current()
 
    # display
    def show_current(self):
        if self.index >= len(self.images):
            self.finish()
            return
 
        path = self.images[self.index]
        self.progress_label.config(text=f"{self.index + 1} / {len(self.images)}")
 
        try:
            img = Image.open(path)
            img.load()
            img = ImageOps.exif_transpose(img)
            self.current_pil = img
            size = os.path.getsize(path)
            rel = os.path.relpath(path, self.folder)
            self.info_label.config(
                text=f"{rel}   •   {img.width}×{img.height}   •   {human_size(size)}"
            )
            self._render()
            self._set_buttons(True)
        except Exception as exc:  # unreadable  file
            self.current_pil = None
            self.canvas.config(
                image="",
                text=f"Couldn't open this file:\n{os.path.basename(path)}\n\n{exc}",
            )
            self.info_label.config(text=path)
            self._set_buttons(True)  # still allow keep/delete
 
    def _render(self):
        if self.current_pil is None:
            return
        w = max(self.canvas.winfo_width() - 4, 50)
        h = max(self.canvas.winfo_height() - 4, 50)
        img = self.current_pil.copy()
        img.thumbnail((w, h), Image.LANCZOS)
        self.current_tk = ImageTk.PhotoImage(img)
        self.canvas.config(image=self.current_tk, text="")
 
    def _on_resize(self, _event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self._render)
 
    def commit_deletes(self):
        if self.current_pil is not None:
            self.current_pil.close()
            self.current_pil = None
        failed = []
        for path in self.pending_delete:
            try:
                send2trash(os.path.abspath(path))
            except Exception as exc:
                failed.append(f"{path}: {exc}")
        self.pending_delete.clear()
        if failed:
            messagebox.showerror("Couldn't delete", "\n".join(failed))
 
    def on_close(self):
        self.commit_deletes()
        self.root.destroy()
 
    def finish(self):
        self.commit_deletes()
        self.history.clear()
        self._update_undo()
        self.progress_label.config(text=f"{len(self.images)} / {len(self.images)}")
        self.show_message(
            f"Done in folder! \n\nKept: {self.kept}\nSent to Trash: {self.deleted}\n\n"
            "Open another folder."
        )
 
    # actions
    def keep(self):
        if not self._has_current():
            return
        path = self.images[self.index]
        self.history.append(("keep", path))
        self._update_undo()
        self.kept += 1
        self.set_status(f"Kept {os.path.basename(path)}")
        self.index += 1
        self.show_current()
 
    def delete(self):
        if not self._has_current():
            return
        path = self.images[self.index]
        self.pending_delete.append(path)
        self.history.append(("delete", path))
        self._update_undo()
        self.deleted += 1
        self.set_status(f"Marked {os.path.basename(path)} for Trash")
        self.index += 1
        self.show_current()
 
    def undo(self):
        if not self.history:
            self.set_status("Nothing to undo.")
            return
        action, path = self.history.pop()
        self._update_undo()
        if action == "delete":
            self.pending_delete.remove(path)
            self.deleted -= 1
        else:
            self.kept -= 1
        self.index -= 1
        self.set_status(f"Back to {os.path.basename(path)}")
        self.show_current()
 
    def _has_current(self):
        return bool(self.images) and self.index < len(self.images)
 
 
def main():
    start = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    ImageSorter(root, start)
    root.mainloop()
 
 
if __name__ == "__main__":
    main()
 