#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, writeFile
from math import ceil


TAG_NAMESPACE_SEPARATOR = "_"
JOURNAL_REL_PATH = "journal"
HANDOUT_REL_PATH = "handout.md"
INBOX_REL_PATH = JOURNAL_REL_PATH + "/" + "INBOX.md"
TAGS_REL_PATH = JOURNAL_REL_PATH + "/" + "tags"
MARKDOWN_FILE_SUFFIX = ".md"
ARCHIVE_FOLDERNAME = "_Archive"


def compileHandout(thefolder, notebookpath, handoutDict, today):
    for x in thefolder.iterdir():

        if x.is_dir():
            if x.name != ARCHIVE_FOLDERNAME:
                compileHandout(thefolder=x, notebookpath=notebookpath, handoutDict=handoutDict, today=today)

        elif x.is_file() and x.name.endswith(MARKDOWN_FILE_SUFFIX):
            thisFileMap = {}
            parsedEntries = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)
            for e in parsedEntries["entries"]:

                thisBucket = ceil((today - e["date"].replace(hour=0, minute=0, second=0)).days / 7.0)
                if thisBucket == 0:
                    thisBucket = 1
                if thisBucket not in thisFileMap:
                    thisFileMap[thisBucket] = e["location"]

            for bk, bv in thisFileMap.items():
                if bk not in handoutDict:
                    handoutDict[bk] = []
                handoutDict[bk].append(bv)


def archiveEntries(thefolder, archiveOlderThanDate):
    for x in thefolder.iterdir():

        if x.is_dir():
            if x.name != ARCHIVE_FOLDERNAME:
                archiveEntries(thefolder=x, archiveOlderThanDate=archiveOlderThanDate)

        elif x.is_file() and x.name.endswith(MARKDOWN_FILE_SUFFIX):
            parsedEntries = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)
            oldest = None
            for e in parsedEntries["entries"]:
                if oldest is None or e["date"] < oldest:
                    oldest = e["date"]

            if oldest is not None:
                if oldest < archiveOlderThanDate:
                    thequarter = oldest.strftime("%Y") + "-Q" + str((oldest.month // 3) + 1)
                    archiveFolder = x.parent / ARCHIVE_FOLDERNAME

                    for e in parsedEntries:
                        archiveQuarterFolder = archiveFolder / thequarter
                        if not archiveQuarterFolder.exists():
                            archiveQuarterFolder.mkdir(parents=True)

                        acounter = 2
                        archiveFile = archiveQuarterFolder / x.name
                        while archiveFile.exists():
                            archiveFile = archiveQuarterFolder / (x.stem + "-" + str(acounter) + x.suffix)
                            acounter = acounter + 1
                        writeFile(filepath=archiveFile, prefix=parsedEntries["prefix"], entries=parsedEntries["entries"], mode="w")
 
                    x.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="organize_journal")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--archiveOlderThanWeeks", type=int, default=-1, help="entries older than this will be moved to archive; if set to -1, user is asked for input, if set to 0, no entries are moved to archive")
    args = parser.parse_args()


    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / JOURNAL_REL_PATH
    inboxpath = notebookpath / INBOX_REL_PATH
    tagspath = notebookpath / TAGS_REL_PATH
    handoutpath = notebookpath / HANDOUT_REL_PATH

    archiveOlderThanWeeks = args.archiveOlderThanWeeks
    if archiveOlderThanWeeks == -1:
        archiveOlderThanWeeksStr = input("entries older than this will be moved to archive (in weeks) [default: 12]: ")
        print()
        archiveOlderThanWeeks = 12 if len(archiveOlderThanWeeksStr.strip()) == 0 else int(archiveOlderThanWeeksStr)


    tags = {}
    untagged = []
    inboxEntriesDict = parseEntries(thepath=inboxpath, notebookpath=notebookpath, untaggedtag=None, originPath=inboxpath.parent)
    for e in inboxEntriesDict["entries"]:
        etags = e["tags"]
        if len(etags) == 0:
            untagged.append(e)
        else:
            for t in etags:
                if t not in tags:
                    tags[t] = []
                tags[t].append(e)


    for k, v in tags.items():

        # a_b_c --> a/b/c.md
        namespaceComponents = k.split(TAG_NAMESPACE_SEPARATOR)
        folderpath = tagspath
        filename = k
        if len(namespaceComponents) > 1:
            folderpath = tagspath / ("/".join(namespaceComponents[0:-1]))
            filename = namespaceComponents[-1]
        if not folderpath.exists():
            folderpath.mkdir(parents=True)

        filepath = folderpath / (filename + MARKDOWN_FILE_SUFFIX)
        tagsEntriesDict = {"prefix": [], "entries": []}
        if filepath.exists():
            tagsEntriesDict = parseEntries(thepath=filepath, notebookpath=notebookpath, untaggedtag=None, originPath=filepath.parent)

        v.extend(tagsEntriesDict["entries"])
        writeFile(filepath=filepath, prefix=[], entries=v)


    writeFile(filepath=inboxpath, prefix=inboxEntriesDict["prefix"], entries=untagged)
    tags = None
    untagged = None


    today = datetime.today().replace(hour=0, minute=0, second=0)
    archiveOlderThanDate = None
    if archiveOlderThanWeeks > 0:
        archiveOlderThanDate = today - timedelta(days=(archiveOlderThanWeeks*7))

    if archiveOlderThanDate is not None:
        archiveEntries(thefolder=journalpath, archiveOlderThanDate=archiveOlderThanDate)


    handoutDict = {}
    compileHandout(thefolder=journalpath, notebookpath=notebookpath, handoutDict=handoutDict, today=today)
    for k, v in sorted(handoutDict.items(), reverse=True):
        print(k)
        for vv in v:
            print("   " + vv)

    with open(handoutpath, "w", encoding="utf-8") as handoutfile:
        handoutfile.write("# handout (generated on " + datetime.now().strftime("%Y%m%d %H:%M") + ")\n\n")

        for k, v in sorted(handoutDict.items(), reverse=True):
            print("## " + str(k) + " weeks old")
            handoutfile.write("## " + str(k) + " weeks old\n")

            for vloc in v:
                print("  " + vloc.replace("#L", ":"))
                handoutfile.write("  [" + vloc + "](" + vloc + ")\n")

            print()
            handoutfile.write("\n")

    print("handout file: /" + handoutpath.relative_to(notebookpath).as_posix())
    