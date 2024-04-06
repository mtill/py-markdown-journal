#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import re
import datetime
from pathlib import Path


entryprefix = "## "
entryregexes = [[re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ?(.*)'), "%Y-%m-%d %H:%M"],
                [re.compile(r'(\d{4}-\d{2}-\d{2}) ?(.*)'), "%Y-%m-%d"],
                [re.compile(r'(\d{8}) ?(.*)'), "%Y%m%d"]
               ]
tagregex = re.compile(r'\bx(\w+)\b')
relativeImageOrLinkRegex = re.compile(r'!?\[([^\]]*)\]\((\.\.?/[^\)]*)\)')

entryprefixlength = len(entryprefix)


def _stripcontent(thecontent):
    while len(thecontent) != 0:
        if len(thecontent[-1].strip()) == 0:
            thecontent.pop()
        else:
            return


def __replaceLinkMatch(l, notebookPath, originPath):
    rellink = (originPath / l.group(2)).resolve()
    return "/" + rellink.relative_to(notebookPath).as_posix()

def makeLinksRelativeTo(content, notebookPath, originPath):
    return relativeImageOrLinkRegex.sub(lambda x: __replaceLinkMatch(l=x, notebookPath=notebookPath, originPath=originPath), content)


def writeFile(filepath, prefix, entries):
    sortedEntries = sorted(entries, key=lambda x: x["date"])
    with open(filepath, "w", encoding="utf-8") as qf:
        for p in prefix:
            qf.write(p)

        for v in sortedEntries:
            for vline in v["content"]:
                qf.write(vline)
            qf.write("\n")


def prettyTable(table, rightAlign=False):
    result = []
    formatPrefix = "{:>" if rightAlign else "{:"

    result = []
    width = []
    for l in range(0, len(table)):
        for c in range(0, len(table[l])):
            le = len(table[l][c])
            if c >= len(width):
                width.append(le)
            elif le > width[c]:
                width[c] = le

    isFirst = True
    for l in range(0, len(table)):
        r = []
        for c in range(0, len(width)):
            st = "" if c >= len(table[l]) else table[l][c]
            r.append((formatPrefix + str(width[c]) + "}").format(st))
        result.append("| " + (" | ".join(r)) + " |")
        if isFirst:
            result.append("-" * (sum(width) + (len(width)-1)*3 + 4))
            isFirst = False

    return result


def parseEntries(thepath, notebookpath, untaggedtag="untagged"):
    entries = []
    prefix = []

    with open(thepath, "r", encoding="utf-8") as f:
        lasttime = None
        lastcontent = []
        lastpos = 0
        lasttags = []
        pos = -1
        for line in f:
            line = line.rstrip()
            pos = pos + 1

            thematch = None
            thedateformat = None
            if line.startswith(entryprefix):
                for entryregex in entryregexes:
                    thematch = entryregex[0].match(line[entryprefixlength:].lstrip())
                    if thematch is not None:
                        thedateformat = entryregex[1]
                        break

                thedate = datetime.datetime.min if thedateformat is None else datetime.datetime.strptime(thematch.group(1), thedateformat)

                if len(lastcontent) != 0:
                    _stripcontent(thecontent=lastcontent)
                    if untaggedtag is not None and len(lasttags) == 0:
                        lasttags = [untaggedtag]
                    entries.append({"date": lasttime, "content": lastcontent, "tags": lasttags, "pos": lastpos, "location": ("/" + thepath.relative_to(notebookpath).as_posix() + "#L" + str(lastpos))})

                lasttime = thedate
                lastcontent = [line]
                lasttags = tagregex.findall(line)
                lastpos = pos + 1
            else:

                if lasttime is None:
                    prefix.append(line)
                else:
                    lastcontent.append(line)
                    lasttags.extend(tagregex.findall(line))

        if len(lastcontent) != 0:
            _stripcontent(thecontent=lastcontent)
            if untaggedtag is not None and len(lasttags) == 0:
                lasttags = [untaggedtag]
            entries.append({"date": lasttime, "content": lastcontent, "tags": lasttags, "pos": lastpos, "location": ("/" + thepath.relative_to(notebookpath).as_posix() + "#L" + str(lastpos))})

    return {"prefix": prefix, "entries": entries}

