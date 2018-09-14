import json

import requests

headers = {
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

url = (
    "https://www.pixiv.net/ajax/showcase/latest"
)

param = {
    "page": 1,
    "article_num": 16
}
#   if page is out of range, received article will less than article_num.


session = requests.Session()

resp = session.get(url, headers=headers, params=param)

if resp.status_code == 200:
    js = json.loads(resp.text, encoding='utf-8')
    if js['error']:
        print(js['message'])
    else:
        print(len(js['body']))
else:
    print("something goes wrong.")
    print(resp.status_code)