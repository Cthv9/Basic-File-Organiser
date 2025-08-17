#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Organizer (GUI) - v3
New: "Extension + Date" and "Extension only" schemes, e.g. xls/2025/06/file.xls
Other features kept:
- Choose source/destination
- Copy or Move
- Dry-run
- Organize by Date, Category, Category + Date, Extension only, Extension + Date
- Date source: Created or Modified
- Sanitize filenames (Windows-invalid chars, trailing dot/space)
- Add missing extension by signature detection (common types)
- Avoid overwrites (auto " (1)", " (2)")
- Long path support (Windows)
- Log to UI and to organizer_log.txt in destination
"""

import os
import shutil
import time
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

IS_WINDOWS = os.name == "nt"

def longpath(p: Path) -> str:
    s = str(p)
    if IS_WINDOWS:
        if s.startswith('\\\\?\\'):
            return s
        if s.startswith('\\\\'):
            return '\\\\?\\UNC\\' + s.lstrip('\\')
        return '\\\\?\\' + s
    return s

INVALID_CHARS = set('<>:"/\\|?*')

def sanitize_name(name: str) -> str:
    cleaned = ''.join('_' if ch in INVALID_CHARS else ch for ch in name)
    cleaned = cleaned.rstrip('. ').strip()
    if not cleaned:
        cleaned = '_file'
    return cleaned

def unique_path(target: Path) -> Path:
    candidate = target
    stem = candidate.stem
    suf = candidate.suffix
    i = 1
    while True:
        try:
            exists = candidate.exists()
        except OSError:
            exists = os.path.exists(str(candidate))
        if not exists:
            return candidate
        candidate = candidate.with_name(f"{stem} ({i}){suf}")
        i += 1

# Categories (kept for Category schemes)
CATEGORY_MAP = {
    "Images": {'.jpg','.jpeg','.png','.gif','.bmp','.tif','.tiff','.webp','.heic','.heif','.svg','.raw','.cr2','.nef','.rw2'},
    "Videos": {'.mp4','.mov','.mkv','.avi','.wmv','.mts','.m2ts','.3gp','.m4v','.webm'},
    "Audio":  {'.mp3','.wav','.flac','.ogg','.m4a','.aac','.wma','.aiff','.alac'},
    "Documents": {'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.rtf','.csv','.md','.odt','.ods','.odp'},
    "Archives": {'.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.iso'},
    "Code": {'.py','.js','.ts','.tsx','.jsx','.html','.css','.json','.xml','.yaml','.yml','.sql','.sh','.bat','.ps1'},
    "Executables": {'.exe','.msi','.apk','.dmg','.app','.pkg'},
}

def categorize(ext: str) -> str:
    e = ext.lower()
    for cat, exts in CATEGORY_MAP.items():
        if e in exts:
            return cat
    return "Other"

# Signature-based extension detection for missing extensions
def detect_ext_from_signature(path: Path) -> str | None:
    try:
        with open(longpath(path), 'rb', buffering=0) as f:
            head = f.read(2048)
    except Exception:
        return None
    if len(head) < 4:
        return None
    ascii64 = head[:64]

    # images
    if head.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if ascii64.startswith(b'GIF87a') or ascii64.startswith(b'GIF89a'):
        return '.gif'
    if head.startswith(b'BM'):
        return '.bmp'
    # ISO-BMFF (mp4/mov/heic)
    if len(head) >= 12 and ascii64[4:8] == b'ftyp':
        if b'ftypheic' in ascii64 or b'ftypheif' in ascii64 or b'ftypheix' in ascii64 or b'ftyphevc' in ascii64 or b'ftypmif1' in ascii64 or b'ftypmsf1' in ascii64:
            return '.heic'
        if b'ftypqt' in ascii64:
            return '.mov'
        return '.mp4'
    # video
    if head.startswith(bytes.fromhex('1A45DFA3')):
        return '.mkv'
    # docs/archives
    if head.startswith(b'%PDF'):
        return '.pdf'
    if head.startswith(b'PK\x03\x04'):
        import zipfile
        try:
            with zipfile.ZipFile(longpath(path), 'r') as z:
                names = z.namelist()[:32]
                joined = ' '.join(names)
                if 'word/' in joined:
                    return '.docx'
                if 'xl/' in joined:
                    return '.xlsx'
                if 'ppt/' in joined:
                    return '.pptx'
        except Exception:
            pass
        return '.zip'
    if head.startswith(b'Rar!\x1a\x07\x00'):
        return '.rar'
    if head.startswith(bytes.fromhex('377ABCAF271C')):
        return '.7z'
    if head.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
        return '.doc'
    # audio
    if head.startswith(b'ID3') or head[:2] == b'\xff\xfb':
        return '.mp3'
    if head.startswith(b'OggS'):
        return '.ogg'
    if head.startswith(b'fLaC'):
        return '.flac'
    if head.startswith(b'RIFF') and head[8:12] == b'WAVE':
        return '.wav'
    return None

def add_extension_if_missing(path: Path, dry_run: bool) -> Path:
    if path.suffix:
        return path
    ext = detect_ext_from_signature(path)
    if not ext:
        return path
    new_path = path.with_name(path.name + ext)
    if new_path.exists():
        new_path = unique_path(new_path)
    if not dry_run:
        os.replace(longpath(path), longpath(new_path))
    return new_path

# Date helpers
def get_dates(path: Path) -> tuple[float, float]:
    try:
        stat = path.stat()
    except Exception:
        stat = os.stat(str(path))
    mtime = stat.st_mtime
    if IS_WINDOWS and hasattr(stat, 'st_ctime'):
        ctime = stat.st_ctime
    else:
        ctime = mtime
    return (ctime, mtime)

def subfolder_by_date(path: Path, date_source: str, granularity: str) -> str:
    cts, mts = get_dates(path)
    ts = cts if date_source == 'Created' else mts
    dt = datetime.fromtimestamp(ts)
    if granularity == 'YYYY/MM/DD':
        return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}"
    return f"{dt.year:04d}/{dt.month:02d}"

# Core
def process_file(src: Path, dest_root: Path, scheme: str, date_source: str, granularity: str, do_move: bool, sanitize: bool, add_missing_ext: bool, dry_run: bool, log):
    try:
        current = src

        # Sanitize
        if sanitize:
            cleaned = sanitize_name(current.name)
            if cleaned != current.name:
                proposed = current.with_name(cleaned)
                if proposed.exists():
                    proposed = unique_path(proposed)
                if not dry_run:
                    os.replace(longpath(current), longpath(proposed))
                log(f"[RENAME] {current} -> {proposed}")
                current = proposed

        # Add extension if missing
        if add_missing_ext:
            new_current = add_extension_if_missing(current, dry_run)
            if new_current != current:
                log(f"[EXT]    {current} -> {new_current}")
                current = new_current

        # Build destination path according to scheme
        ext = (current.suffix or "").lower().lstrip('.')
        category = categorize(current.suffix)

        if scheme == "Date only (YYYY/MM)":
            sub = subfolder_by_date(current, date_source, granularity)
        elif scheme == "Category only":
            sub = category
        elif scheme == "Category + Date":
            sub = category + "/" + subfolder_by_date(current, date_source, granularity)
        elif scheme == "Extension only":
            sub = ext if ext else "_noext"
        else:  # "Extension + Date"
            ext_folder = ext if ext else "_noext"
            sub = ext_folder + "/" + subfolder_by_date(current, date_source, granularity)

        target_dir = dest_root / sub
        target_path = target_dir / current.name
        if target_path.exists():
            target_path = unique_path(target_path)

        if dry_run:
            op = "MOVE" if do_move else "COPY"
            log(f"[{op}]   {current} -> {target_path}")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            if do_move:
                shutil.move(longpath(current), longpath(target_path))
            else:
                shutil.copy2(longpath(current), longpath(target_path))
            log(f"OK {('MOVE' if do_move else 'COPY')}: {current} -> {target_path}")
    except Exception as e:
        log(f"ERR: {src} -> {e}")

# GUI
class OrganizerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Organizer | By DF")
        self.geometry("840x640")
        self.minsize(780, 560)

        # Vars
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.move_var = tk.BooleanVar(value=True)
        self.dry_var  = tk.BooleanVar(value=True)
        self.sanitize_var = tk.BooleanVar(value=True)
        self.addext_var   = tk.BooleanVar(value=True)
        self.date_var = tk.StringVar(value="Created" if IS_WINDOWS else "Modified")
        self.gran_var = tk.StringVar(value="YYYY/MM")
        self.scheme_var = tk.StringVar(value="Extension + Date")

        pad = {'padx': 8, 'pady': 6}
        frm = ttk.Frame(self); frm.pack(fill='both', expand=True, **pad)

        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Source folder:").pack(side='left')
        ttk.Entry(row, textvariable=self.src_var, width=78).pack(side='left', padx=6)
        ttk.Button(row, text="Browse", command=self.pick_src).pack(side='left')

        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Destination:  ").pack(side='left')
        ttk.Entry(row, textvariable=self.dst_var, width=78).pack(side='left', padx=6)
        ttk.Button(row, text="Browse", command=self.pick_dst).pack(side='left')

        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Organization:").pack(side='left')
        ttk.Combobox(row, textvariable=self.scheme_var,
                     values=["Extension + Date", "Category + Date", "Date only (YYYY/MM)",
                             "Extension only", "Category only"],
                     width=28, state="readonly").pack(side='left', padx=4)

        ttk.Label(row, text="Date:").pack(side='left')
        ttk.Combobox(row, textvariable=self.date_var, values=["Created", "Modified"], width=12, state="readonly").pack(side='left', padx=4)

        ttk.Label(row, text="Subfolders:").pack(side='left')
        ttk.Combobox(row, textvariable=self.gran_var, values=["YYYY/MM", "YYYY/MM/DD"], width=12, state="readonly").pack(side='left', padx=4)

        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Radiobutton(row, text="Move", variable=self.move_var, value=True).pack(side='left', padx=4)
        ttk.Radiobutton(row, text="Copy", variable=self.move_var, value=False).pack(side='left', padx=4)
        ttk.Checkbutton(row, text="Dry run (no changes)", variable=self.dry_var).pack(side='left', padx=8)
        ttk.Checkbutton(row, text="Sanitize filenames", variable=self.sanitize_var).pack(side='left', padx=8)
        ttk.Checkbutton(row, text="Add missing extension", variable=self.addext_var).pack(side='left', padx=8)

        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Button(row, text="Run", command=self.run).pack(side='left')
        ttk.Button(row, text="Stop", command=self.stop).pack(side='left', padx=6)
        ttk.Button(row, text="Clear Log", command=lambda: self.log_text.delete('1.0','end')).pack(side='left', padx=6)

        self.log_text = tk.Text(frm, height=18, wrap='none')
        self.log_text.pack(fill='both', expand=True, **pad)
        yscroll = ttk.Scrollbar(self.log_text, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side='right', fill='y')

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, anchor='w').pack(fill='x')

        self._stop = False

    def pick_src(self):
        d = filedialog.askdirectory(title="Select source folder")
        if d: self.src_var.set(d)

    def pick_dst(self):
        d = filedialog.askdirectory(title="Select destination folder")
        if d: self.dst_var.set(d)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"{ts}  {msg}\n"
        self.log_text.insert('end', line); self.log_text.see('end')
        dst = self.dst_var.get().strip()
        if dst:
            try:
                Path(dst).mkdir(parents=True, exist_ok=True)
                with open(Path(dst) / "organizer_log.txt", "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass

    def run(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not dst:
            messagebox.showerror("Error", "Please set both source and destination folders."); return
        src_path = Path(src); dst_path = Path(dst)
        if not src_path.exists():
            messagebox.showerror("Error", f"Source does not exist:\n{src_path}"); return
        if src_path.resolve() == dst_path.resolve():
            messagebox.showerror("Error", "Source and destination must be different."); return

        dry = self.dry_var.get()
        do_move = self.move_var.get()
        sanitize = self.sanitize_var.get()
        addext = self.addext_var.get()
        date_source = self.date_var.get()
        gran = self.gran_var.get()
        scheme = self.scheme_var.get()

        self._stop = False
        self.status.set("Running...")
        self.log(f"START  src={src_path}  dst={dst_path}  op={'MOVE' if do_move else 'COPY'}  dry={dry}  scheme={scheme}  date={date_source}  sub={gran}  sanitize={sanitize}  addext={addext}")

        count = 0
        for root, dirs, files in os.walk(src_path):
            if self._stop: break
            # Skip dest if nested
            try:
                if str(dst_path).startswith(str(src_path)) and str(Path(root)).startswith(str(dst_path)):
                    continue
            except Exception:
                pass
            for fname in files:
                if self._stop: break
                process_file(Path(root)/fname, dst_path, scheme, date_source, gran, do_move, sanitize, addext, dry, self.log)
                count += 1
                if count % 200 == 0:
                    self.status.set(f"Processed {count} files..."); self.update_idletasks()

        self.status.set(f"Finished. Processed {count} files.")
        self.log(f"FINISH total={count}")

    def stop(self):
        self._stop = True
        self.status.set("Stopping..."); self.log("STOP requested by user.")

def main():
    app = OrganizerGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
