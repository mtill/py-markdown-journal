#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, writeFile


MARKDOWN_SUFFIX = ".md"
RECENT_TAG = "@recent"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--weeks", type=int, default=-1, help="number of weeks considered as \"recent\"; if set to -1, user is asked for input")
    args = parser.parse_args()

    numberOfWeeksToConsider = args.weeks
    if numberOfWeeksToConsider == -1:
        numberOfWeeksToConsiderStr = input("number of weeks [default: 1]: ")
        print()
        numberOfWeeksToConsider = 1 if len(numberOfWeeksToConsiderStr.strip()) == 0 else int(numberOfWeeksToConsiderStr)


    notebookpath = Path(args.notebookpath).resolve()
    today = datetime.today()
    afterDate = (today - timedelta(weeks=numberOfWeeksToConsider)).replace(hour=0, minute=0, second=0)

    for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):
        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

            modified = False
            for e in entriesDict["entries"]:
                if RECENT_TAG not in e["tags"]:
                    if e["date"] >= afterDate:
                        e["content"][0] = e["content"][0] + " " + RECENT_TAG
                        e["tags"].append(RECENT_TAG)
                        modified = True

            if modified:
                writeFile(filepath=x, prefix=entriesDict["prefix"], entries=entriesDict["entries"], mode="w", reverse=False)
