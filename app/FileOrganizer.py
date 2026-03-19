#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Organizzatore File (GUI) - v4
Funzionalità:
- Scegli sorgente/destinazione
- Copia o Sposta
- Simulazione (dry-run)
- Organizza per Data, Categoria, Categoria + Data, Solo estensione, Estensione + Data
- Sorgente data: Creazione o Modifica
- Normalizza nomi file (caratteri non validi su Windows, punto/spazio finale)
- Aggiungi estensione mancante tramite rilevamento firma file
- Evita sovrascritture (auto " (1)", " (2)")
- Supporto percorsi lunghi (Windows)
- Esclusione file per pattern (es. *.tmp, thumbs.db)
- Barra di progresso e interfaccia reattiva (multi-thread)
- Log su UI e su organizer_log.txt nella destinazione
"""

import os
import sys
import shutil
import time
import fnmatch
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk

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

# Categorie
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

def detect_ext_from_signature(path: Path) -> str | None:
    try:
        with open(longpath(path), 'rb', buffering=0) as f:
            head = f.read(2048)
    except Exception:
        return None
    if len(head) < 4:
        return None
    ascii64 = head[:64]

    if head.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if ascii64.startswith(b'GIF87a') or ascii64.startswith(b'GIF89a'):
        return '.gif'
    if head.startswith(b'BM'):
        return '.bmp'
    if len(head) >= 12 and ascii64[4:8] == b'ftyp':
        if b'ftypheic' in ascii64 or b'ftypheif' in ascii64 or b'ftypheix' in ascii64 or b'ftyphevc' in ascii64 or b'ftypmif1' in ascii64 or b'ftypmsf1' in ascii64:
            return '.heic'
        if b'ftypqt' in ascii64:
            return '.mov'
        return '.mp4'
    if head.startswith(bytes.fromhex('1A45DFA3')):
        return '.mkv'
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

def process_file(src: Path, dest_root: Path, scheme: str, date_source: str, granularity: str, do_move: bool, sanitize: bool, add_missing_ext: bool, dry_run: bool, log):
    try:
        current = src

        if sanitize:
            cleaned = sanitize_name(current.name)
            if cleaned != current.name:
                proposed = current.with_name(cleaned)
                if proposed.exists():
                    proposed = unique_path(proposed)
                if not dry_run:
                    os.replace(longpath(current), longpath(proposed))
                log(f"[RINOMINA] {current} -> {proposed}")
                current = proposed

        if add_missing_ext:
            new_current = add_extension_if_missing(current, dry_run)
            if new_current != current:
                log(f"[EXT]      {current} -> {new_current}")
                current = new_current

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
            op = "SPOSTA" if do_move else "COPIA"
            log(f"[{op}]   {current} -> {target_path}")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            if do_move:
                shutil.move(longpath(current), longpath(target_path))
            else:
                shutil.copy2(longpath(current), longpath(target_path))
            log(f"OK {('SPOSTA' if do_move else 'COPIA')}: {current} -> {target_path}")
    except Exception as e:
        log(f"ERR: {src} -> {e}")


# Mappe display italiano <-> valore interno inglese
SCHEME_LABELS = {
    "Extension + Date":    "Estensione + Data",
    "Category + Date":     "Categoria + Data",
    "Date only (YYYY/MM)": "Solo data (AAAA/MM)",
    "Extension only":      "Solo estensione",
    "Category only":       "Solo categoria",
}
SCHEME_LABELS_INV = {v: k for k, v in SCHEME_LABELS.items()}

DATE_LABELS = {
    "Created":  "Creazione",
    "Modified": "Modifica",
}
DATE_LABELS_INV = {v: k for k, v in DATE_LABELS.items()}


# GUI
class OrganizerGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="litera")
        self.title("Organizzatore File | By DF")
        self.geometry("880x700")
        self.minsize(820, 600)

        # Vars
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.move_var = tk.BooleanVar(value=True)
        self.dry_var  = tk.BooleanVar(value=True)
        self.sanitize_var = tk.BooleanVar(value=True)
        self.addext_var   = tk.BooleanVar(value=True)
        self.date_var = tk.StringVar(value=DATE_LABELS["Created"] if IS_WINDOWS else DATE_LABELS["Modified"])
        self.gran_var = tk.StringVar(value="YYYY/MM")
        self.scheme_var = tk.StringVar(value=SCHEME_LABELS["Extension + Date"])
        self.exclude_var = tk.StringVar()

        self._stop = False

        pad = {'padx': 8, 'pady': 5}

        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=8, pady=(8, 0))

        frm = ttk.Frame(notebook)
        notebook.add(frm, text="  Organizzatore  ")

        about_frm = ttk.Frame(notebook)
        notebook.add(about_frm, text="  Info  ")
        self._build_about(about_frm)

        # Riga sorgente
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Cartella sorgente:").pack(side='left')
        ttk.Entry(row, textvariable=self.src_var, width=72).pack(side='left', padx=6)
        ttk.Button(row, text="Sfoglia", command=self.pick_src, bootstyle="secondary").pack(side='left')

        # Riga destinazione
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Destinazione:       ").pack(side='left')
        ttk.Entry(row, textvariable=self.dst_var, width=72).pack(side='left', padx=6)
        ttk.Button(row, text="Sfoglia", command=self.pick_dst, bootstyle="secondary").pack(side='left')

        # Riga opzioni organizzazione
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Organizzazione:").pack(side='left')
        ttk.Combobox(row, textvariable=self.scheme_var,
                     values=list(SCHEME_LABELS.values()),
                     width=26, state="readonly").pack(side='left', padx=4)
        ttk.Label(row, text="Data:").pack(side='left', padx=(10, 0))
        ttk.Combobox(row, textvariable=self.date_var,
                     values=list(DATE_LABELS.values()),
                     width=12, state="readonly").pack(side='left', padx=4)
        ttk.Label(row, text="Sottocartelle:").pack(side='left', padx=(10, 0))
        ttk.Combobox(row, textvariable=self.gran_var,
                     values=["YYYY/MM", "YYYY/MM/DD"],
                     width=12, state="readonly").pack(side='left', padx=4)

        # Riga opzioni operazione
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Radiobutton(row, text="Sposta", variable=self.move_var, value=True).pack(side='left', padx=4)
        ttk.Radiobutton(row, text="Copia",  variable=self.move_var, value=False).pack(side='left', padx=4)
        ttk.Checkbutton(row, text="Simulazione (nessuna modifica)", variable=self.dry_var).pack(side='left', padx=8)
        ttk.Checkbutton(row, text="Normalizza nomi file", variable=self.sanitize_var).pack(side='left', padx=8)
        ttk.Checkbutton(row, text="Aggiungi estensione mancante", variable=self.addext_var).pack(side='left', padx=8)

        # Riga esclusioni
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        ttk.Label(row, text="Escludi:              ").pack(side='left')
        ttk.Entry(row, textvariable=self.exclude_var, width=55).pack(side='left', padx=6)
        ttk.Label(row, text="(es. *.tmp, thumbs.db, desktop.ini)", foreground="#6c757d").pack(side='left')

        # Riga pulsanti
        row = ttk.Frame(frm); row.pack(fill='x', **pad)
        self._btn_run = ttk.Button(row, text="Avvia", command=self.run, bootstyle="primary")
        self._btn_run.pack(side='left')
        ttk.Button(row, text="Interrompi", command=self.stop, bootstyle="danger-outline").pack(side='left', padx=6)
        ttk.Button(row, text="Pulisci Log",
                   command=lambda: self.log_text.delete('1.0', 'end'),
                   bootstyle="secondary-outline").pack(side='left', padx=6)

        # Barra di progresso
        self.progress = ttk.Progressbar(frm, mode='determinate', bootstyle="primary-striped")
        self.progress.pack(fill='x', padx=0, pady=(4, 0))

        # Area log
        self.log_text = tk.Text(
            frm, height=16, wrap='none',
            font=("Consolas", 9),
            bg="#f8f9fa", fg="#212529",
            relief="flat", borderwidth=1,
        )
        self.log_text.pack(fill='both', expand=True, pady=(6, 0))
        yscroll = ttk.Scrollbar(self.log_text, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side='right', fill='y')

        # Barra di stato
        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.status, anchor='w').pack(fill='x', padx=8, pady=(0, 4))

    def _build_about(self, parent):
        ttk.Label(parent, text="Organizzatore File", font=("", 13, "bold")).pack(pady=(60, 4))
        ttk.Label(parent, text="v4.0.0", foreground="#6c757d").pack()
        ttk.Label(
            parent,
            text="\nOrganizza automaticamente i file in cartelle\nper estensione, categoria o data.\n",
            justify='center',
            foreground="#6c757d",
        ).pack()
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=140, pady=12)
        ttk.Label(parent, text="Made with \u2764\ufe0f by DF", foreground="#6c757d").pack()

    def pick_src(self):
        d = filedialog.askdirectory(title="Seleziona cartella sorgente")
        if d: self.src_var.set(d)

    def pick_dst(self):
        d = filedialog.askdirectory(title="Seleziona cartella di destinazione")
        if d: self.dst_var.set(d)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"{ts}  {msg}\n"
        self.log_text.insert('end', line)
        self.log_text.see('end')
        dst = self.dst_var.get().strip()
        if dst:
            try:
                Path(dst).mkdir(parents=True, exist_ok=True)
                with open(Path(dst) / "organizer_log.txt", "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass

    # Metodi thread-safe per aggiornare la UI dal worker thread
    def _safe_log(self, msg: str):
        self.after(0, lambda: self.log(msg))

    def _safe_status(self, msg: str):
        self.after(0, lambda: self.status.set(msg))

    def _safe_progress_step(self):
        self.after(0, lambda: self.progress.step(1))

    def run(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not dst:
            messagebox.showerror("Errore", "Impostare sia la cartella sorgente che quella di destinazione.")
            return
        src_path = Path(src); dst_path = Path(dst)
        if not src_path.exists():
            messagebox.showerror("Errore", f"La cartella sorgente non esiste:\n{src_path}")
            return
        if src_path.resolve() == dst_path.resolve():
            messagebox.showerror("Errore", "Sorgente e destinazione devono essere cartelle diverse.")
            return

        dry = self.dry_var.get()
        do_move = self.move_var.get()
        sanitize = self.sanitize_var.get()
        addext = self.addext_var.get()
        date_source = DATE_LABELS_INV.get(self.date_var.get(), self.date_var.get())
        gran = self.gran_var.get()
        scheme = SCHEME_LABELS_INV.get(self.scheme_var.get(), self.scheme_var.get())
        raw_excl = self.exclude_var.get()
        exclude_patterns = [p.strip().lower() for p in raw_excl.split(',') if p.strip()]

        # Pre-conteggio per la barra di progresso
        total = sum(len(files) for _, _, files in os.walk(src_path))
        self.after(0, lambda: self.progress.configure(maximum=max(total, 1), value=0))

        self._stop = False
        self._btn_run.configure(state='disabled')
        self.status.set("In esecuzione...")
        self.log(f"INIZIO  src={src_path}  dest={dst_path}  op={'SPOSTA' if do_move else 'COPIA'}  simulazione={dry}  schema={scheme}  data={date_source}  sub={gran}  normalizza={sanitize}  estensione={addext}")

        threading.Thread(
            target=self._run_worker,
            args=(src_path, dst_path, scheme, date_source, gran, do_move, sanitize, addext, dry, exclude_patterns),
            daemon=True,
        ).start()

    def _run_worker(self, src_path, dst_path, scheme, date_source, gran, do_move, sanitize, addext, dry, exclude_patterns):
        count = 0
        for root, dirs, files in os.walk(src_path):
            if self._stop:
                break
            try:
                if str(dst_path).startswith(str(src_path)) and str(Path(root)).startswith(str(dst_path)):
                    continue
            except Exception:
                pass
            for fname in files:
                if self._stop:
                    break
                if exclude_patterns and any(fnmatch.fnmatch(fname.lower(), pat) for pat in exclude_patterns):
                    continue
                process_file(Path(root) / fname, dst_path, scheme, date_source, gran, do_move, sanitize, addext, dry, self._safe_log)
                count += 1
                self._safe_progress_step()
                if count % 200 == 0:
                    self._safe_status(f"Elaborati {count} file...")

        if self._stop:
            self._safe_log("Arresto richiesto dall'utente.")
            self.after(0, lambda: self.status.set("Interruzione completata."))
        else:
            self.after(0, lambda c=count: self.status.set(f"Completato. Elaborati {c} file."))
            self._safe_log(f"FINE totale={count}")

        self.after(0, lambda: [
            self._btn_run.configure(state='normal'),
            self.progress.configure(value=0),
        ])

    def stop(self):
        self._stop = True
        self.status.set("Interruzione in corso...")


def main():
    app = OrganizerGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
