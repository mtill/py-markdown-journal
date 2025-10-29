from pathlib import Path
import os
from datetime import datetime
from noteslib import parseEntries, writeFile

NOTEBOOK_PATH = Path(os.environ.get('NOTES_PATH', '.')).resolve()
JOURNAL_PATH = NOTEBOOK_PATH / "journal"

entries = {}
prefixes = {}

for i in JOURNAL_PATH.glob("**/*.md"):
    print(i)
    parsedEntries = parseEntries(thepath=i, notebookpath=i)
    prefixes[i.name] = parsedEntries["prefix"]

    for entry in parsedEntries["entries"]:
        dt = entry["date"]

        # determine quarter file
        quarter = (dt.month - 1) // 3 + 1
        quarter_filename = f"{dt.year}-Q{quarter}.md"
        journal_file = JOURNAL_PATH / quarter_filename

        if quarter_filename not in entries:
            entries[quarter_filename] = []
        entries[quarter_filename].append(entry)

    i.unlink()  # delete original file


for quarter_filename, parsedEntries in entries.items():
    writeFile(filepath=JOURNAL_PATH / quarter_filename,
                prefix=prefixes.get(quarter, ""),
                entries=parsedEntries)


