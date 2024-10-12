#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import time
import json
from pathlib import Path
from datetime import datetime
from noteslib import createQuarterFile, parseEntries, writeFile, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR


ENTRY_ID_FORMAT = "%Y%m%d-%H%M%S"


def _findModifiedFiles(thefolder, journalpath, lastrun_timestamp, results_journalfiles, results_notesfiles, isInJournalFolder=False):
    for x in thefolder.iterdir():
        if x.is_dir():
            cIsInJournalFolder = isInJournalFolder
            if not cIsInJournalFolder and x.samefile(journalpath):
                cIsInJournalFolder = True

            _findModifiedFiles(thefolder=x, journalpath=journalpath, lastrun_timestamp=lastrun_timestamp, results_journalfiles=results_journalfiles, results_notesfiles=results_notesfiles, isInJournalFolder=cIsInJournalFolder)
        elif x.is_file() and x.suffix.lower() == MARKDOWN_SUFFIX and x.stat().st_mtime > lastrun_timestamp:
            if isInJournalFolder:
                results_journalfiles.append(x)
            else:
                results_notesfiles.append(x)


def _scanFiles(thefiles, doMove, notebookpath, tags):
    for x in thefiles:
        entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)

        hasTaggedEntries = False
        untaggedEntries = []
        for e in entriesDict["entries"]:
            eTags = e["tags"]
            eId = e["date"].strftime(ENTRY_ID_FORMAT)
            e["id"] = eId

            if doMove:
                e["location"] = None

            if len(eTags) == 0:
                untaggedEntries.append(e)
            else:
                hasTaggedEntries = True

                for t in eTags:
                    if t not in tags:
                        tags[t] = []
                    tags[t].append(e)

        # move entries from file, don't copy them
        if doMove:
            if len(untaggedEntries) == 0 and len("".join(entriesDict["prefix"]).strip()) == 0:
                x.unlink()
            elif hasTaggedEntries:   # update file only if needed (when entries will be moved to some other file) 
                writeFile(filepath=x, prefix=entriesDict["prefix"], entries=untaggedEntries, mode="w", addLocation=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_notes")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--journalpath", type=str, default="journal", help="relative path to journal directory")
    args = parser.parse_args()

    today = datetime.today()
    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / args.journalpath

    notesconfigpath = notebookpath / ".notes.json"
    notesconfig = {}
    if notesconfigpath.exists():
        with open(notesconfigpath, "r", encoding="utf-8") as notesconfigfile:
            notesconfig = json.load(notesconfigfile)
    lastrun_timestamp = notesconfig.get("lastrun_timestamp", 0)


    results_journalfiles = []
    results_notesfiles = []
    _findModifiedFiles(thefolder=notebookpath, journalpath=journalpath, lastrun_timestamp=lastrun_timestamp, results_journalfiles=results_journalfiles, results_notesfiles=results_notesfiles, isInJournalFolder=False)

    tags = {}
    _scanFiles(thefiles=results_journalfiles, doMove=True, notebookpath=notebookpath, tags=tags)
    results_journalfiles = None
    _scanFiles(thefiles=results_notesfiles, doMove=False, notebookpath=notebookpath, tags=tags)
    results_notesfiles = None

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
                fe["location"] = None   # we don't want to add location to items from the same file
                fileEntriesIds[fe["date"].strftime(ENTRY_ID_FORMAT)] = fe

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


    createQuarterFile(today=today, thepath=journalpath, fileprefix="")

    notesconfig["lastrun_timestamp"] = time.time()
    with open(notesconfigpath, "w", encoding="utf-8") as notesconfigfile:
        json.dump(notesconfig, notesconfigfile, indent=2)

