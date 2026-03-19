# Organizzatore File

Strumento desktop per organizzare automaticamente i file in cartelle strutturate per estensione, categoria o data. Interfaccia grafica in italiano, nessuna dipendenza esterna richiesta per l'utilizzo dell'eseguibile.

---

## Funzionalità

- **Schemi di organizzazione** — Estensione + Data, Categoria + Data, Solo data, Solo estensione, Solo categoria
- **Sposta o Copia** — scelta tra operazione distruttiva e non
- **Simulazione** — anteprima delle operazioni senza modificare nulla (attiva per default)
- **Normalizzazione nomi file** — rimuove caratteri non validi su Windows
- **Rilevamento estensione** — aggiunge l'estensione mancante tramite analisi della firma del file
- **Esclusioni** — filtra file per pattern (es. `*.tmp`, `thumbs.db`, `desktop.ini`)
- **Barra di progresso** — avanzamento in tempo reale con conteggio file
- **Interfaccia reattiva** — elaborazione in background, la finestra non si blocca mai
- **Log completo** — su schermo e su file `organizer_log.txt` nella cartella di destinazione
- **Supporto percorsi lunghi** — gestione automatica dei percorsi oltre 260 caratteri su Windows

---

## Avvio da sorgente

**Requisiti:** Python 3.10+ e le dipendenze in `requirements.txt`.

```bash
pip install -r requirements.txt
python app/FileOrganizer.py
```

---

## Build eseguibile Windows

Per distribuire l'app ai colleghi senza installare Python:

```bash
pip install -r requirements.txt
build.bat
```

Il file `dist\OrganizzatoreFile.exe` è standalone: basta copiarlo e aprirlo, nessuna installazione richiesta.

> **Nota:** la build va eseguita su una macchina Windows con Python installato.

---

## Utilizzo

1. Seleziona la **cartella sorgente** (dove si trovano i file da organizzare)
2. Seleziona la **cartella di destinazione**
3. Scegli lo schema di organizzazione e le opzioni desiderate
4. Inserisci eventuali pattern da escludere nel campo **Escludi**
5. Lascia **Simulazione** attiva per vedere l'anteprima senza modifiche
6. Premi **Avvia** — la barra di progresso mostra l'avanzamento

---

## Categorie riconosciute

| Categoria    | Estensioni principali                              |
|--------------|----------------------------------------------------|
| Images       | jpg, jpeg, png, gif, bmp, tiff, webp, heic, raw… |
| Videos       | mp4, mov, mkv, avi, wmv, mts…                    |
| Audio        | mp3, wav, flac, ogg, m4a, aac…                   |
| Documents    | pdf, doc, docx, xls, xlsx, ppt, txt, csv…        |
| Archives     | zip, rar, 7z, tar, gz, iso…                       |
| Code         | py, js, ts, html, css, json, sql, sh, bat…       |
| Executables  | exe, msi, apk, dmg…                               |
| Other        | tutto il resto                                     |
