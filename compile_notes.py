#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, writeFile


IGNORE_TAGS = ["inbox", "rs"]
TAG_NAMESPACE_SEPARATOR = "_"
MARKDOWN_SUFFIX = ".md"
REVERSE_ORDER = False
ARCHIVE_FOLDERNAME = "_Archive"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--journalpath", type=str, default="journal", help="relative path to journal directory")
    parser.add_argument("--archiveEntriesOlderThanWeeks", type=int, default=12, help="entries older than the specified number are moved to archive (in weeks; set to -1 to disable)")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / args.journalpath
    archiveEntriesOlderThanWeeks = args.archiveEntriesOlderThanWeeks
    archiveEntriesOlderThanDate = None if archiveEntriesOlderThanWeeks == -1 else (today - timedelta(weeks=archiveEntriesOlderThanWeeks)).replace(hour=0, minute=0, second=0)

    thequarter = today.strftime("%Y") + "-Q" + str(((today.month - 1) // 3) + 1) + ".md"
    thequarterFile = journalpath / thequarter
    if not thequarterFile.exists():
        with open(thequarterFile, "w") as qf:
            qf.write("# " + thequarter + "\n\n")

    tags = {}
    for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):
        if ARCHIVE_FOLDERNAME in x.parts:
            continue

        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

            for e in entriesDict["entries"]:
                e["id"] = e["date"].strftime("%Y%m%d-%H%M%S")
                e["content"].append("[source](" + e["location"] + ")")

                for t in e["tags"]:
                    if t not in IGNORE_TAGS:
                        if t not in tags:
                            tags[t] = []
                        tags[t].append(e)
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
                print("ADDING to " + filepath.relative_to(notebookpath).as_posix() + ":")
                print("\n".join(e["content"]))
                print()
                modified = True


        if modified:
            writeFile(filepath=filepath, prefix=prefix, entries=fileEntries, mode="w", reverse=REVERSE_ORDER)


    # move older entries to archive
    if archiveEntriesOlderThanDate is not None:
        for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):
            if ARCHIVE_FOLDERNAME in x.parts:
                continue

            if x.is_file():
                entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

                recentEntries = []
                oldEntries = {}
                for e in entriesDict["entries"]:
                    eDate = e["date"]
                    if eDate < archiveEntriesOlderThanDate:
                        eQuarter = eDate.strftime("%Y") + "-Q" + str(((eDate.month - 1) // 3) + 1)
                        if eQuarter not in oldEntries:
                            oldEntries[eQuarter] = []
                        oldEntries[eQuarter].append(e)
                    else:
                        recentEntries.append(e)

                if len(oldEntries) != 0:
                    if len(recentEntries) == 0 and len(entriesDict["prefix"]) == 0:
                        x.unlink()
                    else:
                        writeFile(filepath=x, prefix=entriesDict["prefix"], entries=recentEntries, mode="w", reverse=REVERSE_ORDER)

                    for thequarter, theentries in oldEntries.items():
                        archiveFolder = x.parent / ARCHIVE_FOLDERNAME / thequarter
                        if not archiveFolder.exists():
                            archiveFolder.mkdir(parents=True)
                        archiveFile = archiveFolder / x.name

                        theprefix = []
                        if archiveFile.exists():
                            oldEntriesDict = parseEntries(thepath=archiveFile, notebookpath=notebookpath, untaggedtag=None, originPath=archiveFile.parent)
                            theentries.extend(oldEntriesDict["entries"])
                        writeFile(filepath=archiveFile, prefix=theprefix, entries=theentries, mode="w", reverse=REVERSE_ORDER)

