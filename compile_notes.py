#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import createQuarterFile, parseEntries, writeFile, ARCHIVE_FOLDERNAME, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR
from archive_entries import archive_entries


UNTAGGED_FOLDERNAME = "untagged"


def _scanFiles(thefolder, tags, untaggedFolders, isInUntaggedFolder=False):
    if thefolder.name == ARCHIVE_FOLDERNAME:
        return
    if thefolder.name == UNTAGGED_FOLDERNAME:
        isInUntaggedFolder = True
        untaggedFolders.append(thefolder)

    for x in thefolder.iterdir():
        if x.is_dir():
            _scanFiles(thefolder=x, tags=tags, untaggedFolders=untaggedFolders, isInUntaggedFolder=isInUntaggedFolder)
        elif x.is_file() and x.suffix.lower() == MARKDOWN_SUFFIX:
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

            # move entries from untagged file, don't copy them
            if hasTaggedEntries and isInUntaggedFolder:
                writeFile(filepath=x, prefix=entriesDict["prefix"], entries=untaggedEntries, mode="w", addLocation=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--archiveEntriesOlderThanWeeks", type=int, default=12, help="entries older than the specified number are moved to archive (in weeks; set to -1 to disable)")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    archiveEntriesOlderThanDate = None
    archiveEntriesOlderThanWeeks = args.archiveEntriesOlderThanWeeks
    if archiveEntriesOlderThanWeeks >= 0:
        archiveEntriesOlderThanDate = (today - timedelta(weeks=archiveEntriesOlderThanWeeks)).replace(hour=0, minute=0, second=0)


    tags = {}
    untaggedFolders = []
    _scanFiles(thefolder=notebookpath, tags=tags, untaggedFolders=untaggedFolders)

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

    for untaggedFolder in untaggedFolders:
        createQuarterFile(today=today, thepath=untaggedFolder, fileprefix=UNTAGGED_FOLDERNAME+"-")


