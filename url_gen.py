import json
import pprint
import re
import webbrowser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup as bs

"""
supported:
Fanbox, Fantia, Patreon, Gumroad
"""

# test data
# urls = ["https://toranoe.fanbox.cc/", "https://hmzz.fanbox.cc/posts", "https://tjuan.fanbox.cc/posts/6802249"]
# urls = ["https://fantia.jp/posts/2495125", "https://fantia.jp/fanclubs/3959", "https://fantia.jp/fanclubs/497105", "https://fantia.jp/fanclubs/265314"]
# urls = ["https://www.patreon.com/user?u=15327898", "https://www.patreon.com/user/posts?u=15327898", "https://www.patreon.com/HMZB", "https://www.patreon.com/posts/0-94457434"]
# urls = ["https://kkuddf.gumroad.com/", "https://hentairinhee.gumroad.com/", "https://hentairinhee.gumroad.com/l/tsnne?layout=profile"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

if __name__ == "__main__":
    while True:
        url = input("> ")
        domain = urlparse(url).hostname
        if domain is None:
            continue
        if re.fullmatch(r"\w+\.fanbox\.cc", domain):
            res = requests.get(f"https://{domain}", headers=headers)
            if res.status_code == 404:
                continue
            soup = bs(res.text, "html.parser")
            og_image = soup.select_one("head > meta[property='og:image']")
            content = og_image.get("content")
            try:
                user_id = re.match(r"https://pixiv.pximg.net/c/\w+/fanbox/public/images/creator/(\d+)", content).group(1)
            except AttributeError:
                print("err")
                continue
            if m := re.match(r"https://(\w+)\.fanbox\.cc/posts/(\d+)", url):
                kemono_url = f"https://kemono.su/fanbox/user/{user_id}/post/{m.group(2)}"
            else:
                kemono_url = f"https://kemono.su/fanbox/user/{user_id}"
        elif "www.pixiv.net" == domain or "pixiv.net" == domain:
            if m := re.match(r"https://(www\.)?pixiv.net/fanbox/creator/(\d+)", url):
                kemono_url = f"https://kemono.su/fanbox/user/{m.group(2)}"
            elif m := re.match(r"https://(www\.)?pixiv.net/users/(\d+)", url):
                kemono_url = f"https://kemono.su/fanbox/user/{m.group(2)}"
            elif m := re.match(r"https://(www\.)?pixiv.net/member\.php\?id=(\d+)", url):
                kemono_url = f"https://kemono.su/fanbox/user/{m.group(2)}"
            else:
                continue
        elif "fantia.jp" == domain:
            if m := re.match(r"https://fantia\.jp/(fanclubs|posts)/(\d+)", url):
                if m.group(1) == "fanclubs":
                    kemono_url = f"https://kemono.su/fantia/user/{m.group(2)}"
                else:
                    res = requests.get(url, headers=headers)
                    if res.status_code == 404:
                        continue
                    soup = bs(res.text, "html.parser")
                    user = json.loads(soup.select_one("head script[type='application/ld+json']").text)
                    user_url = user["author"]["url"]
                    m_ = re.fullmatch(r"https://fantia\.jp/(fanclubs|posts)/(\d+)/?", user_url)
                    kemono_url = f"https://kemono.su/fantia/user/{m_.group(2)}/post/{m.group(2)}"
            else:
                continue
        elif "www.patreon.com" == domain:
            if m := re.fullmatch(r"https://www.patreon.com/user(/posts)?\?u=(\d+)", url):
                kemono_url = f"https://kemono.su/patreon/user/{m.group(2)}"
            elif m := re.match(r"https://www\.patreon\.com/(\w+)/?", url):
                res = requests.get(url, headers=headers)
                if res.status_code == 404:
                    continue
                soup = bs(res.text, "html.parser")
                user = json.loads(soup.select_one("#__NEXT_DATA__").text)
                if m.group(1) == "posts":
                    m = re.fullmatch(r"https://www\.patreon\.com/posts/(.+)-(\w+)/?", url)
                    user_id = \
                    user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"]["post"]["data"]["relationships"]["user"][
                        "data"]["id"]
                    kemono_url = f"https://kemono.su/patreon/user/{user_id}/post/{m.group(2)}"
                else:
                    user_id = \
                    user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"]["campaign"]["data"]["relationships"][
                        "creator"]["data"]["id"]
                    kemono_url = f"https://kemono.su/patreon/user/{user_id}"
            else:
                continue
        elif re.fullmatch(r"\w+\.gumroad.com", domain):
            res = requests.get(f"https://{domain}", headers=headers)
            if res.status_code == 404:
                continue
            soup = bs(res.text, "html.parser")
            user = json.loads(soup.select_one("body script[data-component-name='Profile']").text)
            user_id = user["creator_profile"]["external_id"]
            if m := re.match(r"https://(\w+)\.gumroad\.com/l/(\w+)", url):
                kemono_url = f"https://kemono.su/gumroad/user/{user_id}/post/{m.group(2)}"
            else:
                kemono_url = f"https://kemono.su/gumroad/user/{user_id}"
        else:
            continue
        status_code = requests.head(kemono_url).status_code
        if status_code == 404 or status_code == 302:
            continue
        print(f"{url} -> {kemono_url}")
        webbrowser.open(kemono_url)
