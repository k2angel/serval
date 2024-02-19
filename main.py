import datetime
import json
import math
import os
import pickle
import re
import shutil
import time
import tomllib
import zipfile
from collections import deque
from zipfile import BadZipFile

import chardet
import requests
from discord_webhook import DiscordWebhook
from PIL import Image, UnidentifiedImageError
from plyer import notification as notice
from psd_tools import PSDImage
from pystyle import *
from requests.exceptions import ChunkedEncodingError, ConnectionError
from rich.console import Console
from tomli_w import dump
from tqdm import tqdm
from urllib3.exceptions import ProtocolError


class Api:
    def __init__(self):
        self.base_url = "https://kemono.su"
        self.headers = {"accept": "application/json"}
        self.cookies = None

    def creators(self) -> list:
        res = requests.get(f"{self.base_url}/api/v1/creators.txt", headers=self.headers)
        return res.json()

    def creator_info(self, creator_id: int | str) -> dict:
        try:
            creator = creators["creators"][creator_id]
        except KeyError:
            return dict()
        else:
            return creator

    def search_ceator(self, word: str) -> list:
        creators_data = []
        for creator in creators["creators"].values():
            name = creator["name"]
            if word.lower() in name.lower():
                id = creator["id"]
                service = creator["service"]
                creator_data = {
                    "name": name,
                    "id": id,
                    "service": service
                }
                creators_data.append(creator_data)
        return creators_data

    def user(self, service: str, creator_id: int | str, offset: int | None = None) -> list:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{creator_id}", params={"o": offset},
                           headers=self.headers)
        return res.json()

    def post(self, service: str, creator_id: int | str, post_id: int | str) -> dict:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{creator_id}/post/{post_id}", headers=self.headers)
        return res.json()

    def discord_server(self, discord_server: int | str) -> list:
        res = requests.get(f"{self.base_url}/api/v1/discord/channel/lookup/{discord_server}", headers=self.headers)
        return res.json()

    def discord_channel(self, channel_id: int | str, offset: int | None = None) -> list:
        res = requests.get(f"{self.base_url}/api/v1/discord/channel/{channel_id}", params={"o": offset})
        return res.json()

    def login(self, session: str):
        self.cookies = {"session": session}

    def favorites(self, type_: str) -> list:
        res = requests.get(f"{self.base_url}/api/v1/account/favorites", params={"type": type_},
                           headers=self.headers, cookies=self.cookies)
        return res.json()

    def add_favorite(self, type_: str, service: str, creator_id: int | str, post_id: int | str | None = None):
        if type_ == "creator":
            requests.post(f"{self.base_url}/api/v1/favorites/{type_}/{service}/{creator_id}",
                          headers=self.headers, cookies=self.cookies)
        elif type_ == "post":
            requests.post(f"{self.base_url}/api/v1/favorites/{type_}/{service}/{creator_id}/{post_id}",
                          headers=self.headers, cookies=self.cookies)

    def download(self, url, file):
        with requests.get(url, stream=True) as response:
            with open(file, "wb") as f:
                shutil.copyfileobj(response.raw, f)


class Client:
    def __init__(self):
        self.api = Api()
        self.deque = deque()
        self.logged = False
        if os.path.exists("./posts"):
            with open("./posts", "rb") as f:
                self.posts = pickle.load(f)
        else:
            self.posts = list()
            with open("./posts", "wb") as f:
                pickle.dump(self.posts, f)

    def download(self):
        def convert_size(size):
            units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB")
            i = math.floor(math.log(size, 1024)) if size > 0 else 0
            size = round(size / 1024 ** i, 2)

            return f"{size} {units[i]}"

        dsize = len(self.deque)
        if dsize:
            file_num = 0
            file_size = 0
            start = time.time()
            print_("[*] Download started.")
            notification("Download started.")
            if dsize != 1:
                qbar = tqdm(range(dsize), Center.XCenter("Queue", spaces=14), leave=False)
            for i in range(dsize):
                data = self.deque.popleft()
                path = os.path.join(settings["directory"], data["service"],
                                    f"{data['creator_name']}[{data['creator_id']}]",
                                    f"{data['title']}[{data['post_id']}]")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                for attachment in tqdm(data["attachments"], Center.XCenter("Attachments", spaces=14), leave=False):
                    url = attachment["url"]
                    name = str(attachment["name"] or os.path.basename(url))
                    file = os.path.join(path, name)
                    if os.path.exists(file):
                        continue
                    error_count = 0
                    while True:
                        try:
                            self.api.download(url, file)
                            if attachment["type"] == "archive" and settings["extract"]["enable"]:
                                self.extract(file)
                            elif attachment["type"] == "image":
                                Image.open(file)
                            elif attachment["type"] == "psd" and settings["psdConvert"]["enable"]:
                                psd = PSDImage.open(file)
                                psd.composite().save(f"{os.path.splitext(file)[0]}.{settings['psdConvert']['format']}")
                            file_num = file_num + 1
                            file_size = file_size + os.path.getsize(file)
                            break
                        except (ProtocolError, UnidentifiedImageError, BadZipFile, ChunkedEncodingError,
                                ConnectionError):
                            error_count = error_count + 1
                            if error_count > 10:
                                break
                            time.sleep(10)
                        except FileNotFoundError:
                            break
                        except OSError as e:
                            if str(e) == "[Errno 28] No space left on device":
                                with open("./queue", "wb") as f:
                                    pickle.dump(self.deque, f)
                            else:
                                print(type(e))
                                print(str(e))
                            os.remove(file)
                            input()
                            exit()
                        except Exception as e:
                            print(type(e))
                            print(str(e))
                            os.remove(file)
                            input()
                            exit()
                # time.sleep(1)
                if "qbar" in locals():
                    qbar.update(1)
                self.posts.append(f"{data['post_id']}@{data['service']}[{data['creator_id']}]")
                with open("posts", "wb") as f:
                    pickle.dump(self.posts, f)
            if "qbar" in locals():
                qbar.close()
            elapsed = time.time() - start
            info = f"TIME: {datetime.timedelta(seconds=elapsed)}\nFILES: {file_num}\nSIZE: {convert_size(file_size)}"
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(Box.DoubleCube(info)), 1))
            print_("[*] Download finished.")
            notification(f"Download finished.\n{info}")
        else:
            print_("[!] There is nothing in the queue.")

    def extract(self, archive: str):
        extract_dir = os.path.splitext(archive)[0]
        extract_dir_name = os.path.basename(extract_dir) + "/"
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for info in tqdm(z.infolist(), Center.XCenter("Extract", spaces=18), leave=False):
                try:
                    info.filename = info.orig_filename.encode('cp437').decode('cp932')
                except UnicodeDecodeError:
                    result = chardet.detect(info.orig_filename.encode("cp437"))
                    info.filename = info.orig_filename.encode("cp437").decode(result["encoding"])
                if os.sep != "/" and os.sep in info.filename:
                    info.filename = info.filename.replace(os.sep, "/")
                if extract_dir_name == info.filename[0:(len(extract_dir_name))]:
                    info.filename = info.filename[(len(extract_dir_name)):]
                if info.filename == "":
                    continue
                try:
                    z.extract(info, extract_dir)
                except RuntimeError:
                    pass
        if settings["extract"]["deletezip"]:
            os.remove(archive)

    def parse(self, post: dict):
        title = post["title"].translate(
            str.maketrans(
                {"　": " ", '\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”', '<': '＜', '>': '＞', '|': '｜'}))
        creator_id = post["user"]
        creator_name = self.api.creator_info(creator_id)["name"].translate(
            str.maketrans(
                {"　": " ", '\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”', '<': '＜', '>': '＞', '|': '｜'}))
        post_id = post["id"]
        service = post["service"]
        if f"{post_id}@{service}[{creator_id}]" in self.posts or not post["attachments"]:
            return
        attachments = list()
        page = 0
        for attachment in post["attachments"]:
            name = attachment["name"]
            ext = os.path.splitext(name)[1]
            if re.match(r"\w{8}-\w{4}-\w{4}-\w{4}-\w{12}", name) is not None or re.match(r"\w{24}", name):
                name = f"{post_id}_p{page}{ext}"
                page = page + 1
                type = "image"
            elif re.match(r"https?://[\w/:%#$&?()~.=+\-]+", name) is not None:
                name = os.path.basename(attachment["path"])
                type = "unknonw"
            else:
                if ext == ".jpg" or ext == ".jpeg" or ext == ".png" or ext == "gif":
                    type = "image"
                elif ext == ".psd":
                    type = "psd"
                elif ext == ".zip":
                    type = "archive"
                elif ext == ".mp4" or ext == ".mov":
                    type = "movie"
                else:
                    type = "unknown"
            url = f"{self.api.base_url}/data/{attachment['path']}"
            attachments.append({"name": name, "url": url, "type": type})
        data = {
            "title": title,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "post_id": post_id,
            "service": service,
            "attachments": attachments
        }
        self.deque.append(data)

    def creators(self, update: bool) -> dict:
        content_length = requests.head(f"{self.api.base_url}/api/v1/creators.txt").headers["content-length"]
        if not os.path.exists("./creators.json"):
            print_("[!] Not found creators.json")
            print_("[*] Download started...")
            creators = self.api.creators()
            creators_data = {}
            for creator in creators:
                id = creator["id"]
                creators_data[id] = creator
            creators_ = {
                "creators": creators_data,
                "content-length": content_length
            }
            with open("creators.json", "w", encoding="utf-8") as f:
                json.dump(creators_, f, ensure_ascii=False)
            print_("[*] Creator list has been downloaded.")
        elif update:
            print_("[*] Checking creators list update...")
            with open("creators.json", "r", encoding="utf-8") as f:
                creators_ = json.load(f)
                if creators_["content-length"] != content_length:
                    print_("[!] Creators list has been updated.")
                    print_(f"{creators_['content-length']} -> {content_length}")
                    print_("[*] Download started...")
                    creators = self.api.creators()
                    creators_data = {}
                    for creator in creators:
                        id = creator["id"]
                        creators_data[id] = creator
                    creators_ = {
                        "creators": creators_data,
                        "content-length": content_length
                    }
                    with open("creators.json", "w", encoding="utf-8") as f:
                        json.dump(creators_, f)
                    print_("[*] Creator list has been downloaded.")
                else:
                    print_("[*] Creator list has not been updated.")
        else:
            with open("creators.json", "r", encoding="utf-8") as f:
                creators_ = json.load(f)
        return creators_

    def search_creator(self, word: str):
        creators = self.api.search_ceator(word)
        if not creators:
            print_(f"[!] Not found {word} in creators list.")
            return
        digits = len(str(len(creators)))
        for creator, i in zip(creators, range(len(creators))):
            print_(f"[{str(i + 1).zfill(digits)}] {creator['name']}@{creator['service']}[{creator['id']}]")
        while True:
            select = input_("[SELECT] > ")
            try:
                select = int(select)
                if select == 0:
                    break
                else:
                    i = select - 1
                    creator = creators[i]
                    with console.status("[bold green]Fetching data..."):
                        self.user(creator["service"], creator["id"])
                    print_("[*] Fetch done.")
                    client.download()
            except (ValueError, IndexError):
                print_("[!] ERROR.")
                input_("[*] Press ENTER to go back.")
            else:
                break

    def user(self, service: str, creator_id: int | str):
        creator = self.api.creator_info(creator_id)
        if creator:
            offset = 0
            post_num = 0
            while True:
                posts = self.api.user(service, creator_id, offset=offset)
                for post in posts:
                    self.parse(post)
                    post_num = post_num + 1
                if len(posts) < 50:
                    break
                offset = offset + 50
            info = f"NAME: {creator['name']}\nPOSTS: {post_num}\nSERVICE: {creator['service']}"
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(Box.DoubleCube(info)), speed=1))
            notification(info)
        else:
            print_("[!] Not found.")

    def post(self, service: str, creator_id: int | str, post_id: int | str):
        post = self.api.post(service, creator_id, post_id)
        if post == {"error": "Not Found"}:
            print_("[!] Not found.")
            return
        self.parse(post)
        creator = self.api.creator_info(post["user"])
        info = f"NAME: {creator['name']}\nTITLE: {post['title']}\nSERVICE: {creator['service']}"
        print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(Box.DoubleCube(info)), speed=1))

    def discord_server(self, discord_server: int | str):
        channels = self.api.discord_server(discord_server)
        if channels:
            digits = len(str(len(channels)))
            for channel, i in zip(channels, range(len(channels))):
                print_(f"[{str(i + 1).zfill(digits)}] {channel['name']}@discord[{channel['id']}]")
        else:
            print_("[!] Not found.")

    def discord_channel(self, channel_id: int | str):
        pass

    def login(self):
        global settings

        def get_session() -> str:
            username = input_("[USERNAME] > ")
            password = input_("[PASSWORD] > ")
            session = requests.session()
            res = session.post(f"{self.api.base_url}/account/login", data={"username": username, "password": password})
            if res.url == f"{self.api.base_url}/account/login":
                print_("[!] Login failed...")
            else:
                print_("[*] Login successfully!")
                for cookie in session.cookies:
                    if cookie.name == "session":
                        session_key = cookie.value
                        session_expires = cookie.expires
                        settings["account"]["uname"] = username
                        settings["account"]["passwd"] = password
                        settings["account"]["cookie"]["session"] = session_key
                        settings["account"]["cookie"]["expires"] = session_expires
                        with open("./settings.toml", "wb") as f:
                            dump(settings, f)
                        return session_key

        if settings["account"]["cookie"]["session"]:
            cookie = settings["account"]["cookie"]
            if int(time.time()) > cookie["account"]["expires"]:
                session_key = get_session()
                self.api.login(session_key)
            else:
                self.api.login(cookie["account"]["session"])
                print_("[*] Login successfully!")
        else:
            session_key = get_session()
            self.api.login(session_key)
        self.logged = True

    def favorites(self):
        creators = self.api.favorites("artist")
        if not creators:
            print_(f"[!] Not found.")
            return
        # ?sort=faved_seq&order=desc
        creators = sorted(creators, key=lambda faved_seq: faved_seq["faved_seq"], reverse=True)
        digits = len(str(len(creators)))
        for creator, i in zip(creators, range(len(creators))):
            print_(f"[{str(i + 1).zfill(digits)}] {creator['name']}@{creator['service']}[{creator['id']}]")
        while True:
            select = input_("[SELECT] > ")
            try:
                select = int(select)
                if select == 0:
                    break
                else:
                    i = select - 1
                    creator = creators[i]
                    with console.status("[bold green]Fetching data..."):
                        self.user(creator["service"], creator["id"])
                    print_("[*] Fetch done.")
                    client.download()
            except (ValueError, IndexError):
                print_("[!] ERROR.")
                input_("[*] Press ENTER to go back.")


def print_(text: str):
    print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(text, spaces=28), 1))


def input_(text: str):
    return Write.Input(Center.XCenter(text, spaces=28), Colors.yellow_to_red,
                       interval=0, hide_cursor=True)


def notification(message: str):
    def desktop(message: str):
        notice.notify(title="Notification", message=message, app_name="Tumbl-Ripper", app_icon="./icon.ico")

    def discord(message: str):
        if settings["notification"]["discord"]["webhookUrl"] != "":
            if settings["notification"]["discord"]["mention"]["enable"]:
                if settings["notification"]["discord"]["mention"]["discordId"] != "":
                    message = f"<@{settings['notification']['discord']['mention']['discordId']}>\n{message}"
            DiscordWebhook(url=settings["notification"]["discord"]["webhookUrl"], content=message).execute()

    if settings["notification"]["enable"]:
        if settings["notification"]["desktop"]["enable"]:
            desktop(message)
        if settings["notification"]["discord"]["enable"]:
            discord(message)


def settings():
    with open("settings.toml", "rb") as f:
        settings = tomllib.load(f)
    return settings


banner = r"""
  ________  _______   _______  ___      ___  __      ___       
 /"       )/"     "| /"      \|"  \    /"  |/""\    |"  |      
(:   \___/(: ______)|:        |\   \  //  //    \   ||  |      
 \___  \   \/    |  |_____/   ) \\  \/. .//' /\  \  |:  |      
  __/  \\  // ___)_  //      /   \.    ////  __'  \  \  |___   
 /" \   :)(:      "||:  __   \    \\   //   /  \\  \( \_|:  \  
(_______/  \_______)|__|  \___)    \__/(___/    \___)\_______) 
                                                               
"""
menu = "[D] Download   [S] Search   [U] Update   [L] Login   [F] Favorite"
version = 1.2
System.Title(f"serval v{version}")

os.chdir(os.path.dirname(os.path.abspath(__file__)))
settings = settings()

client = Client()
creators = client.creators(update=False)

console = Console()

if __name__ == "__main__":
    while True:
        System.Clear()
        print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
        print_(menu)
        mode = input_("[SERVAL] > ")
        if mode == "d":
            System.Clear()
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
            url = input_("[URL] > ")
            if m := re.match(r"https://kemono\.su/(\w+)/user/(\d+)", url):
                with console.status("[bold green]Fetching data...") as status:
                    if m_ := re.match(r"https://kemono\.su/(\w+)/user/(\d+)/post/(\w+)", url):
                        client.post(m_.group(1), m_.group(2), m_.group(3))
                    else:
                        client.user(m.group(1), m.group(2))
                print_("[*] Fetch done.")
                try:
                    client.download()
                except Exception as e:
                    print(type(e))
                    print_(str(e))
            elif m := re.match(r"https://kemono.su/discord/server/(\d+)", url):
                with console.status("[bold green]Fetching data...") as status:
                    if m_ := re.match(r"https://kemono.su/discord/server/(\d+)#(\d+)", url):
                        client.discord_channel(m.group(2))
                    else:
                        client.discord_server(m.group(1))
                print_("[*] Fetch done.")
            else:
                print_("[!] ERROR.")
        elif mode == "s":
            System.Clear()
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
            word = input_("[SEARCH] > ")
            if word == "":
                print_("[!] ERROR.")
            else:
                client.search_creator(word)
        elif mode == "u":
            client.creators(update=True)
        elif mode == "l":
            client.login()
        elif mode == "f":
            if not client.logged:
                print_("[!] Not logging in.")
            else:
                System.Clear()
                print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
                # type_ = input_("[?] Artist OR Post > ").lower()
                client.favorites()
        else:
            print_("[!] ERROR.")
        input_("[*] Press ENTER to go back.")
