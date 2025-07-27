import io
import json
import math
import os
from collections import deque
from zipfile import BadZipFile

from PIL import Image, UnidentifiedImageError
from tqdm import tqdm
from urllib3.exceptions import ProtocolError

from . import global_var
from .global_var import domain, base_url
from .api import Api
from .common import Color, Table, logger


class Client:
    def __init__(self):
        self.api = Api()
        self.deque = deque()
        self.logged = False

        self.creators(False)

    # キューをダウンロード
    def download(self):
        def convert_size(size):
            units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB")
            i = math.floor(math.log(size, 1024)) if size > 0 else 0
            size = round(size / 1024**i, 2)

            return f"{size} {units[i]}"

        folder_name = str.maketrans(
            {
                "　": " ",
                "\\": "＼",
                "/": "／",
                ":": "：",
                "*": "＊",
                "?": "？",
                '"': "”",
                "<": "＜",
                ">": "＞",
                "|": "｜",
            }
        )

        dsize = len(self.deque)
        if not dsize:
            Color.warn("There is nothing in the queue.")
            return

        table = Table()
        table.add_column("Title")
        table.add_column("ID")
        table.add_column("Attachments")

        for v in list(self.deque):
            table.add_row(v["title"], v["post_id"], str(len(v["attachments"])))

        table.print()
        print()

        file_num = 0
        file_size = 0
        print("Download started.")
        if dsize != 1:
            qbar = tqdm(range(dsize), "Queue", leave=False)
        for i in range(dsize):
            data = self.deque.popleft()
            # フォルダ名に使えない文字を置換、スペースを除去
            path = os.path.join(
                "./img",
                data["service"],
                f"[{data['creator_id']}] {data['creator_name'].translate(folder_name).strip()}",
                f"[{data['post_id']}] {data['title'].translate(folder_name).strip()}",
            )
            if global_var.args.flat:
                path = os.path.dirname(path)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            for attachment in tqdm(data["attachments"], "Attachments", leave=False):
                file = os.path.join(path, attachment["name"])
                if os.path.exists(file):
                    logger.debug("skip: " + file)
                    continue
                _type = attachment["type"]
                try:
                    self.api.download(attachment["url"], file)
                    # ファイル破損チェック
                    if _type == "image":
                        Image.open(file)
                    file_num = file_num + 1
                    file_size = file_size + os.path.getsize(file)
                    logger.debug("download: " + file)
                # ファイルが破損していた場合削除
                except (ProtocolError, UnidentifiedImageError, BadZipFile, ConnectionError):
                    os.remove(file)
                except FileNotFoundError:
                    logger.debug("notfound: " + file)
                except OSError as e:
                    logger.debug(type(e))
                    logger.debug(str(e))
                    # 空き容量が無い場合は終了
                    if str(e) == "[Errno 28] No space left on device":
                        Color.warn("No space left on device")
                        input()
                        exit()
            # time.sleep(1)
            if dsize != 1:
                qbar.update(1)
        if dsize != 1:
            qbar.close()

        table = Table()
        table.add_column("Files")
        table.add_column("Size")
        table.add_row(str(file_num), convert_size(file_size))
        table.print()

        Color.info("Download completed.")

    # 投稿の解析
    def parse(self, post: dict, bw=None, cover=False):
        title = post["title"]
        if bw is not None and bw.lower() in title.lower():
            return
        creator_id = post["user"]
        post_id = post["id"]
        attachments = list()
        page = 0
        if cover:
            url = os.path.join(f"https://img.{domain}/thumbnail/data/{post['file']['path']}")
            try:
                img = Image.open(io.BytesIO(self.api.get_content(url)))
            except UnidentifiedImageError as e:
                logger.debug(str(e))
                logger.debug(url)
            else:
                if (800, 420) != img.size:
                    ext = os.path.splitext(post["file"]["name"])[1]
                    url = f"{base_url}/data/{post['file']['path']}"
                    attachments.append({"name": f"{post_id}_p{page}{ext}", "url": url, "type": "image"})
                    page = page + 1
        for attachment in post["attachments"]:
            basename = attachment["name"]
            ext = os.path.splitext(basename)[1][1:]
            if ext in global_var.exts.keys():
                _type = global_var.exts[ext]
                if global_var.enable_filter and not global_var.args_dict[_type]:
                    continue
            else:
                _type = "unknown"
                continue
            # if _type == "image" and len(name) == 24:
            if _type == "image":
                basename = f"{post_id}_p{page}.{ext}"
                page = page + 1
            url = f"{base_url}/data/{attachment['path']}"
            attachments.append({"name": basename, "url": url, "type": _type})
        if len(attachments) == 0:
            return
        data = {
            "title": title,
            "creator_id": creator_id,
            "creator_name": self.creator_info(creator_id)["name"],
            "post_id": post_id,
            "service": post["service"],
            "attachments": attachments,
        }
        self.deque.append(data)

    # ユーザー一覧を更新、読込
    def creators(self, update: bool):
        if not os.path.exists("creators.json") or update:
            creators = {}
            for creator in self.api.creators():
                id = creator["id"]
                creators[id] = creator
            self._creators = creators
            with open("creators.json", "w", encoding="utf-8") as f:
                json.dump(self._creators, f, ensure_ascii=False, indent=4)
        else:
            self._creators = json.load(open("creators.json", "r", encoding="utf-8"))

    # ユーザー情報を取得
    def creator_info(self, creator_id: int | str) -> dict:
        try:
            creator = self._creators[creator_id]
        except KeyError:
            return dict()
        else:
            return creator

    # ユーザーを検索
    def search_creator(self, word: str, service: str | None):
        creators_data = []
        for creator in self._creators.values():
            name = creator["name"]
            _service = creator["service"]
            if service is None:
                pass
            elif service != _service:
                continue
            if word.lower() in name.lower():
                _id = creator["id"]
                creator_data = {
                    "name": name,
                    "id": _id,
                    "service": _service,
                    "url": (
                        f"{base_url}/{_service}/user/{_id}"
                        if _service != "discord"
                        else f"{base_url}/{_service}/server/{_id}"
                    ),
                }
                creators_data.append(creator_data)

        return creators_data

    def creator(self, service: str, creator_id: int | str):
        _creator = self.creator_info(creator_id)
        print(f"{_creator['name']}@{_creator['service']}[{_creator['id']}]")
        if _creator:
            offset = 0 if global_var.args.page is None else (global_var.args.page - 1) * 50
            word = None if global_var.args.word is None else global_var.args.word + " "
            tag = None if global_var.args.tag is None else global_var.args.tag
            while True:
                posts = self.api.creator(service, creator_id, offset=offset, word=word, tag=tag)
                for post in posts:
                    self.parse(post, bw=global_var.args.block_word, cover=global_var.args.cover)
                if len(posts) < 50:
                    break
                if global_var.args.page is not None:
                    break
                offset = offset + 50
        else:
            Color.warn("Not found.")

    def post(self, service: str, creator_id: int | str, post_id: int | str):
        _post = self.api.post(service, creator_id, post_id)
        if _post == {"error": "Not Found"}:
            Color.warn("Not found.")
            return
        self.parse(_post["post"], cover=global_var.args.cover)

    # チャンネル一覧を表示
    def discord_server(self, discord_server: int | str):
        channels = self.api.discord_server(discord_server)
        if channels:
            table = Table()
            table.add_column("Channel")
            table.add_column("ID")
            for channel in channels:
                table.add_row("#" + channel["name"], channel["id"])
            table.print()
        else:
            Color.warn("Not found.")

    def discord_channel(self, channel_id: int | str):
        pass
