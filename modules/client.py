from argparse import Namespace
import json
import math
import os
import time
from collections import deque
from xmlrpc.client import ProtocolError
from zipfile import BadZipFile

from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from .api import Api
from .common import Color, Table, logger


class Client:
    def __init__(self):
        self.api = Api()
        self.deque = deque()
        self.logged = False

        self.creators(False)

    def download(self, args: Namespace):
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
            path = os.path.join(
                "./img",
                data["service"],
                f"[{data['creator_id']}] {data['creator_name'].translate(folder_name)}",
                f"[{data['post_id']}] {data['title'].translate(folder_name)}",
            )
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            for attachment in tqdm(
                data["attachments"],
                "Attachments",
                leave=False,
            ):
                url = attachment["url"]
                name = str(attachment["name"] or os.path.basename(url))
                file = os.path.join(path, name)
                if os.path.exists(file):
                    continue
                error_count = 0
                _type = attachment["type"]
                while True:
                    try:
                        if (
                            not args.image
                            and not args.archive
                            and not args.movie
                            and not args.psd
                            and not args.pdf
                        ):
                            pass
                        elif _type == "image" and not args.image:
                            break
                        elif _type == "archive" and not args.archive:
                            break
                        elif _type == "movie" and not args.movie:
                            break
                        elif _type == "psd" and not args.psd:
                            break
                        elif _type == "pdf" and not args.pdf:
                            break
                        self.api.download(url, file)
                        if _type == "image":
                            # ファイル破損チェック
                            Image.open(file)
                        file_num = file_num + 1
                        file_size = file_size + os.path.getsize(file)
                        break
                    except (
                        ProtocolError,
                        UnidentifiedImageError,
                        BadZipFile,
                        ConnectionError,
                    ):
                        error_count = error_count + 1
                        if error_count > 10:
                            break
                        time.sleep(10)
                    except FileNotFoundError:
                        break
                    except OSError as e:
                        os.remove(file)
                        if str(e) == "[Errno 28] No space left on device":
                            Color.warn("No space left on device")
                            input()
                            exit()
                        else:
                            logger.debug(type(e))
                            logger.debug(str(e))
                    except Exception as e:
                        logger.debug(type(e))
                        logger.debug(str(e))
            # time.sleep(1)
            if "qbar" in locals():
                qbar.update(1)
        if "qbar" in locals():
            qbar.close()

        table = Table()
        table.add_column("Files")
        table.add_column("Size")
        table.add_row(str(file_num), convert_size(file_size))
        table.print()

        Color.info("Download completed.")

    def parse(self, post: dict, bw=None):
        title = post["title"]
        if bw is not None and bw in title:
            return
        creator_id = post["user"]
        creator_name = self.creator_info(creator_id)["name"]
        post_id = post["id"]
        service = post["service"]
        if not post["attachments"]:
            return
        attachments = list()
        page = 0
        for attachment in post["attachments"]:
            basename = attachment["name"]
            name, ext = os.path.splitext(basename)
            if ext in [".jpg", ".jpeg", ".png", ".gif"]:
                    _type = "image"
            elif ext == ".psd":
                _type = "psd"
            elif ext == ".zip":
                _type = "archive"
            elif ext in [".mp4", ".mov", ".mkv"]:
                _type = "movie"
            else:
                _type = "unknown"
            # if _type == "image" and len(name) == 24:
            if _type == "image":
                basename = f"{post_id}_p{page}{ext}"
                page = page + 1
            url = f"{self.api.base_url}/data/{attachment['path']}"
            attachments.append({"name": basename, "url": url, "type": _type})
        data = {
            "title": title,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "post_id": post_id,
            "service": service,
            "attachments": attachments,
        }
        self.deque.append(data)

    def creators(self, update: bool):
        if not os.path.exists("creators.json") or update:
            creators = self.api.creators()
            creators_ = {}
            for creator in creators:
                id = creator["id"]
                creators_[id] = creator
            self._creators = creators_
            with open("creators.json", "w", encoding="utf-8") as f:
                json.dump(self._creators, f, ensure_ascii=False, indent=4)
        else:
            self._creators = json.load(open("creators.json", "r", encoding="utf-8"))

    def creator_info(self, creator_id: int | str) -> dict:
        try:
            creator = self._creators[creator_id]
        except KeyError:
            return dict()
        else:
            return creator

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
                        f"https://kemono.su/{_service}/user/{_id}"
                        if _service != "discord"
                        else f"https://kemono.su/{_service}/server/{_id}"
                    ),
                }
                creators_data.append(creator_data)

        return creators_data

    def creator(self, service: str, creator_id: int | str, args: Namespace):
        _creator = self.creator_info(creator_id)
        print(f"{_creator['name']}@{_creator['service']}[{_creator['id']}]")
        if _creator:
            offset = 0 if args.page is None else (args.page - 1) * 50
            word = None if args.word is None else args.word+" "
            while True:
                posts = self.api.creator(service, creator_id, offset=offset, word=word)
                for post in posts:
                    self.parse(post, bw=args.block_word)
                if len(posts) < 50:
                    break
                if args.page is not None:
                    break
                offset = offset + 50
        else:
            Color.warn("Not found.")

    def post(self, service: str, creator_id: int | str, post_id: int | str):
        _post = self.api.post(service, creator_id, post_id)
        if _post == {"error": "Not Found"}:
            Color.warn("Not found.")
            return
        self.parse(_post["post"])

    def discord_server(self, discord_server: int | str):
        channels = self.api.discord_server(discord_server)
        if channels:
            table = Table()
            table.add_column("Channel")
            table.add_column("ID")
            for channel in channels:
                table.add_row("#"+channel["name"], channel["id"])
            table.print()
        else:
            Color.warn("Not found.")

    def discord_channel(self, channel_id: int | str):
        pass
