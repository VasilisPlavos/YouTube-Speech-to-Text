# Local watch-folder transcription pipeline — Design

**Branch:** `support-local-in-out`
**Date:** 2026-06-24
**Status:** Approved (pending implementation plan)

## Overview

Προσθήκη ενός **watch-folder pipeline** στο υπάρχον FastAPI service. Το container κάνει
mount έναν host φάκελο· μέσα του υπάρχει υποφάκελος `in/`. Κάθε αρχείο ήχου ή βίντεο που
εμφανίζεται στο `in/` ανιχνεύεται αυτόματα, μεταγράφεται τοπικά με Whisper σε ένα `.md`
αρχείο, και στη συνέχεια **το πρωτότυπο μαζί με το `.md`** μετακινούνται στο `out/`.

Το feature **συνυπάρχει** με το υπάρχον YouTube HTTP endpoint (`GET /yt/{id}`) στο **ίδιο
container** — ο watcher ξεκινά στο startup του app, το HTTP API παραμένει αμετάβλητο.

## Goals

- Αυτόματη, χωρίς ανθρώπινη παρέμβαση, μεταγραφή τοπικών αρχείων ήχου/βίντεο.
- Επαναχρησιμοποίηση της υπάρχουσας μηχανής μεταγραφής (Whisper μέσω `SpeechRecognition`).
- Καθαρός κύκλος ζωής αρχείων: `in/ → out/` σε επιτυχία, `in/ → error/` σε αποτυχία.
- Εγγυημένη εκκαθάριση προσωρινών αρχείων ακόμη κι όταν η διαδικασία σκάει.

## Non-goals

- Καμία αλλαγή στη συμπεριφορά του YouTube HTTP endpoint.
- Όχι database, όχι message queue, όχι websockets — μένουμε στο υπάρχον "files on disk" στυλ.
- Όχι retry λογική σε αποτυχίες (ένα πέρασμα· αποτυχία → `error/`).
- Όχι παράλληλη επεξεργασία (σειριακά, ένα αρχείο τη φορά).

## Folder layout

Το container κάνει mount **έναν** host φάκελο στο `/data` (path παραμετροποιήσιμο μέσω env
`WATCH_DIR`, default `/data`). Στο startup δημιουργούνται αν λείπουν:

```
/data
├── in/        # ο χρήστης ρίχνει εδώ audio/video αρχεία
├── out/       # επιτυχημένα: <name>.<ext> (πρωτότυπο) + <name>.md (transcript)
├── error/     # αποτυχημένα: <name>.<ext> + <name>.error.log
└── .work/     # προσωρινοί per-process φάκελοι (internal, αγνοείται από το scan)
```

Παράδειγμα εκτέλεσης:

```shell
docker run -d --name youtube-to-text -p 3300:80 -v /host/media:/data youtube-to-text:latest
```

## Configuration (env vars)

| Var             | Default  | Περιγραφή                                              |
|-----------------|----------|--------------------------------------------------------|
| `WATCH_DIR`     | `/data`  | Ο mounted base φάκελος που περιέχει `in/`, `out/`, κ.λπ.|
| `POLL_INTERVAL` | `5`      | Δευτερόλεπτα μεταξύ σαρώσεων του `in/`.                 |
| `DEFAULT_LANG`  | (κενό)   | Προαιρετική γλώσσα Whisper· κενό = auto-detect.         |

## Detection (polling)

- Background **daemon thread** ξεκινά στο FastAPI startup (lifespan handler).
- Κάθε `POLL_INTERVAL` δευτερόλεπτα σαρώνει το `in/` για αρχεία με υποστηριζόμενο extension.
- **Stability check:** ένα αρχείο επεξεργάζεται μόνο όταν το μέγεθός του παραμένει **ίδιο
  μεταξύ δύο διαδοχικών σαρώσεων** — αποτρέπει το να πιαστεί αρχείο που ακόμα αντιγράφεται.
  Τα τελευταία γνωστά μεγέθη κρατούνται σε memory map `{path: size}`.
- **Σειριακή** επεξεργασία: ένα αρχείο τη φορά (το Whisper είναι CPU/GPU-heavy).

Επιλέχθηκε polling αντί για watchdog/inotify επειδή τα Docker volume mounts (bind mounts σε
Windows/macOS, network filesystems) συχνά **δεν** προωθούν αξιόπιστα filesystem events.

## Supported formats

- **Audio:** `.mp3 .wav .m4a .flac .ogg .aac .opus .wma`
- **Video:** `.mp4 .mkv .mov .avi .webm .flv`

Ο έλεγχος γίνεται case-insensitive στο extension. Οτιδήποτε άλλο αγνοείται και παραμένει
στο `in/` (δεν θεωρείται σφάλμα).

## Per-file pipeline

Για κάθε σταθερό αρχείο που επιλέγεται από το `in/`:

1. Δημιουργείται **μοναδικός** working φάκελος `WATCH_DIR/.work/<unique-id>/`. Όλα τα
   προσωρινά artifacts γράφονται μέσα εκεί. `unique-id` = όνομα αρχείου + αύξων μετρητής
   (ντετερμινιστικό, ευανάγνωστο, εύκολο στο testing — όχι timestamp/random).
2. **try:**
   1. `ffmpeg` κανονικοποιεί το input σε WAV (16 kHz, mono) **μέσα στο workdir** — καλύπτει
      ομοιόμορφα audio και video.
   2. `get_text(wav, language)` τρέχει Whisper (υπάρχουσα συνάρτηση). Γλώσσα από `DEFAULT_LANG`
      ή auto-detect αν κενό.
   3. Γράφεται το `.md` (πρώτα στο workdir):
      ```markdown
      ---
      channel: local folder
      id: <όνομα αρχείου χωρίς extension>
      ---
      <transcript text>
      ```
   4. Μετακινούνται στο `out/`: το πρωτότυπο ως `out/<name>.<ext>` και το `out/<name>.md`.
3. **except** (οποιοδήποτε σφάλμα ffmpeg/Whisper/IO):
   - Το πρωτότυπο μετακινείται στο `error/<name>.<ext>`.
   - Γράφεται `error/<name>.error.log` με το traceback. **Καμία** επανάληψη.
4. **finally:**
   - `shutil.rmtree(workdir, ignore_errors=True)` — ο working φάκελος σβήνει **πάντα**,
     ακόμη κι αν σκάσει οτιδήποτε ενδιάμεσα. Δεν χρειάζεται ξεχωριστή `os.remove` για το WAV.

### Collisions

Αν υπάρχει ήδη `out/<name>.<ext>` ή `out/<name>.md`, προστίθεται αριθμητικό suffix στη βάση
του ονόματος (`<name>-1`, `<name>-2`, …) ώστε **να μην γίνεται overwrite**. Το πρωτότυπο και
το `.md` κρατούν το ίδιο (suffixed) base name. Η ίδια λογική ισχύει και για το `error/`.

### Startup cleanup

Στο startup, πριν ξεκινήσει το polling, σβήνεται όλο το περιεχόμενο του `.work/` — καθαρίζει
ορφανά working dirs από προηγούμενο run που τερματίστηκε βίαια.

## Code structure

Ακολουθεί το υπάρχον στυλ (`processors.py` = logic/IO, `main.py` = routing μόνο):

- **`app/watcher.py`** (νέο): polling loop, stability tracking, επιλογή αρχείου, dispatch στο
  pipeline. Κρατά το `main.py` λεπτό και το `processors.py` εστιασμένο.
- **`app/processors.py`** (επέκταση):
  - `extract_audio_to_wav(input_path, workdir)` — shell out σε `ffmpeg`.
  - `transcribe_local_file(path, workdir, language)` — orchestrate extract → `get_text` → md
    string. Reuse της υπάρχουσας `get_text`.
  - Βοηθητικές: φίλτρο extension, build του md, collision-safe move.
- **`app/main.py`**: στο lifespan/startup spawn το watcher daemon thread. Το YouTube endpoint
  μένει αμετάβλητο.
- **Config**: ανάγνωση env vars με defaults σε ένα σημείο (π.χ. στην κορυφή του `watcher.py`).
- **`Dockerfile`**: καμία νέα system dependency (το `ffmpeg` υπάρχει ήδη). Το `CMD` μένει
  `fastapi run main.py --port 80`. Documentation του `-v` mount σε σχόλια/README.

## Testing

Unit tests **χωρίς** πραγματικό Whisper/ffmpeg (η βαριά μεταγραφή μένει εκτός CI):

- Φίλτρο extensions (case-insensitive· audio + video accept, άλλα reject).
- Stability check (ίδιο μέγεθος σε δύο σαρώσεις ⇒ ready· διαφορετικό ⇒ skip).
- Μορφή του `.md` frontmatter (`channel`, `id`, body = text).
- Collision suffixing (`<name>-1`, `<name>-2`).
- Λογική move→`out/` (επιτυχία) και move→`error/` + log (αποτυχία), με temp dirs και
  monkeypatched transcription.
- `finally` cleanup: ο workdir σβήνεται και όταν η μεταγραφή πετάει exception.

**Project rule:** end-to-end εκτέλεση **μόνο** μέσω Docker. Τα unit tests (`python -m unittest`)
δεν σηκώνουν το app, οπότε τρέχουν κανονικά· για οποιοδήποτε non-Docker run του ίδιου του app
θα ζητηθεί πρώτα επιβεβαίωση.

## Open questions

Καμία — το design είναι εγκεκριμένο.
