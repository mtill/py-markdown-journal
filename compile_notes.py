#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, writeFile, ARCHIVE_FOLDERNAME, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR
from archive_entries import archive_entries


RELATIVE_JOURNAL_PATH = "journal"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--archiveEntriesOlderThanWeeks", type=int, default=12, help="entries older than the specified number are moved to archive (in weeks; set to -1 to disable)")
    parser.add_argument("--removeTaggedEntriesFromJournal", action="store_true", default=True, help="#tagged entries are moved from journal (not copied)")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / RELATIVE_JOURNAL_PATH
    archiveEntriesOlderThanDate = None
    archiveEntriesOlderThanWeeks = args.archiveEntriesOlderThanWeeks
    if archiveEntriesOlderThanWeeks >= 0:
        archiveEntriesOlderThanDate = (today - timedelta(weeks=archiveEntriesOlderThanWeeks)).replace(hour=0, minute=0, second=0)
    removeTaggedEntriesFromJournal = args.removeTaggedEntriesFromJournal

    thequarter = today.strftime("%Y") + "-Q" + str(((today.month - 1) // 3) + 1) + ".md"

    tags = {}
    for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):
        if ARCHIVE_FOLDERNAME in x.parts:
            continue

        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

            hasTaggedEntries = False
            untaggedEntries = []
            for e in entriesDict["entries"]:
                eTags = e["tags"]
                eId = e["date"].strftime("%Y%m%d-%H%M%S")
                e["id"] = eId

                if len(eTags) == 0:
                    untaggedEntries.append(e)
                else:
                    hasTaggedEntries = True

                    for t in eTags:
                        if t not in tags:
                            tags[t] = []
                        tags[t].append(e)

            # move entries from journal, don't copy them
            if removeTaggedEntriesFromJournal and hasTaggedEntries and x.is_relative_to(journalpath):
                writeFile(filepath=x, prefix=entriesDict["prefix"], entries=untaggedEntries, mode="w", addLocation=False)

            entriesDict = None


    for k, v in tags.items():
        namespaceComponents = k.split(TAG_NAMESPACE_SEPARATOR)
        # a_b_c --> a/b/c.md
        folderpath = notebookpath
        filename = k
        if len(namespaceComponents) > 1:
            folderpath = notebookpath / ("/".join(namespaceComponents[0:-1]))
            filename = namespaceComponents[-1]
            if not folderpath.exists():
                folderpath.mkdir(parents=True)

        filepath = folderpath / (filename + MARKDOWN_SUFFIX)

        modified = False
        prefix = []
        fileEntries = []
        fileEntriesIds = {}

        if filepath.is_file():
            entriesDict = parseEntries(thepath=filepath, notebookpath=notebookpath, untaggedtag=None)
            prefix = entriesDict["prefix"]
            fileEntries = entriesDict["entries"]
            for fe in fileEntries:
                fileEntriesIds[fe["date"].strftime("%Y%m%d-%H%M%S")] = e

        for tagEntry in v:
            if tagEntry["id"] not in fileEntriesIds:
                fileEntriesIds[tagEntry["id"]] = tagEntry
                fileEntries.append(tagEntry)
                #print("ADDING to " + filepath.relative_to(notebookpath).as_posix() + ":")
                #print("\n".join(e["content"]))
                #print()
                modified = True


        if modified:
            writeFile(filepath=filepath, prefix=prefix, entries=fileEntries, mode="w", addLocation=True)

    if archiveEntriesOlderThanDate is not None:
        archive_entries(notebookpath=notebookpath, workingdirectory=notebookpath, archiveEntriesOlderThanDate=archiveEntriesOlderThanDate)

    thequarterFile = journalpath / thequarter
    if not thequarterFile.exists():
        with open(thequarterFile, "w") as qf:
            qf.write("\n")

