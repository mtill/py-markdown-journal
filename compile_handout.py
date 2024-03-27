#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from collections import OrderedDict
from datetime import datetime, timedelta
from noteslib import parseEntries, makeLinksRelativeTo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compile_handout")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--weeks", type=int, default=-1, help="number of weeks considered as \"recent\"; if set to -1, user is asked for input")
    args = parser.parse_args()

    notebookpath = Path(args.notebookpath).resolve()
    numberOfWeeksToConsider = args.weeks
    if numberOfWeeksToConsider == -1:
        numberOfWeeksToConsider = int(input("number of weeks: "))
        print()

    journalpath = notebookpath / "journal"
    handoutpath = notebookpath / "handout"
    if handoutpath.exists():
        for c in handoutpath.glob("*.md"):
            c.chmod(0o666)
            c.unlink()
    else:
        handoutpath.mkdir()

    today = datetime.today()
    afterDate = (today - timedelta(weeks=numberOfWeeksToConsider)).replace(hour=0, minute=0, second=0)

    tags = {}
    tagsMetadata = {}
    for x in sorted(journalpath.iterdir()):
        isFirst = True
        if x.is_file():
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath)
            for e in entriesDict["entries"]:
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

    for k, v in tags.items():
        filename = handoutpath / (f"{tagsMetadata[k][0]:03d}" + "-" + f"{tagsMetadata[k][1]:03d}" + "-" + f"{tagsMetadata[k][2]:03d}" + "_" + k + ".md")
        with open(filename, "w", encoding="utf-8") as handoutfile:
            handoutfile.write("# " + k + "\n**" + afterDate.strftime("%d.%m.%Y") + " - " + today.strftime("%d.%m.%Y") + "  //  " + str(tagsMetadata[k][0]) + " recent / " + str(tagsMetadata[k][1]) + " in inbox / " + str(tagsMetadata[k][2]) + " older**\n\n")

            for stickyi in notebookpath.glob('**/*.md'):
                if stickyi.stem.lower() == k:
                    handoutfile.write("## 📌 " + stickyi.relative_to(notebookpath).as_posix() + "\n\n")
                    with open(stickyi, "r", encoding="utf-8") as stickyf:
                        for stickyl in stickyf:
                            stickyl = makeLinksRelativeTo(stickyl, notebookPath=notebookpath, originPath=stickyi)
                            if stickyl.startswith("#"):
                                stickyl = "##" + stickyl
                            handoutfile.write(stickyl)
                    handoutfile.write("\n\n[source](/" + str(stickyi.relative_to(notebookpath).as_posix()) + ")\n\n")

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

        filename.chmod(0o444)

