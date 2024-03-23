#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
import string
from pathlib import Path
from noteslib import parseEntries


SCAN_FULL_CONTENT = True
EXACT_MATCH = False


if __name__ == "__main__":
    notebookpath = Path(sys.argv[1]).resolve()
    journalpath = notebookpath / "journal"

    replacePunctuationTranslator = str.maketrans(string.punctuation, ' '*len(string.punctuation))

    print(("\n"*20) + ((("="*30)+"\n")*3) + ("\n"*20))

    alltags = {}
    parsedFiles = []
    for x in sorted(journalpath.iterdir()):
        if x.is_file():
            parsedFile = parseEntries(thepath=x, notebookpath=notebookpath)
            parsedFiles.append(parsedFile)

            for e in parsedFile["entries"]:
                for lctag in e["tags"]:
                    if lctag not in alltags:
                        alltags[lctag] = []
                    alltags[lctag].append(e["date"])

    print("\n\n=== ALL TAGS ===")
    print(" ".join(["x" + axx[0] for axx in sorted(alltags.items(), key=lambda ax: max(ax[1]), reverse=True)]))
    print("\n")


    searchStrings = []
    for xs in sys.argv[2:]:
        searchStrings.extend(xs.split(" "))
    if len(searchStrings) == 0:
        searchStringsInput = input("search strings [xinbox]: ")
        print()
        searchStrings = ["xinbox"] if len(searchStringsInput.strip()) == 0 else searchStringsInput.split(" ")


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
                if isFirst:
                    print("===== /" + x.relative_to(notebookpath).as_posix() + " =====\n")
                    isFirst = False
                print(("\n".join(e["content"])) + "\n\n/" + x.relative_to(notebookpath).as_posix() + ":" + str(e["pos"]) + "\n")

