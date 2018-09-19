import asyncio
import datetime
import enum
import json
import logging
import math
import os
import pytz
import random
import re
import sys
import time

from collections import namedtuple

import aiohttp


#---------------------------------------------------------------------------#
#   pypxv                                                                   #
#       Python pixiv ranking/spotlight downloader.                          #
#       Featuring asynchronous downloading.                                 #
#       Login on python is not required.                                    #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   Constants and generic objects                                           #
#---------------------------------------------------------------------------#


class _StrEnum(str, enum.Enum):
    pass


class IllustType(_StrEnum):
    ILLUST = "0"
    MANGA = "1"
    UGOIRA = "2"


class HTTPStatus(enum.IntEnum):
    OK = 200
    NOT_FOUND = 404


RANKING_URL = "https://www.pixiv.net/ranking.php"
SPOTLIGHT_MAIN_URL = "https://www.pixiv.net/ajax/showcase/article"
SPOTLIGHT_QUERYLIST_URL = "https://www.pixiv.net/ajax/showcase/latest"

UGOIRA_META_template = "https://www.pixiv.net/ajax/illust/{:8d}/ugoira_meta"

DEFAULT_SAVEDIR = "pixiv_image"
DEFAULT_FILEFMT = "%Y_%m_%d"

MODE_PAGE = {
    "daily": 10,
    "weekly": 10,
    "rookie": 6,
    "original": 6,
    "male": 10,
    "female": 10
}
AVAILABLE_CONTENTS = [
    "illust", "manga", "ugoira"
]
AVAILABLE_MODES = list(MODE_PAGE.keys())
ILLUST_ATTRS = [
    "attr",
    "date",
    "height",
    "illust_book_style",
    "illust_content_type",
    "illust_id",
    "illust_page_count",
    "illust_series",
    "illust_type",
    "illust_upload_timestamp",
    "profile_img",
    "rank",
    "rating_count",
    "tags",
    "title",
    "url",
    "user_id",
    "user_name",
    "view_count",
    "width",
    "yes_rank"
]
COMMON_EXTS = ["jpg", "png", "gif", "bmp", "zip"]
RANKING_REFERER = (
    "https://www.pixiv.net/member_illust.php?"
    "mode=medium&illust_id="
)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/63.0.3239.132 Safari/537.36"
)
CAMOUFLAGE_HEADERS = {
    "User-Agent": _USER_AGENT,
}
SPOTLIGHT_LIST_HEADERS = {
    "Host": "www.pixiv.net",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) "
        "Gecko/20100101 Firefox/62.0"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.pixiv.net/showcase/",
}

#   Too many concurrent connection may cause you cut from server.
#   This value is safe for now.
SEM_LIMIT = 5

_logstrfmt = "{asctime}|{name}|{levelname:^7s}| {message}"
_logtimefmt = "%H:%M:%S"
_filetimefmt = "%Y-%m-%d %H:%M:%S"

_logfile = "./pixiv.log"

_console_formatter = logging.Formatter(_logstrfmt, _logtimefmt, "{")
_file_formatter = logging.Formatter(_logstrfmt, _filetimefmt, "{")

_console_hdl = logging.StreamHandler(sys.stdout)
_console_hdl.setFormatter(_console_formatter)
_file_hdl = logging.FileHandler(_logfile, "a+", "utf-8")
_file_hdl.setFormatter(_file_formatter)

_pxvroot = logging.getLogger("Pixiv")
_pxvroot.setLevel(logging.INFO)
_pxvroot.addHandler(_console_hdl)
_pxvroot.addHandler(_file_hdl)

pxlog = _pxvroot    #   Alias

#   A better name?
_thumbnail_suffix = r"p0_master1200\..*"
_thumbnail_suffix_sc = r"master1200\..*"
_thumbnail_middle = r"c/\d+x\d+(_\d*)?/img-master"
_origin_image = "img-original"
_origin_ugoira = "img-zip-ugoira"
_suffix_image = "p{page}"
_suffix_ugoira = "ugoira1920x1080"

_pat_thumbnail_mid = re.compile(_thumbnail_middle)
_pat_thumbnail_suf = re.compile(_thumbnail_suffix)
_pat_thumbnail_sc_suf = re.compile(_thumbnail_suffix_sc)

_origin_mid = {
    IllustType.ILLUST: _origin_image,
    IllustType.MANGA: _origin_image,
    IllustType.UGOIRA: _origin_ugoira
}
_origin_suf = {
    IllustType.ILLUST: _suffix_image,
    IllustType.MANGA: _suffix_image,
    IllustType.UGOIRA: _suffix_ugoira
}

_loop = asyncio.get_event_loop()
_sem = asyncio.Semaphore(SEM_LIMIT)

#---------------------------------------------------------------------------#
#   NOTE                                                                    #
#       Since all 3 types of illust will turn into the same intermediate    #
#   data.                                                                   #
#   raw json -(dispatcher)-> dict/namedtuple metadata -(post process)-> ... #
#   ... series of necessary data;                                           #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   Metadata structure and enums                                            #
#---------------------------------------------------------------------------#


_illust_meta_fields = [
    "illust_id",            #   int
    "illust_page_count",    #   int *from str
    "template_url",         #   str *can be used in str.format form.
    "illust_type"           #   str *see "IllustType"
]
NewIllustMeta = namedtuple(
    "IllustMeta", _illust_meta_fields
)

_illust_derived_fields = [
    "illust_id",
    "url",
    "format"                #   Or preforge with two fields above?
]
NewIllustDerived = namedtuple(
    "IllustDerived", _illust_derived_fields
)

_pattern_table = {
    IllustType.ILLUST: (_pat_thumbnail_mid, _pat_thumbnail_suf),
    IllustType.MANGA: (_pat_thumbnail_mid, _pat_thumbnail_suf),
    IllustType.UGOIRA: (_pat_thumbnail_mid, _pat_thumbnail_sc_suf)
}

def _make_illust_meta(content):
    illust_id = content["illust_id"]
    illust_page_count = int(content["illust_page_count"])
    illust_type = content["illust_type"]

    if "spotlight_article_id" in content.keys():
        url = content["url"]["768x1200"]
    else:
        url = content["url"]

    pat_mid, pat_suf = _pattern_table[illust_type]

    #   These name may somehow confusing.
    url = pat_mid.sub(
        _origin_mid[illust_type], url
    )
    url = pat_suf.sub(
        _origin_suf[illust_type], url
    )
    return NewIllustMeta(
            illust_id,
            illust_page_count,
            url,
            illust_type
        )

def _make_derived_fields(meta, ext):
    deriveds = list()
    tmp_url = str()
    for i in range(meta.illust_page_count):
        tmp_url = meta.template_url.format(illust_id=meta.illust_id, page=i)
        tmp_url += f".{ext}"
        deriveds.append(
            NewIllustDerived(
                "{illust_id}_p{page}".format(illust_id=meta.illust_id, page=i),
                tmp_url, ext
            )
        )
    return deriveds

def _make_sample_url(meta, ext):
    sample = meta.template_url.format(illust_id=meta.illust_id, page=0)
    sample += f".{ext}"
    return sample


#---------------------------------------------------------------------------#
#   Exposed APIs                                                            #
#---------------------------------------------------------------------------#


def fetch_ranking_info(date="", mode="daily", content="", pages=-1):
    """
    Fetch daily(or other period) ranking info.

    Args:
        date        string
            Date represented in form of YYYYMMDD.
        mode        string
            See "AVAILABLE_MODES".
        content     string
            See "AVAILABLE_CONTENTS".
        pages       int
            If page == -1, fetches all page, otherwise follows input param.
            For the maximum page available, see "MODE_PAGES".
            Illust per page is 50.

    Returns:
        dict from deserialized json, contains infos about ranking illusts.
    
    Raises:
        ValueError
            User input an invalid date, that is, a date latter than most recent
            published ranking. *See ranking publish rule.
        Any type of connection error.
            --
    """
    if not date:
        date = _make_most_recent_date()
    else:
        if not _is_valid_date(date):
            raise ValueError("Invalid date")
    queries = _make_query(
        date, mode, content, pages
    )
    pxlog.info(f"Start fetching ranking {date} info")
    coro = _query_dispatcher(
        RANKING_URL, queries, headers=CAMOUFLAGE_HEADERS
    )
    texts = _loop.run_until_complete(coro)
    #   Stupid way solving name conflict.
    jscontent = _merge_json(texts)

    pxlog.info("Fetching ranking info ok")
    return jscontent

def fetch_spotlight_info(feature):
    """
    Fetch spotlight info.

    Args:
        feature     int
            Spotlight code represented in url, should be a 4-digits number.
    
    Returns:
        dict from deserialized json, contains infos about spotlight illusts.
    
    Raises:
        Any type of connnection error.
    """
    content = dict()
    pxlog.info(f"Start fetching spotlight {feature} info")
    text = _loop.run_until_complete(
        _spotlight_fetcher(feature)
    )
    content = json.loads(text, encoding="utf-8")
    pxlog.info("Fetching spotlight info ok")
    return content

def fetch_spotlight_list(article_num=17, pages=1):
    """
    Fetch list of published spotlight.

    Args:
        article_num     int
            Number of spotlight metadata per queried page.
        pages           int
            Number of queried page.
    
    Returns:
        dict from deserialized json, contains spotlight metadatas.
    
    Raises:
        Any type of connection error.
    """
    content = dict()
    pxlog.info(
        "Start fetching spotlight list {}/page (total: {})".format(
            article_num, article_num * pages
        )
    )
    queries = [
        {"page": i, "article_num": article_num}
        for i in range(1, pages+1)
    ]

    texts = _loop.run_until_complete(
        _query_dispatcher(
            SPOTLIGHT_QUERYLIST_URL, queries, headers=SPOTLIGHT_LIST_HEADERS
        )
    )
    
    #   More generalized "_merge_json"?
    #   Use "operator.itemgetter".
    for t in texts:
        if content:
            content["body"].extend(
                json.loads(t, encodong="utf-8")["body"]
            )
        else:
            content = json.loads(t, encoding="utf-8")

    pxlog.info(
        "Fetch spotlight list info ok"
    )
    return content

def download_spotlight(
        feature,
        *,
        savedir=DEFAULT_SAVEDIR, dirname=""
    ):
    """
    Download spotlight illusts with given feature code.

    Args:
        feature     int
            Spotlight code represented in url, should be a 4-digits number.
        savedir     string
            Directory of illust to place.
        dirname     string
            Directory name containing illusts.
    
    Returns:
        list of integer, indicated downloaded bytes.
    
    Raises:
        aiohttp.ServerDisconnectedError
            Too much concurrent connection or dense request 
            may result in this error.
    """
    #   Add more options:   savedir, dirname
    content = fetch_spotlight_info(feature)
    #   Forging save path.
    if not dirname:
        dirname = "Spotlight_{feature}".format(feature=feature)
    fullpath = os.path.join(savedir, dirname)
    metadatas = list(map(_make_illust_meta, content["body"][0]["illusts"]))
    return _download("spotlight", metadatas, fullpath)

def filter_content(contents, rules, mode=any):
    """
    Filter contents by given rule.

    Args:
        contents    list
            List of illust, the content may vary from source to source.
            Besure you know the data hierachy of object.
        rules       list
            A list of function takes one content and returns boolean value,
            indicating the content is selected.
        mode        `any` or `all`
            Choose wether satisfy all rules or any of them.
    
    Returns:
        list of filtered contents.
    
    Raises:
        None
    """
    if not (mode in (any, all)):
        raise ValueError("Accept only one of 'any' or 'all'.")
    res = []
    for i in contents:
        if mode(r(i) for r in rules):
            res.append(i)
    return res

def download_ranking(
        date="", mode="daily", content="", pages=-1, targets=[],
        *,
        savedir=DEFAULT_SAVEDIR, dirname=""
    ):
    """
    Download ranking illusts.

    Args:
        date        string
            Date represented in form of YYYYMMDD.
        mode        string
            See "AVAILABLE_MODES".
        content     string
            See "AVAILABLE_CONTENTS".
        pages       int
            If page == -1, fetches all page, otherwise follows input param.
            For the maximum page available, see "MODE_PAGES".
            Illust per page is 50.
        targets     list
            list of illust_id, which is an integer.
            Illust_id is a 8-digits natural number that strictly growing up,
            could up to 9-digits in the future.
        savedir     string
            Directory of illust to place.
        dirname     string
            Directory name containing illusts.
    
    Returns:
        list of integer, indicated downloaded bytes.
    
    Raises:
        aiohttp.ServerDisconnectedError
            Too much concurrent connection or dense request 
            may result in this error.
    """
    js = fetch_ranking_info(date, mode, content, pages)
    #   Forging save path.
    if not date:
        date = js["date"]
    datestr = datetime.datetime.strptime(date, "%Y%m%d")
    if not dirname:
        dirname = datetime.datetime.strftime(datestr, DEFAULT_FILEFMT)
    fullpath = os.path.join(savedir, dirname)
    #   Filtering by given name.
    ok = _filter_by_name(js["contents"], targets)
    metadatas = list(map(_make_illust_meta, ok))
    return _download("ranking", metadatas, fullpath)

def _download(taskname, metadatas, fullpath):
    """
    Core function of launching concurrent tasks.
    
    Args:
        taskname    string
            Name for logging.
        metadatas   `IllustMeta`
            Processed metadata, extracted from ranking info or spotlight info.
            Should only generated by '_make_illust_meta'.
        fullpath    string
            Path of a directory, saving downloaded images.
    
    Returns:
        list of integer, indicates bytes downloaded.
    
    Raises:
        aiohttp.ServerDisconnectedError
            Too much concurrent connection or dense request 
            may result in this error.
    """
    start = time.perf_counter()
    pxlog.info("Start download illusts")

    downloaded = _loop.run_until_complete(
        _chaining(metadatas, fullpath)
    )

    pxlog.info(f"Download {taskname} ok")
    elapsed = time.perf_counter() - start
    total_size = sum(downloaded)
    avg_speed = total_size / elapsed
    pxlog.info(
        f"Elapsed time: {elapsed:.2f} s, avg: {byte2human(avg_speed)}/s"
    )
    pxlog.info(
        f"Total {len(downloaded)} illusts, {byte2human(total_size)}"
    )
    return downloaded


#---------------------------------------------------------------------------#
#   Precedures                                                              #
#---------------------------------------------------------------------------#


async def _spotlight_fetcher(feature):
    #   TODO hard-coded constant?
    query = {"article_id": feature}
    text = str()
    async with aiohttp.ClientSession(
            loop=_loop, headers=CAMOUFLAGE_HEADERS, raise_for_status=True
        ) as client:
        async with client.get(SPOTLIGHT_MAIN_URL, params=query) as resp:
            text = await resp.text()

    return text

async def _query_dispatcher(
        url, queries, *, headers=dict()
    ):
    """ Launching concurrent queries with given headers. """
    #   if page is out of range, received article will less than article_num.
    texts = []
    async with aiohttp.ClientSession(
            loop=_loop, headers=headers
        ) as client:
        try:
            tasks = [
                _query_fetcher(client, url, q)
                for q in queries
            ]
            gat = asyncio.gather(*tasks, loop=_loop)
            texts = await gat
        except Exception:
            gat.cancel()
            raise
    return texts

async def _query_fetcher(client, url, query):
    async with _sem:
        await asyncio.sleep(random.random() * 0.7 + 0.3, loop=_loop)
        async with client.get(url, params=query) as resp:
            text = await resp.text()
    return text

async def _chaining(metadatas, dirname):
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    #   This layer intends to reuse session, but does it really works?
    async with aiohttp.ClientSession(
            loop=_loop, headers=CAMOUFLAGE_HEADERS
        ) as client:
        #   Not using raise for status, status is necessary in judging
        #   file extensions.
        approved = await _ext_dispatcher(client, metadatas)
        downloaded = await _dl_dispatcher(client, approved, dirname)
    return downloaded

async def _ext_dispatcher(client, metadatas):
    pxlog.debug("Start trying file exts")
    tasks = [
        _loop.create_task(_ext_fetcher(client, m))
        for m in metadatas
    ]
    gat = asyncio.gather(*tasks, loop=_loop)
    try:
        res = await gat
    except:
        #   Cancel once error occurs, purge pending tasks.
        gat.cancel()
        raise
    #   Unwind nested list.
    res = [i for each in res for i in each]
    pxlog.debug("Tried {} files".format(len(res)))
    return res

async def _ext_fetcher(client, metadata):
    async with _sem:
        res = await _ext_core(client, metadata)
    return res

async def _ext_core(client, metadata):
    #   If a file ext is not found, return enpty list.
    header = {"referer": RANKING_REFERER}
    pxlog.debug("Trying {}".format(metadata.illust_id))
    #   The file ext of type UGOIRA is determined.
    if metadata.illust_type == IllustType.UGOIRA:
        return _make_derived_fields(metadata, 'zip')
    for ext in COMMON_EXTS:
        await asyncio.sleep(random.random()*2 + 0.3, loop=_loop)
        sample_url = _make_sample_url(metadata, ext)
        async with client.head(sample_url, headers=header) as resp:
            status = resp.status
            if status == HTTPStatus.OK:
                pxlog.debug("{} -> {}".format(metadata.illust_id, ext))
                return _make_derived_fields(metadata, ext)
            elif status == HTTPStatus.NOT_FOUND:
                continue
            else:
                pxlog.debug(
                    "Status of {}: {}".format(metadata.illust_id, status)
                )
            pass
        pass
    #   Prompt for not found.
    #   Return empty list for not hit.
    pxlog.info("{} extension not found".format(metadata.illust_id))
    return []

async def _dl_dispatcher(client, deriveds, dirname):
    pxlog.debug("Dispatching download tasks: {}".format(len(deriveds)))
    tasks = [
        _loop.create_task(_dl_fetcher(client, drv, dirname))
        for drv in deriveds
    ]
    gat = asyncio.gather(*tasks, loop=_loop)
    try:
        res = await gat
    except:
        gat.cancel()
        raise
    return res

async def _dl_fetcher(client, derived, dirname):
    #   Simple layer to save indent.
    async with _sem:
        await asyncio.sleep(random.random()*2 + 0.3)
        res = await _dl_core(client, derived, dirname)
    return res

async def _dl_core(client, derived, dirname):
    pxlog.debug("Start download {}".format(derived.illust_id))
    start = time.perf_counter()
    elapsed = 0
    size = 0
    header = {"referer": RANKING_REFERER}

    target_url = derived.url
    fname = derived.illust_id + f".{derived.format}"
    fullname = os.path.join(dirname, fname)

    try:
        async with client.get(target_url, headers=header) as resp:
            if resp.status == HTTPStatus.NOT_FOUND:
                pxlog.info("Not found {}".format(target_url))
                return size
            resp.raise_for_status()
            size += await _write_stream(resp, fullname)
    except aiohttp.ServerDisconnectedError as server_err:
        if os.path.exists(fullname):
            #   Clean up possible incomplete file.
            os.remove(fullname)
        pxlog.critical(
            "Disconnected by server, one possible reason is the interval" + \
            "between each connection is too short."
        )
        raise server_err
    else:
        elapsed = time.perf_counter() - start
        pxlog.info(
            "{file:14s} {size:10s} {elapsed:>4.1f} s".format(
                file=derived.illust_id, size=byte2human(size), elapsed=elapsed
            )
        )
    return size

async def _write_stream(resp, fpath, chunk_size=4096):
    n = 0
    reader = resp.content
    with open(fpath, "wb") as f:
        async for chunk in reader.iter_chunked(chunk_size):
            n += f.write(chunk)
    return n

#---------------------------------------------------------------------------#
#   Helpers                                                                 #
#---------------------------------------------------------------------------#

def _make_query(date="", mode="daily", content="", pages=-1):
    if not (mode in AVAILABLE_MODES):
        raise ValueError(f"Unknown mode: {mode}")
    if pages < 0:
        pages = MODE_PAGE[mode]
    else:
        pages = pages if pages <= MODE_PAGE[mode] else MODE_PAGE[mode]
    queries = [
        {
            "mode": mode,
            "p": str(i + 1),
            "format": "json"
        }
        for i in range(pages)
    ]
    if date:
        for q in queries:
            q.update({"date": date})
    if content and (content in AVAILABLE_CONTENTS):
        for q in queries:
            q.update({"content": content})
    return queries

def _is_valid_date(date):
    now = datetime.datetime.now()
    target = datetime.datetime.strptime(date, "%Y%m%d")
    if target > now:
        return False
    return True

def _make_most_recent_date():
    timezone = "Asia/Tokyo"
    local_now = datetime.datetime.now()
    tokyo_now = local_now.astimezone(pytz.timezone(timezone))
    delta_day = tokyo_now.date() - local_now.date()
    delta = 1   \
        if tokyo_now.hour > 12 or delta_day.days == 1 else \
            2
    date = local_now - datetime.timedelta(days=delta)
    return date.strftime("%Y%m%d")

def _merge_json(texts):
    dict_content = dict()
    for t in texts:
        if dict_content:
            dict_content["contents"].extend(
                json.loads(t, encoding="utf-8")["contents"]
            )
        else:
            dict_content = json.loads(t, encoding="utf-8")
    dict_content["contents"].sort(key=lambda x: x["rank"])
    return dict_content

def _is_ugoira(content) -> bool:
    return content["illust_type"] == IllustType.UGOIRA

def _is_illust_fresh(content) -> bool:
    yes_rank = content["yes_rank"]
    return yes_rank <= 0 or yes_rank > 500

def _filter_by_name(contents, targets):
    id_set = set(targets)
    ok = [
        i
        for i in contents
        if i["illust_id"] in id_set
    ]
    return ok

def _filter_by_condition(contents, *conditions):
    ok = [
        i 
        for i in contents
        if all(cond(i) for cond in conditions)
    ]
    return ok

def byte2human(b):
    """
    Convert byte to human-readable representation.
    
    Args:
        b       int
            Bytes
    
    Returns:
        string of byte in human-readable representation.
    
    Raises:
        None
    """
    unit_suffix = [
        "", "K", "M", "G", "T", "P", "E", "Z", "Y"
    ]
    expo = lambda byt: math.floor(math.log(byt, 1024))
    if b > 0:
        mag = expo(b)
    else:
        mag = 0
    if mag > 8:
        mag=8
    expr = f"{b/(1024**mag):8.3f} {unit_suffix[mag]}B"
    return expr
