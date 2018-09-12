import os
import re
import shutil
from collections import defaultdict
from datetime import datetime

_common_imgext = [
    "jpg", "jpeg", "png", "gif"
]

ANYPAT = r".*"
ANYIMGPAT = "|".join(
    r"(.*\.{})".format(ext) for ext in _common_imgext
)
PXVIMGPAT = r"\d{8,}_p\d+\..*"
MONTH_ABBR = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec"
]

regpxvimg = re.compile(PXVIMGPAT)
reganyimg = re.compile(ANYIMGPAT)
regany = re.compile(ANYPAT)


def find_matched(walkroot=".", fpat=regpxvimg, dirpat=regany):
    """Walk through directories matches dirpat and return files matches fpat."""
    fullpathes = list()
    for root, dirs, files in os.walk(walkroot):
        for f in files:
            if fpat.match(f):
                fullpathes.append(
                    os.path.join(root, f)
                )
        dirs[:] = list(filter(dirpat.match, dirs))
        #   Filtering directories to walk.
        #   Must modify dirs to walk with slice and the parameter "topdown"
        #   is set "True".
    return fullpathes

def collect(destdir="sum", srcs=[]):
    """Collect files from srcs to destdir."""
    count = 0
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    dst_src = [
        (
            os.path.join(destdir, os.path.split(s)[1]),
            s
        )
        for s in srcs
    ]
    for dst, src in dst_src:
        if os.path.exists(dst):
            continue
        _ = shutil.copy2(src, dst)
        count += 1
    return count

def sumfmt(prefix="sum"):
    now = datetime.now()
    s = "_".join(
        [prefix, str(now.year), MONTH_ABBR[now.month - 1]]
    )
    return s

def count_by_ext(pathes):
    dct = defaultdict(list)
    for p in pathes:
        dct[p.rsplit(".", maxsplit=1)].append(p)
    return dct

if __name__ == "__main__":
    test = find_matched(".", regpxvimg)
    print(len(test))
    c = collect(destdir=sumfmt("sum"), srcs=test)
    print(c)
    