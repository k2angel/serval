import argparse
import json
import os
import re
import sys
from urllib import parse

import requests
from bs4 import BeautifulSoup as bs

from modules.client import Client
from modules.common import Color, Table


def url_gen(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    domain = parse.urlparse(url).hostname
    if "kemono.su" == domain:
        kemono_url = url
    elif re.fullmatch(r"\w+\.fanbox\.cc", domain):
        res = requests.get(f"https://{domain}", headers=headers)
        if res.status_code == 404:
            return None
        soup = bs(res.text, "html.parser")
        og_image = soup.select_one("head > meta[property='og:image']")
        content = og_image.get("content")
        try:
            user_id = re.match(
                r"https://pixiv.pximg.net/c/\w+/fanbox/public/images/creator/(\d+)",
                content,
            ).group(1)
        except AttributeError:
            return None
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
            return None
    elif "fantia.jp" == domain:
        if m := re.match(r"https://fantia\.jp/(fanclubs|posts)/(\d+)", url):
            if m.group(1) == "fanclubs":
                kemono_url = f"https://kemono.su/fantia/user/{m.group(2)}"
            else:
                res = requests.get(url, headers=headers)
                if res.status_code == 404:
                    return None
                soup = bs(res.text, "html.parser")
                user = json.loads(
                    soup.select_one("head script[type='application/ld+json']").text
                )
                user_url = user["author"]["url"]
                m_ = re.fullmatch(
                    r"https://fantia\.jp/(fanclubs|posts)/(\d+)/?", user_url
                )
                kemono_url = (
                    f"https://kemono.su/fantia/user/{m_.group(2)}/post/{m.group(2)}"
                )
        else:
            return None
    elif "www.patreon.com" == domain:
        if m := re.fullmatch(r"https://www.patreon.com/user(/posts)?\?u=(\d+)", url):
            kemono_url = f"https://kemono.su/patreon/user/{m.group(2)}"
        elif m := re.match(r"https://www\.patreon\.com/(\w+)/?", url):
            res = requests.get(url, headers=headers)
            if res.status_code == 404:
                return None
            soup = bs(res.text, "html.parser")
            user = json.loads(soup.select_one("#__NEXT_DATA__").text)
            if m.group(1) == "posts":
                m = re.fullmatch(r"https://www\.patreon\.com/posts/(.+)-(\w+)/?", url)
                user_id = user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"][
                    "post"
                ]["data"]["relationships"]["user"]["data"]["id"]
                kemono_url = (
                    f"https://kemono.su/patreon/user/{user_id}/post/{m.group(2)}"
                )
            else:
                user_id = user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"][
                    "campaign"
                ]["data"]["relationships"]["creator"]["data"]["id"]
                kemono_url = f"https://kemono.su/patreon/user/{user_id}"
        else:
            return None
    elif re.fullmatch(r"\w+\.gumroad.com", domain):
        res = requests.get(f"https://{domain}", headers=headers)
        if res.status_code == 404:
            return None
        soup = bs(res.text, "html.parser")
        user = json.loads(
            soup.select_one("body script[data-component-name='Profile']").text
        )
        user_id = user["creator_profile"]["external_id"]
        if m := re.match(r"https://(\w+)\.gumroad\.com/l/(\w+)", url):
            kemono_url = f"https://kemono.su/gumroad/user/{user_id}/post/{m.group(2)}"
        else:
            kemono_url = f"https://kemono.su/gumroad/user/{user_id}"
    else:
        return None

    return kemono_url


def update(args: None):
    print("Updating Creators...")
    client.creators(True)
    print(Color.GREEN + "Creators was updated successfully!" + Color.RESET)


def search(args):
    if args.update:
        update()

    creators_data = client.search_creator(args.name, args.service)
    if not creators_data:
        print(f'{Color.YELLOW}Not found "{args.name}" in creators list.{Color.RESET}')
        print(
            f"Try again after running the command below, {Color.GREEN}{os.path.basename(sys.argv[0])} update{Color.RESET}"
        )
        return

    table = Table()
    table.add_column("Name")
    table.add_column("ID")
    table.add_column("Service")
    table.add_column("URL")

    for creator in creators_data:
        table.add_row(
            creator["name"], creator["id"], creator["service"], creator["url"]
        )

    table.print()


def main(args):
    if args.word is not None and len(args.word) < 2:
        Color.warn('For "word": Value must be at least 2 characters.')
        return
    url = url_gen(args.url)
    parse_result = parse.urlparse(url)
    if parse_result.hostname == "kemono.su":
        if result := re.match(r"/discord/server/(\d+)/(\d+)", parse_result.path):
            server_id, channel_id = result.groups()
            return
        elif result := re.match(r"/discord/server/(\d+)", parse_result.path):
            server_id = result.groups()
            return
        if result := re.match(
            rf"/({'|'.join(services)})/user/(\w+)/post/(\w+)", parse_result.path
        ):
            service, creator_id, post_id = result.groups()
            client.post(service, creator_id, post_id)
        elif result := re.match(
            rf"/({'|'.join(services)})/user/(\w+)", parse_result.path
        ):
            service, creator_id = result.groups()
            client.creator(service, creator_id, args)

        client.download(args)


client = Client()
services = [
    "patreon",
    "fanbox",
    "discord",
    "fantia",
    "afdian",
    "boosty",
    "gumroad",
    "subscribestar",
    "dlsite",
]
download_url_dest = """
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()

    _download = subparser.add_parser("download", help="urlを基にダウンロードします", epilog="対応サイト一覧: [kemono.su, pixiv.net, fanbox.cc, fantia.jp, patreon.com, gumroad.com]")
    _download.add_argument("url", type=str, help="urlを指定します (discord非対応)")
    _download.add_argument("-p", "--page", type=int, help="指定したページの投稿のみをダウンロードします")
    _download.add_argument("-w", "--word", type=str, help="指定したワードがタイトルに入っている場合ダウンロードします (二文字以上限定)")
    _download.add_argument("-bw", "--block-word", type=str, help="指定したワードがタイトルに入っている場合ダウンロードしません")
    _download.add_argument("-i", "--image", action="store_true", help="画像のみダウンロードします")
    _download.add_argument("-a", "--archive", action="store_true", help="圧縮ファイルのみダウンロードします")
    _download.add_argument("-m", "--movie", action="store_true", help="動画ファイルのみダウンロードします")
    _download.add_argument("--psd", action="store_true", help="psdファイルのみダウンロードします")
    _download.add_argument("--pdf", action="store_true", help="pdfファイルのみダウンロードします")
    # _download.add_argument("-e", "--extract", action="store_true", help="圧縮ファイルを解凍します (解凍する場合は新しいフォルダの中に展開します)")
    _download.set_defaults(handler=main)

    _search = subparser.add_parser("search", help="ユーザーを検索します")
    _search.add_argument("name", type=str, help="検索するユーザー名")
    _search.add_argument("--service", choices=services, help="ユーザーのサイトを指定")
    _search.add_argument(
        "--update", action="store_true", help="ユーザー一覧を更新したあとに検索します"
    )
    _search.set_defaults(handler=search)

    _update = subparser.add_parser("update", help="ユーザー一覧を更新します")
    _update.set_defaults(handler=update)

    args = parser.parse_args()
    # print(args)

    if hasattr(args, "handler"):
        args.handler(args)
    else:
        parser.print_help()
