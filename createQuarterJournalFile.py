#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime
from noteslib import createQuarterJournalFile


RELATIVE_JOURNAL_PATH = "journal"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="createQuarterJournalFile")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / RELATIVE_JOURNAL_PATH

    createQuarterJournalFile(today=today, journalpath=journalpath)

