#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, updateLinks, createQuarterFile, MARKDOWN_SUFFIX


IGNORE_TAG = "ignore"
TAG_NAMESPACE_SEPARATOR = "_"
EXACT_MATCH_SUFFIX = "NO-OTHER-TAGS"
TIMELINE_SUFFIX = "TIMELINE"
HTML_SUFFIX = ".html"


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
    parser.add_argument("--days", type=int, default=-1, help="tags older than this will be ignored; if set to 0, all entries are considered")
    parser.add_argument("--journalpath", type=str, default="journal", help="relative path to journal directory")
    parser.add_argument("--handoutpath", type=str, default="handout", help="relative path to handout directory")
    parser.add_argument("--enableTimeline", action="store_true", help="generate timeline file")
    parser.add_argument("--writeProtect", action="store_true", help="write-protect handout folder")
    parser.add_argument("--output_format", type=str, default="markdown", help="output format (\"markdown\" or \"html\")")
    parser.add_argument("tagsFilter", type=str, nargs="*", help="ignore entries not tagged with the listed tags; if not specified, filtering is disabled.")
    args = parser.parse_args()

    notebookpath = Path(args.notebookpath).resolve()
    thedays = args.days
    journalpath = notebookpath / args.journalpath
    handoutpath = notebookpath / args.handoutpath
    enableTimeline = args.enableTimeline
    writeProtect = args.writeProtect
    tagsFilter = args.tagsFilter

    generateHTMLOutput = False
    useAbsoluteLinks = False
    fileextension = MARKDOWN_SUFFIX
    md = None
    if args.output_format == "html":
        generateHTMLOutput = True
        useAbsoluteLinks = True
        fileextension = HTML_SUFFIX
        from markdown_it import MarkdownIt
        md = MarkdownIt()
    elif args.output_format != "markdown":
        raise Exception("invalid output format: " + args.output_format)

    if handoutpath.exists():
        recDelete(thepath=handoutpath, skipFirst=True)

    handoutpath.mkdir()

    today = datetime.today()
    ignoreOlderThanDate = None
    if thedays > 0:
        ignoreOlderThanDate = today - timedelta(days=thedays)

    thequarter = today.strftime("%Y") + "-Q" + str(((today.month - 1) // 3) + 1) + ".md"
    thequarterFile = journalpath / thequarter
    if not thequarterFile.exists():
        with open(thequarterFile, "w", encoding="utf-8") as qf:
            qf.write("# " + thequarter + "\n\n")

    tags = {}
    tagsPrefix = {}
    tagsFilterJoin = "" if len(tagsFilter) == 0 else "-".join(tagsFilter) + "-"
    exactMatchTag = tagsFilterJoin + EXACT_MATCH_SUFFIX
    timelineTag = tagsFilterJoin + TIMELINE_SUFFIX
    timelineList = []

    for x in notebookpath.glob("**/*" + MARKDOWN_SUFFIX):

        isFirst = True
        if x.is_file():
            fileTag = TAG_NAMESPACE_SEPARATOR.join(x.relative_to(notebookpath).with_suffix("").parts)
            entriesDict = parseEntries(thepath=x, notebookpath=notebookpath)
            tagsPrefix[fileTag] = {"prefix": entriesDict["prefix"], "file": x}

            for e in entriesDict["entries"]:
                eTags = e["tags"]
                e["origin"] = x

                if IGNORE_TAG in eTags:
                    continue

                ignoreEntry = False
                for tFilter in tagsFilter:
                    if tFilter not in eTags:
                        ignoreEntry = True
                        break
                if ignoreEntry:
                    continue

                if len(tagsFilter) != 0 and len(tagsFilter) == len(eTags):
                    eTags.append(exactMatchTag)

                if ignoreOlderThanDate is None or e["date"] >= ignoreOlderThanDate:
                    timelineList.append(e)

                for t in eTags:
                    if t not in tags:
                        tags[t] = []
                    tags[t].append(e)

            entriesDict = None


    if enableTimeline:
        tags[timelineTag] = timelineList

    for k, v in tags.items():
        v = sorted(v, key=lambda ii: ii["date"], reverse=True)
        tags[k] = v

    #tags = OrderedDict(sorted(tags.items(), key=lambda xy: None if len(xy[1]) == 0 else xy[1][0]["date"], reverse=True))

    for k, v in tags.items():

        if len(v) == 0 or (ignoreOlderThanDate is not None and v[0]["date"] < ignoreOlderThanDate):
            continue

        if k in tagsFilter:
            continue

        print(k)
        namespaceComponents = k.split(TAG_NAMESPACE_SEPARATOR)
        # a_b_c --> a/b/c.md
        folderpath = handoutpath
        filename = k
        if len(namespaceComponents) > 1:
            folderpath = handoutpath / ("/".join(namespaceComponents[0:-1]))
            filename = namespaceComponents[-1]
            if not folderpath.exists():
                folderpath.mkdir(parents=True)

        filenameprefix = "" if len(v) == 0 else (v[0]['date'].strftime("%y%m%d") + "_")
        filepath = folderpath / (filenameprefix + filename + fileextension)
        # print("/" + filepath.relative_to(notebookpath).as_posix())
        filecontent = ["# " + k + "\n**" + today.strftime("%d.%m.%Y") + ("" if len(tagsFilter) == 0 else " // tagsFilter: " + (" ".join(tagsFilter))) + "**\n\n"]

        if k in tagsPrefix and len(tagsPrefix[k]["prefix"]) != 0:
            filecontent.append("<div style=\"color:#00FFFF;\">\n\n")
            filecontent.append("## 📌 " + tagsPrefix[k]["file"].relative_to(notebookpath).as_posix() + "\n\n")
            for stickyl in tagsPrefix[k]["prefix"]:
                stickyl = updateLinks(stickyl, notebookPath=notebookpath, originPath=tagsPrefix[k]["file"].parent)
                if stickyl.startswith("#"):
                    stickyl = "##" + stickyl
                filecontent.append(stickyl)
            filecontent.append("\n\n[source](/" + str(tagsPrefix[k]["file"].relative_to(notebookpath).as_posix()) + ")\n\n")
            filecontent.append("</div>\n\n")

        isFirstOlder = True
        for vv in v:

            if isFirstOlder and vv["date"] < ignoreOlderThanDate:
                isFirstOlder = False
                filecontent.append("\n\n" + ("="*50) + "\n\n")

            for cv in vv["content"]:
                filecontent.append(updateLinks(content=cv, notebookPath=notebookpath, originPath=vv["origin"].parent, destinationPathAbsolute=folderpath.absolute()) + "\n")

            if generateHTMLOutput:
                npathposix = notebookpath.as_posix()
                if not npathposix.startswith("/"):
                    npathposix = "/" + npathposix
                filecontent.append("\n\n[source](vscode://file" + npathposix + vv["location"].replace("#L", ":") + ")\n\n")
            else:
                filecontent.append("\n\n[source](" + vv["location"] + ")\n\n")

        if generateHTMLOutput:
            with open(filepath, "w", encoding="utf-8") as handoutfile:
                handoutfile.write("""<!DOCTYPE html>

<html>
 <head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      background-color: #1d2327;
      color: #d6d6d6;
    }
    img {
      max-width: 100%;
    }
  </style>
  <title>""" + k + """</title>
 </head>
 <body>

""" + md.render("".join(filecontent)) + "\n\n </body>\n</html>\n")

        else:
            with open(filepath, "w", encoding="utf-8") as handoutfile:
                for filecontentline in filecontent:
                    handoutfile.write(filecontentline)

        if writeProtect:
            filepath.chmod(0o444)


    print()
    print("handout folder: " + handoutpath.as_posix())

    if writeProtect:
        writeProtectFolder(thepath=handoutpath)


    createQuarterFile(today=today, thepath=journalpath, fileprefix="")


