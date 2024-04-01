#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import string
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from noteslib import parseEntries


SCAN_FULL_CONTENT = True
EXACT_MATCH = False


if __name__ == "__main__":
    print(("\n"*20) + ((("="*30)+"\n")*3) + ("\n"*20))

    parser = argparse.ArgumentParser(description="compile_handout")
    parser.add_argument("--notebookpath", type=str, required=True, help="path to notebook directory")
    parser.add_argument("--out", type=str, default=None, help="if specified, result will be directed to the specified file")
    parser.add_argument("--search", type=str, nargs="*", default=None, help="search string(s); if not specified, user will be prompted")
    parser.add_argument("--ignoreOlderThanMonths", type=int, default=-1, help="entries older than this will be ignored; if set to -1, user is asked for input, if set to 0, no entries are ignored")
    args = parser.parse_args()

    ignoreOlderThanMonths = args.ignoreOlderThanMonths
    if ignoreOlderThanMonths == -1:
        ignoreOlderThanMonthsStr = input("ignore entries older than (in months) [default: 3]: ")
        print()
        ignoreOlderThanMonths = 3 if len(ignoreOlderThanMonthsStr.strip()) == 0 else int(ignoreOlderThanMonthsStr)

    ignoreOlderThanDate = None
    if ignoreOlderThanMonths > 0:
        ignoreOlderThanDate = datetime.today() - timedelta(days=(ignoreOlderThanMonths*30))

    notebookpath = Path(args.notebookpath).resolve()
    journalpath = notebookpath / "journal"
    mdoutputpath = None if args.out is None else (notebookpath / args.out)

    replacePunctuationTranslator = str.maketrans(string.punctuation, ' '*len(string.punctuation))

    alltags = {}
    parsedFiles = []
    numEntries = 0
    for x in sorted(journalpath.iterdir()):
        if x.is_file():
            parsedFile = parseEntries(thepath=x, notebookpath=notebookpath)
            parsedFiles.append(parsedFile)

            newEntries = []
            for e in parsedFile["entries"]:
                if ignoreOlderThanDate is not None and e["date"] < ignoreOlderThanDate:
                    continue

                numEntries = numEntries + 1
                e["path"] = x
                newEntries.append(e)
                for lctag in e["tags"]:
                    if lctag not in alltags:
                        alltags[lctag] = []
                    alltags[lctag].append(e["date"])

            parsedFile["entries"] = newEntries


    print("=== " + str(numEntries) + " ENTRIES; TAGS FOUND: ===")
    print("; ".join(["x" + axx[0] + " (" + str(len(axx[1])) + ")" for axx in sorted(alltags.items(), key=lambda ax: max(ax[1]), reverse=True)]))
    print("\n")


    searchStrings = args.search
    if searchStrings is None:
        searchStringsInput = input("search strings [xinbox]: ")
        print()
        searchStrings = ["xinbox"] if len(searchStringsInput.strip()) == 0 else searchStringsInput.split(" ")


    foundEntries = []
    for entriesDict in parsedFiles:
        isFirst = True
        for e in entriesDict["entries"]:
            if len(e["content"]) == 0:
                continue

            c = (" ".join(e["content"])) if SCAN_FULL_CONTENT else e["content"][0]
            csplit = c.translate(replacePunctuationTranslator).split(" ")

            ignoreThis = False
            for t in searchStrings:

                if EXACT_MATCH:
                    if t not in csplit:
                        ignoreThis = True
                        break
                else:
                    foundthistag = False
                    for csplitc in csplit:
                        if csplitc.startswith(t):
                            foundthistag = True
                            break
                    if not foundthistag:
                        ignoreThis = True
                        break

            if not ignoreThis:
                foundEntries.append(e)


    if mdoutputpath is None:
        for e in foundEntries:
            print(("\n".join(e["content"])) + "\n\n/" + e["path"].relative_to(notebookpath).as_posix() + ":" + str(e["pos"]) + "\n")

    else:
        if mdoutputpath.exists():
            mdoutputpath.chmod(0o666)

        with open(mdoutputpath, "w", encoding="utf-8") as mdoutputfile:
            for e in foundEntries:
                mdoutputfile.write(("\n".join(e["content"])) + "\n\n[source](" + e["location"] + ")\n\n")

        mdoutputpath.chmod(0o444)
        print(str(len(foundEntries)) + " results: /" + mdoutputpath.relative_to(notebookpath).as_posix())

