#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
from datetime import datetime
from pathlib import Path


ignoreExtensions = [".lnk"]


def addDatePrefix(folders):
    for thefolderStr in folders:
        print("\n===== " + thefolderStr + " #####")
        thefolder = Path(thefolderStr)
        for c in thefolder.iterdir():
            if c.is_file():
                ignoreThis = False
                for ie in ignoreExtensions:
                    if c.name.lower().endswith(ie):
                        ignoreThis = True
                        break
                if ignoreThis:
                    continue

                theprefix = datetime.fromtimestamp(c.stat().st_mtime).strftime("%Y%m%d") + "_"
                if not c.name.startswith(theprefix):
                    newFile = thefolder / (theprefix + c.name)
                    if newFile.exists():
                        print("ignoring existing item: " + str(newFile.absolute().as_posix()))
                    else:
                        print(c.name + " -> " + newFile.name)
                        c.rename(newFile)

if __name__ == "__main__":
    folders = sys.argv[1:]
    addDatePrefix(folders=folders)

