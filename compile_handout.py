#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, makeLinksRelativeTo, createQuarterFile


IGNORE_TAG = "ignore"
TAG_NAMESPACE_SEPARATOR = "_"
MARKDOWN_SUFFIX = ".md"


def writeProtectFolder(thepath: Path):
    for c in thepath.iterdir():
        if c.is_dir():
            writeProtectFolder(thepath=c)

    thepath.chmod(0o555)


def recDelete(thepath: Path, skipFirst=False):
    thepath.chmod(0o777)

    for c in thepath.iterdir():
        if c.is_file():
            c.chmod(0o666)
            c.unlink()
        else:
            recDelete(thepath=c, skipFirst=False)

    thepath.rmdir()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_handout")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--ignoreOlderThanWeeks", type=int, default=-1, help="tags older than this will be ignored; if set to -1, user is asked for input, if set to 0, no entries are ignored")
    parser.add_argument("--output_format", type=str, default="markdown", help="output format (\"markdown\" or \"html\")")
    parser.add_argument("--journalpath", type=str, default="journal", help="relative path to journal directory")
    parser.add_argument("--handoutpath", type=str, default="handout", help="relative path to handout directory")
    args = parser.parse_args()

    notebookpath = Path(args.notebookpath).resolve()
    ignoreOlderThanWeeks = args.ignoreOlderThanWeeks
    if ignoreOlderThanWeeks == -1:
        ignoreOlderThanWeeksStr = input("ignore tags older than (in weeks) [default: 12]: ")
        print()
        ignoreOlderThanWeeks = 12 if len(ignoreOlderThanWeeksStr.strip()) == 0 else int(ignoreOlderThanWeeksStr)


    journalpath = notebookpath / args.journalpath
    handoutpath = notebookpath / args.handoutpath
    if handoutpath.exists():
        recDelete(thepath=handoutpath, skipFirst=True)

    handoutpath.mkdir()

    today = datetime.today()
    ignoreOlderThanDate = None
    if ignoreOlderThanWeeks > 0:
        ignoreOlderThanDate = today - timedelta(days=(ignoreOlderThanWeeks*7))

    thequarter = today.strftime("%Y") + "-Q" + str(((today.month - 1) // 3) + 1) + ".md"
    thequarterFile = journalpath / thequarter
    if not thequarterFile.exists():
        with open(thequarterFile, "w") as qf:
            qf.write("# " + thequarter + "\n\n")

    tags = {}
    tagsPrefix = {}
    for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):

        isFirst = True
        if x.is_file():
            fileTag = TAG_NAMESPACE_SEPARATOR.join(x.relative_to(notebookpath).with_suffix("").parts)
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath, untaggedtag=None, originPath=x.parent)
            tagsPrefix[fileTag] = {"prefix": entriesDict["prefix"], "file": x}

            for e in entriesDict["entries"]:

                if IGNORE_TAG in e["tags"]:
                    continue

                for t in e["tags"]:
                    if t not in tags:
                        tags[t] = []
                    tags[t].append(e)

            entriesDict = None


    for k, v in tags.items():
        v = sorted(v, key=lambda ii: ii["date"], reverse=True)
        tags[k] = v

    #tags = OrderedDict(sorted(tags.items(), key=lambda xy: None if len(xy[1]) == 0 else xy[1][0]["date"], reverse=True))
    oldertags = []

    for k, v in tags.items():
        if len(v) == 0 or (ignoreOlderThanDate is not None and v[0]["date"] < ignoreOlderThanDate):
            oldertags.append(k)
            continue

        namespaceComponents = k.split(TAG_NAMESPACE_SEPARATOR)
        # a_b_c --> a/b/00-01-001-c.md
        folderpath = handoutpath
        filename = k
        if len(namespaceComponents) > 1:
            folderpath = handoutpath / ("/".join(namespaceComponents[0:-1]))
            filename = namespaceComponents[-1]
            if not folderpath.exists():
                folderpath.mkdir(parents=True)


        filepath = folderpath / (filename + MARKDOWN_SUFFIX)
        # print("/" + filepath.relative_to(notebookpath).as_posix())
        filecontent = ["# " + k + "\n**" + today.strftime("%d.%m.%Y")]

        if k in tagsPrefix and len(tagsPrefix[k]["prefix"]) != 0:
            filecontent.append("<div style=\"color:#00FFFF;\">\n\n")
            filecontent.append("## 📌 " + tagsPrefix[k]["file"].relative_to(notebookpath).as_posix() + "\n\n")
            for stickyl in tagsPrefix[k]["prefix"]:
                stickyl = makeLinksRelativeTo(stickyl, notebookPath=notebookpath, originPath=tagsPrefix[k]["file"].parent)
                if stickyl.startswith("#"):
                    stickyl = "##" + stickyl
                filecontent.append(stickyl)
            filecontent.append("\n\n[source](/" + str(tagsPrefix[k]["file"].relative_to(notebookpath).as_posix()) + ")\n\n")
            filecontent.append("</div>\n\n")

        for vv in v:
            for cv in vv["content"]:
                filecontent.append(cv + "\n")

            filecontent.append("\n\n[source](" + vv["location"] + ")\n\n")

        with open(filepath, "w", encoding="utf-8") as handoutfile:
            for filecontentline in filecontent:
                handoutfile.write(filecontentline)

        filepath.chmod(0o444)


    if len(oldertags) != 0:
        print("skipped tags (older than " + str(ignoreOlderThanWeeks) + " weeks): " + (" ".join(oldertags)))

    #print("\nHandout folder: /" + handoutpath.relative_to(notebookpath).as_posix())


    print("handout folder: " + handoutpath.as_posix())

    writeProtectFolder(thepath=handoutpath)


    createQuarterFile(today=today, thepath=journalpath, fileprefix="")


