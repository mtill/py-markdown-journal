#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
from datetime import datetime
from pathlib import Path


def addDatePrefix(folders):
    for thefolderStr in folders:
        thefolder = Path(thefolderStr)
        for c in thefolder.iterdir():
            if c.is_file():
                theprefix = datetime.fromtimestamp(c.stat().st_mtime).strftime("%Y%m%d") + "_"
                if not c.name.startswith(theprefix):
                    newFile = thefolder / (theprefix + c.name)
                    if newFile.exists():
                        print("ignoring existing item: " + str(newFile.absolute().as_posix()))
                    else:
                        c.rename(newFile)

if __name__ == "__main__":
    folders = sys.argv[1:]
    addDatePrefix(folders=folders)

