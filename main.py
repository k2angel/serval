import argparse
import json
import os
import re
import signal
import sys
from urllib import parse

import requests
from bs4 import BeautifulSoup as bs

from modules import global_var
from modules.api import APIError
from modules.client import Client
from modules.common import Color, Table
from modules.global_var import domain, sld, tld, base_url, user_agent


# ページを解析してユーザIDを取得、urlを生成する
def url_gen(url):
    headers = {
        "User-Agent": user_agent
    }
    parse_result = parse.urlparse(url)
    url_domain = parse_result.hostname
    if m := re.match(rf"{sld}\.({'|'.join(tld)})", url_domain):
        kemono_path = parse_result.path
    elif re.fullmatch(r"\w+\.fanbox\.cc", url_domain):
        res = requests.get(f"https://{url_domain}", headers=headers)
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
            kemono_path = f"/fanbox/user/{user_id}/post/{m.group(2)}"
        else:
            kemono_path = f"/fanbox/user/{user_id}"
    elif "www.pixiv.net" == url_domain or "pixiv.net" == url_domain:
        if m := re.match(r"https://(www\.)?pixiv.net/fanbox/creator/(\d+)", url):
            kemono_path = f"/fanbox/user/{m.group(2)}"
        elif m := re.match(r"https://(www\.)?pixiv.net/users/(\d+)", url):
            kemono_path = f"/fanbox/user/{m.group(2)}"
        elif m := re.match(r"https://(www\.)?pixiv.net/member\.php\?id=(\d+)", url):
            kemono_path = f"/fanbox/user/{m.group(2)}"
        else:
            return None
    elif "fantia.jp" == url_domain:
        if m := re.match(r"https://fantia\.jp/(fanclubs|posts)/(\d+)", url):
            if m.group(1) == "fanclubs":
                kemono_path = f"/fantia/user/{m.group(2)}"
            else:
                res = requests.get(url, headers=headers)
                if res.status_code == 404:
                    return None
                soup = bs(res.text, "html.parser")
                user = json.loads(soup.select_one("head script[type='application/ld+json']").text)
                user_url = user["author"]["url"]
                m_ = re.fullmatch(r"https://fantia\.jp/(fanclubs|posts)/(\d+)/?", user_url)
                kemono_path = f"/fantia/user/{m_.group(2)}/post/{m.group(2)}"
        else:
            return None
    elif "www.patreon.com" == url_domain:
        if m := re.fullmatch(r"https://www.patreon.com/user(/posts)?\?u=(\d+)", url):
            kemono_path = f"/patreon/user/{m.group(2)}"
        elif m := re.match(r"https://www\.patreon\.com/(\w+)/?", url):
            res = requests.get(url, headers=headers)
            if res.status_code == 404:
                return None
            soup = bs(res.text, "html.parser")
            user = json.loads(soup.select_one("#__NEXT_DATA__").text)
            if m.group(1) == "posts":
                m = re.fullmatch(r"https://www\.patreon\.com/posts/(.+)-(\w+)/?", url)
                user_id = user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"]["post"]["data"]["relationships"][
                    "user"
                ]["data"]["id"]
                kemono_path = f"/patreon/user/{user_id}/post/{m.group(2)}"
            else:
                user_id = user["props"]["pageProps"]["bootstrapEnvelope"]["bootstrap"]["campaign"]["data"][
                    "relationships"
                ]["creator"]["data"]["id"]
                kemono_path = f"/patreon/user/{user_id}"
        else:
            return None
    elif re.fullmatch(r"\w+\.gumroad.com", url_domain):
        res = requests.get(f"https://{url_domain}", headers=headers)
        if res.status_code == 404:
            return None
        soup = bs(res.text, "html.parser")
        user = json.loads(soup.select_one("body script[data-component-name='Profile']").text)
        user_id = user["creator_profile"]["external_id"]
        if m := re.match(r"https://(\w+)\.gumroad\.com/l/(\w+)", url):
            kemono_path = f"/gumroad/user/{user_id}/post/{m.group(2)}"
        else:
            kemono_path = f"/gumroad/user/{user_id}"
    else:
        return None

    return base_url+kemono_path


# ユーザー一覧を更新
def update():
    print("Updating Creators...")
    client.creators(True)
    print(Color.GREEN + "Creators was updated successfully!" + Color.RESET)


# ユーザーを検索
def search():
    if global_var.args.update:
        update()

    creators_data = client.search_creator(global_var.args.name, global_var.args.service)
    if not creators_data:
        print(f'{Color.YELLOW}Not found "{global_var.args.name}" in creators list.{Color.RESET}')
        print(
            f"Try again after running the command below, {Color.GREEN}{os.path.basename(sys.argv[0])} update{Color.RESET}"
        )
        return

    # 結果を表示
    table = Table()
    table.add_column("Name")
    table.add_column("ID")
    table.add_column("Service")
    table.add_column("URL")

    for creator in creators_data:
        table.add_row(creator["name"], creator["id"], creator["service"], creator["url"])

    table.print()


def main():
    args_error = False
    if global_var.args.word is not None and len(global_var.args.word) < 2:
        Color.warn('For "word": Value must be at least 2 characters.')
        args_error = True
    if global_var.args.page == 0:
        Color.warn('For "page": The value must be at least 1.')
        args_error = True
    if args_error:
        return
    url = url_gen(global_var.args.url)
    parse_result = parse.urlparse(url)
    if parse_result.hostname == domain:
        global_var.args_dict = vars(global_var.args)
        global_var.enable_filter = any([global_var.args_dict[k] for k in global_var.types])

        try:
            if result := re.match(r"/discord/server/(\d+)/(\d+)", parse_result.path):
                server_id, channel_id = result.groups()  # noqa: F841
                return
            elif result := re.match(r"/discord/server/(\d+)", parse_result.path):
                server_id = result.groups()  # noqa: F841
                return
            if result := re.match(rf"/({'|'.join(services)})/user/(\w+)/post/(\w+)", parse_result.path):
                service, creator_id, post_id = result.groups()
                client.post(service, creator_id, post_id)
            elif result := re.match(rf"/({'|'.join(services)})/user/(\w+)", parse_result.path):
                service, creator_id = result.groups()
                client.creator(service, creator_id)
        except APIError as e:
            Color.error(str(e))
            return

        try:
            client.download()
        except KeyboardInterrupt:
            Color.warn("Download interrupted.")


client = Client()
services = ["patreon", "fanbox", "discord", "fantia", "afdian", "boosty", "gumroad", "subscribestar", "dlsite"]
version = "0.3"
signal.signal(signal.SIGINT, signal.SIG_DFL)

# 引数の解析
if __name__ == "__main__":
    # バージョン表示
    version_parser = argparse.ArgumentParser(add_help=False)
    version_parser.add_argument("-v", "--version", action="store_true")
    args, unknown = version_parser.parse_known_args()

    # バージョンを表示した場合終了
    if args.version:
        print("serval v" + version)
        sys.exit(0)

    parser = argparse.ArgumentParser(parents=[version_parser])
    subparser = parser.add_subparsers()

    _download = subparser.add_parser(
        "download",
        help="urlを基にダウンロードします",
        epilog=f"対応サイト一覧: [{sld}({', '.join(tld)}), pixiv.net, fanbox.cc(不安定), fantia.jp, patreon.com, gumroad.com]",
    )
    _download.add_argument("url", type=str, help="urlを指定します (対応サイト一覧参照)")
    _download.add_argument("-p", "--page", type=int, help="指定したページの投稿のみをダウンロードします")
    _download.add_argument(
        "-w", "--word", type=str, help="指定したワードがタイトルに入っている場合ダウンロードします (二文字以上限定)"
    )
    _download.add_argument(
        "-bw", "--block-word", type=str, help="指定したワードがタイトルに入っている場合ダウンロードしません"
    )
    _download.add_argument("--tag", type=str, help="指定したタグが付けられているポストをダウンロードします")
    for k, v in global_var.types.items():
        if v["short"] is None:
            _download.add_argument("--" + k, action="store_true", help=v["help"] + "ファイルのみダウンロードします")
        else:
            _download.add_argument(
                "-" + v["short"], "--" + k, action="store_true", help=v["help"] + "ファイルのみダウンロードします"
            )
    # _download.add_argument("--url", action="store_true", help="投稿本文にあるurlのショートカットを作成します")
    _download.add_argument("--cover", action="store_true", help="カバー/ヘッダー画像があるかどうか解析します (fanboxのみ)")
    _download.add_argument("--flat", action="store_true", help="投稿毎にフォルダを作成しないようにします")
    # _download.add_argument("-e", "--extract", action="store_true", help="圧縮ファイルを解凍します (解凍する場合は新しいフォルダの中に展開します)")
    _download.set_defaults(handler=main)

    _search = subparser.add_parser("search", help="ユーザーを検索します")
    _search.add_argument("name", type=str, help="検索するユーザー名")
    _search.add_argument("--service", choices=services, help="検索するサイトを指定")
    _search.add_argument("--update", action="store_true", help="ユーザー一覧を更新したあとに検索します")
    _search.set_defaults(handler=search)

    _update = subparser.add_parser("update", help="ユーザー一覧を更新します")
    _update.set_defaults(handler=update)

    # 引数をグローバル変数に
    global_var.args = parser.parse_args()
    print(global_var.args)

    # サブコマンドのハンドラを実行
    if hasattr(global_var.args, "handler"):
        global_var.args.handler()
    else:
        # サブコマンドが指定されていないときはヘルプメッセージを表示
        parser.print_help()
