#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
from pathlib import Path
from datetime import datetime, timedelta
from noteslib import parseEntries, makeLinksRelativeTo


IGNORE_TAG = "ignore"
TAG_NAMESPACE_SEPARATOR = "_"


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
    parser.add_argument("--weeks", type=int, default=-1, help="number of weeks considered as \"recent\"; if set to -1, user is asked for input")
    parser.add_argument("--ignoreOlderThanWeeks", type=int, default=-1, help="tags older than this will be ignored; if set to -1, user is asked for input, if set to 0, no entries are ignored")
    parser.add_argument("--output_format", type=str, default="markdown", help="output format (\"markdown\" or \"html\")")
    parser.add_argument("--highlight_tag", type=str, default="inbox", help="highlight entries with this tag assigned, e.g., entries with \"inbox\" tag. Default: \"inbox\".")
    args = parser.parse_args()

    generateHTMLOutput = False
    md = None
    if args.output_format == "html":
        generateHTMLOutput = True
        from markdown_it import MarkdownIt
        md = MarkdownIt()
    elif args.output_format != "markdown":
        raise Exception("invalid output format: " + args.output_format)
    fileextension = ".html" if generateHTMLOutput else ".md"

    highlightTag = args.highlight_tag

    notebookpath = Path(args.notebookpath).resolve()
    numberOfWeeksToConsider = args.weeks
    if numberOfWeeksToConsider == -1:
        numberOfWeeksToConsiderStr = input("number of weeks [default: 1]: ")
        print()
        numberOfWeeksToConsider = 1 if len(numberOfWeeksToConsiderStr.strip()) == 0 else int(numberOfWeeksToConsiderStr)

    ignoreOlderThanWeeks = args.ignoreOlderThanWeeks
    if ignoreOlderThanWeeks == -1:
        ignoreOlderThanWeeksStr = input("ignore tags older than (in weeks) [default: 12]: ")
        print()
        ignoreOlderThanWeeks = 12 if len(ignoreOlderThanWeeksStr.strip()) == 0 else int(ignoreOlderThanWeeksStr)

    journalpath = notebookpath / "journal"
    handoutpath = notebookpath / "handout"
    if handoutpath.exists():
        recDelete(thepath=handoutpath, skipFirst=True)

    handoutpath.mkdir()

    today = datetime.today()
    afterDate = (today - timedelta(weeks=numberOfWeeksToConsider)).replace(hour=0, minute=0, second=0)
    ignoreOlderThanDate = None
    if ignoreOlderThanWeeks > 0:
        ignoreOlderThanDate = today - timedelta(days=(ignoreOlderThanWeeks*7))

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
                hasHighlightTag = highlightTag in e["tags"]
                for t in e["tags"]:
                    if t not in tags:
                        tags[t] = []
                    tags[t].append(e)

                    if t not in tagsMetadata:
                        tagsMetadata[t] = {"recent": 0,
                                           "highlight tag": 0,
                                           "older": 0,
                                           "filepath": None,
                                           "filepathstr": "",
                                           "date of latest entry": ""}
                    if hasHighlightTag:
                        tagsMetadata[t]["highlight tag"] = tagsMetadata[t]["highlight tag"] + 1
                    if e["date"] < afterDate:
                        tagsMetadata[t]["older"] = tagsMetadata[t]["older"] + 1
                    else:
                        tagsMetadata[t]["recent"] = tagsMetadata[t]["recent"] + 1
            entriesDict = None

    for k, v in tags.items():
        v = sorted(v, key=lambda ii: ii["date"], reverse=True)
        tags[k] = v
        tagsMetadata[k]["date of latest entry"] = "" if len(v) == 0 else v[0]['date'].strftime("%y%m%d")

    #tags = OrderedDict(sorted(tags.items(), key=lambda xy: None if len(xy[1]) == 0 else xy[1][0]["date"], reverse=True))
    oldertags = []

    print("filename prefix: #recent - #" + highlightTag + " - date of last entry")
    for k, v in tags.items():
        if len(v) == 0 or (k != highlightTag and (ignoreOlderThanDate is not None and v[0]["date"] < ignoreOlderThanDate)):
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

        if tagsMetadata[k]["highlight tag"] > 0:
            filename = filename.upper()

        # f"{tagsMetadata[k]['older']:03d}" + "_"
        # ("" if len(v) == 0 else ("{:03d}".format((today - v[0]['date']).days)) + "-") + \
        filenameprefix = f"{tagsMetadata[k]['recent']:02d}" + "-" + \
                         f"{tagsMetadata[k]['highlight tag']:02d}" + "-" + \
                         ("" if len(tagsMetadata[k]['date of latest entry']) == 0 else tagsMetadata[k]['date of latest entry'] + "-")

        filepath = folderpath / (filenameprefix + filename + fileextension)
        tagsMetadata[k]["filepath"] = filepath
        tagsMetadata[k]["filepathstr"] = filepath.relative_to(notebookpath).as_posix()
        # print("/" + filepath.relative_to(notebookpath).as_posix())
        filecontent = ["# " + k + "\n**" + afterDate.strftime("%d.%m.%Y") + " - " \
                       + today.strftime("%d.%m.%Y") + "  //  " \
                       + str(tagsMetadata[k]["recent"]) + " recent / " \
                       + str(tagsMetadata[k]["highlight tag"]) + " " + highlightTag + " / " \
                       + str(tagsMetadata[k]["older"]) + " older**\n\n"]

        for stickyi in notebookpath.glob('**/*.md'):
            if stickyi.stem.lower() == k:
                filecontent.append("<div style=\"color:#00FFFF;\">\n\n")
                filecontent.append("## 📌 " + stickyi.relative_to(notebookpath).as_posix() + "\n\n")
                with open(stickyi, "r", encoding="utf-8") as stickyf:
                    for stickyl in stickyf:
                        stickyl = makeLinksRelativeTo(stickyl, notebookPath=notebookpath, originPath=stickyi)
                        if stickyl.startswith("#"):
                            stickyl = "##" + stickyl
                        filecontent.append(stickyl)
                filecontent.append("\n\n[source](/" + str(stickyi.relative_to(notebookpath).as_posix()) + ")\n\n")
                filecontent.append("</div>\n\n")

        historicalMode = False
        for vv in v:
            if not historicalMode and vv["date"] < afterDate:
                historicalMode = True
                filecontent.append("<details style=\"color:gray; border:2px solid; padding: 1em;\">\n  <summary>" + k + ": older entries</summary>\n\n")

            ishighlight = False
            if highlightTag in vv["tags"]:
                ishighlight = True
                filecontent.append("<div style=\"color:orange;\">\n\n")

            for cv in vv["content"]:
                cv = makeLinksRelativeTo(cv, notebookPath=notebookpath, originPath=vv["path"])
                #if historicalMode and cv.startswith("#"):
                #    cv = "#" + cv
                filecontent.append(cv + "\n")

            filecontent.append("\n\n[source](" + vv["location"] + ")\n\n")

            if ishighlight:
                filecontent.append("</div>\n\n")

        if historicalMode:
            filecontent.append("</details>\n\n")

        if generateHTMLOutput:
            with open(filepath, "w", encoding="utf-8") as handoutfile:
                handoutfile.write("<!DOCTYPE html>\n\n<html><head><meta charset=\"UTF-8\"><title>" + k + "</title></head><body style=\"background-color: #1d2327; color: #d6d6d6;'\">" + md.render("".join(filecontent)) + "</body></html>\n")
        else:
            with open(filepath, "w", encoding="utf-8") as handoutfile:
                for filecontentline in filecontent:
                    handoutfile.write(filecontentline)

        filepath.chmod(0o444)


    if len(oldertags) != 0:
        print("skipped tags (older than " + str(ignoreOlderThanWeeks) + " weeks): " + (" ".join(oldertags)))

    #print("\nHandout folder: /" + handoutpath.relative_to(notebookpath).as_posix())


    if generateHTMLOutput:
        indexpath = handoutpath / "index.html"
        with open(indexpath, "w", encoding="utf-8") as indexfile:
            indexfile.write("<!DOCTYPE html>\n\n<html><head><meta charset=\"UTF-8\"><title>index</title></head><body>\n")
            indexfile.write("<h1>index</h1>\n<table><tr><th>tag</th><th>recent</th><th>" + highlightTag + "</th><th>older</th>\n")
            for k, v in sorted(tags.items(), key=lambda kvk: tagsMetadata[kvk[0]]["filepathstr"]):
                if tagsMetadata[k]["filepath"] is not None:
                    indexfile.write("<tr><td><a href=\"" + tagsMetadata[k]["filepath"].relative_to(handoutpath).as_posix() + "\">" + k + "</a></td><td>" + str(tagsMetadata[k]["recent"]) + "</td><td>" + str(tagsMetadata[k]["highlight tag"]) + "</td><td>" + str(tagsMetadata[k]["older"]) + "</td></tr>\n")
            indexfile.write("</table>\n</body></html>\n")
        indexpath.chmod(0o444)
    else:
        indexpath = handoutpath / "index.md"
        with open(indexpath, "w", encoding="utf-8") as indexfile:
            indexfile.write("# index\n\n")
            indexfile.write("| tag                                                                    | recent | " + highlightTag + " | older |\n")
            indexfile.write("| ---------------------------------------------------------------------- | ------ | " + ("-"*len(highlightTag)) + " | ----- |\n")
            for k, v in sorted(tags.items(), key=lambda kvk: tagsMetadata[kvk[0]]["filepathstr"]):
                if tagsMetadata[k]["filepath"] is not None:
                    indexfile.write("| " +
                                    ("{:70}".format("[" + k + "](" + tagsMetadata[k]["filepath"].relative_to(handoutpath).as_posix() + ")")) +
                                    " | " + ("{:>6}".format(tagsMetadata[k]["recent"])) +
                                    " | " + (("{:>" + str(len(highlightTag)) + "}").format(tagsMetadata[k]["highlight tag"])) +
                                    " | " + ("{:>5}".format(tagsMetadata[k]["older"])) + " |\n")
        indexpath.chmod(0o444)

    print("index file: " + indexpath.as_posix())
    print("handout folder: " + handoutpath.as_posix())

    writeProtectFolder(thepath=handoutpath)


