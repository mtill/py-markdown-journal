#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from collections import OrderedDict
from datetime import datetime, timedelta
from noteslib import parseEntries, makeLinksRelativeTo


IGNORE_TAG = "ignore"
TAG_NAMESPACE_SEPARATOR = "_"


def writeProtectFolder(thepath: Path):
    for c in thepath.iterdir():
        if c.is_dir():
            writeProtectFolder(thepath=c)

    thepath.chmod(0o555)


def recDelete(thepath: Path):
    thepath.chmod(0o777)

    for c in thepath.iterdir():
        if c.is_file():
            c.chmod(0o666)
            c.unlink()
        else:
            recDelete(thepath=c)

    thepath.rmdir()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_handout")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--weeks", type=int, default=-1, help="number of weeks considered as \"recent\"; if set to -1, user is asked for input")
    parser.add_argument("--ignoreOlderThanMonths", type=int, default=-1, help="tags older than this will be ignored; if set to -1, user is asked for input, if set to 0, no entries are ignored")
    args = parser.parse_args()


    notebookpath = Path(args.notebookpath).resolve()
    numberOfWeeksToConsider = args.weeks
    if numberOfWeeksToConsider == -1:
        numberOfWeeksToConsiderStr = input("number of weeks [default: 1]: ")
        print()
        numberOfWeeksToConsider = 1 if len(numberOfWeeksToConsiderStr.strip()) == 0 else int(numberOfWeeksToConsiderStr)

    ignoreOlderThanMonths = args.ignoreOlderThanMonths
    if ignoreOlderThanMonths == -1:
        ignoreOlderThanMonthsStr = input("ignore tags older than (in months) [default: 3]: ")
        print()
        ignoreOlderThanMonths = 3 if len(ignoreOlderThanMonthsStr.strip()) == 0 else int(ignoreOlderThanMonthsStr)

    journalpath = notebookpath / "journal"
    handoutpath = notebookpath / "handout"
    if handoutpath.exists():
        recDelete(thepath=handoutpath)

    handoutpath.mkdir()

    today = datetime.today()
    afterDate = (today - timedelta(weeks=numberOfWeeksToConsider)).replace(hour=0, minute=0, second=0)
    ignoreOlderThanDate = None
    if ignoreOlderThanMonths > 0:
        ignoreOlderThanDate = today - timedelta(days=(ignoreOlderThanMonths*30))

    tags = {}
    tagsMetadata = {}
    for x in sorted(journalpath.iterdir()):
        isFirst = True
        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath)
            for e in entriesDict["entries"]:
                if IGNORE_TAG in e["tags"]:
                    continue

                e["path"] = x
                inInbox = "inbox" in e["tags"]
                for t in e["tags"]:
                    if t not in tags:
                        tags[t] = []
                    tags[t].append(e)

                    if t not in tagsMetadata:
                        tagsMetadata[t] = [0, 0, 0]
                    if inInbox:
                        tagsMetadata[t][1] = tagsMetadata[t][1] + 1
                    if e["date"] < afterDate:
                        tagsMetadata[t][2] = tagsMetadata[t][2] + 1
                    else:
                        tagsMetadata[t][0] = tagsMetadata[t][0] + 1

    for k, v in tags.items():
        tags[k] = sorted(v, key=lambda ii: ii["date"], reverse=True)
    tags = OrderedDict(sorted(tags.items(), key=lambda xy: None if len(xy[1]) == 0 else xy[1][0]["date"], reverse=True))
    oldertags = []

    print("filename prefix: recent - in inbox - older")
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

        #print(k + ":\t\t" + str(tagsMetadata[k][0]) + " recent\t" + str(tagsMetadata[k][1]) + " in inbox\t" + str(tagsMetadata[k][2]) + " older")
        filepath = folderpath / (f"{tagsMetadata[k][0]:02d}" + "-" + f"{tagsMetadata[k][1]:02d}" + "-" + f"{tagsMetadata[k][2]:03d}" + "_" + filename + ".md")
        print("/" + filepath.relative_to(notebookpath).as_posix())
        with open(filepath, "w", encoding="utf-8") as handoutfile:
            handoutfile.write("# " + k + "\n**" + afterDate.strftime("%d.%m.%Y") + " - " + today.strftime("%d.%m.%Y") + "  //  " + str(tagsMetadata[k][0]) + " recent / " + str(tagsMetadata[k][1]) + " in inbox / " + str(tagsMetadata[k][2]) + " older**\n\n")

            for stickyi in notebookpath.glob('**/*.md'):
                if stickyi.stem.lower() == k:
                    handoutfile.write("<div style=\"color:#00FFFF\">\n\n")
                    handoutfile.write("## 📌 " + stickyi.relative_to(notebookpath).as_posix() + "\n\n")
                    with open(stickyi, "r", encoding="utf-8") as stickyf:
                        for stickyl in stickyf:
                            stickyl = makeLinksRelativeTo(stickyl, notebookPath=notebookpath, originPath=stickyi)
                            if stickyl.startswith("#"):
                                stickyl = "##" + stickyl
                            handoutfile.write(stickyl)
                    handoutfile.write("\n\n[source](/" + str(stickyi.relative_to(notebookpath).as_posix()) + ")\n\n")
                    handoutfile.write("</div>\n\n")

            historicalMode = False
            for vv in v:
                if not historicalMode and vv["date"] < afterDate:
                    historicalMode = True
                    handoutfile.write("<details style=\"color:gray; border:2px solid; padding: 1em\">\n  <summary>" + k + ": older entries</summary>\n\n")

                isininbox = False
                if "inbox" in vv["tags"]:
                    isininbox = True
                    handoutfile.write("<div style=\"color:orange\">\n\n")

                for cv in vv["content"]:
                    cv = makeLinksRelativeTo(cv, notebookPath=notebookpath, originPath=vv["path"])
                    #if historicalMode and cv.startswith("#"):
                    #    cv = "#" + cv
                    handoutfile.write(cv + "\n")

                handoutfile.write("\n\n[source](" + vv["location"] + ")\n\n")

                if isininbox:
                    handoutfile.write("</div>\n\n")

            if historicalMode:
                handoutfile.write("</details>\n\n")

        filepath.chmod(0o444)

    writeProtectFolder(thepath=handoutpath)

    if len(oldertags) != 0:
        print("skipped tags (older than " + str(ignoreOlderThanMonths) + " months): " + (" ".join(oldertags)))

    #print("\nHandout folder: /" + handoutpath.relative_to(notebookpath).as_posix())

