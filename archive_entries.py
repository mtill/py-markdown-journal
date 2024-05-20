#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, writeFile, MARKDOWN_SUFFIX, ARCHIVE_FOLDERNAME


TAG_NAMESPACE_SEPARATOR = "_"
STICKY_TAG = "sticky"


def _isEmpty(lines):
    for l in lines:
        if len(l.strip()) != 0:
            return False
    return True


# move older entries to archive
def archive_entries(notebookpath, workingdirectory, archiveEntriesOlderThanDate):
    for x in workingdirectory.glob("**/*" + MARKDOWN_SUFFIX):
        if ARCHIVE_FOLDERNAME in x.parts:
            continue

        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

            recentEntries = []
            oldEntries = {}   # year - quarter - list of entries
            for e in entriesDict["entries"]:
                eDate = e["date"]
                if STICKY_TAG not in e["tags"] and eDate < archiveEntriesOlderThanDate:
                    eYear = eDate.strftime("%Y")
                    eQuarter = "Q" + str(((eDate.month - 1) // 3) + 1)
                    if eYear not in oldEntries:
                        oldEntries[eYear] = {}
                    if eQuarter not in oldEntries[eYear]:
                        oldEntries[eYear][eQuarter] = []
                    oldEntries[eYear][eQuarter].append(e)
                else:
                    recentEntries.append(e)

            if len(oldEntries) != 0:
                if len(recentEntries) == 0 and _isEmpty(entriesDict["prefix"]):
                    x.unlink()
                else:
                    writeFile(filepath=x, prefix=entriesDict["prefix"], entries=recentEntries, mode="w")

                for theyear, thequartersDict in oldEntries.items():
                    for thequarter, theentries in thequartersDict.items():
                        archiveFolder = x.parent / ARCHIVE_FOLDERNAME / theyear / thequarter
                        if not archiveFolder.exists():
                            archiveFolder.mkdir(parents=True)
                        archiveFile = archiveFolder / x.name

                        theprefix = []
                        if archiveFile.exists():
                            oldEntriesDict = parseEntries(thepath=archiveFile, notebookpath=notebookpath, untaggedtag=None, originPath=archiveFile.parent)
                            theentries.extend(oldEntriesDict["entries"])
                        writeFile(filepath=archiveFile, prefix=theprefix, entries=theentries, mode="w")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--workingdirectory", type=str, default="./", help="working directory, relative to notebook directory")
    parser.add_argument("--archiveEntriesOlderThanWeeks", type=int, default=12, help="entries older than the specified number are moved to archive (in weeks)")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    workingdirectory = notebookpath / args.workingdirectory
    archiveEntriesOlderThanWeeks = args.archiveEntriesOlderThanWeeks
    archiveEntriesOlderThanDate = (today - timedelta(weeks=archiveEntriesOlderThanWeeks)).replace(hour=0, minute=0, second=0)

    archive_entries(notebookpath=notebookpath, workingdirectory=workingdirectory, archiveEntriesOlderThanDate=archiveEntriesOlderThanDate)

