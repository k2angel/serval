import json
import os
import pprint
import queue
import re
import shutil
import threading
import time
import warnings
import webbrowser
import zipfile

import requests
from PIL import Image, UnidentifiedImageError
from plyer import notification
from pystyle import *
from rich.console import Console
from tqdm import TqdmExperimentalWarning, tqdm
from tqdm.rich import tqdm


class Api:
    def __init__(self):
        self.base_url = "https://kemono.su"
        self.headers = {"accept": "application/json"}

    def creators(self) -> list:
        res = requests.get(f"{self.base_url}/api/v1/creators.txt")
        return res.json()

    def search_ceator(self, word: str) -> list:
        creators_data = []
        for creator in creators["creators"].values():
            name = creator["name"]
            if word in name:
                id = creator["id"]
                service = creator["service"]
                creator_data = {
                    "name": name,
                    "id": id,
                    "service": service
                }
                creators_data.append(creator_data)
        return creators_data

    def user(self, service: str, user_id: int | str, offset: int | None = None) -> list:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{user_id}", params={"o": offset})
        return res.json()

    def post(self, service: str, user_id: int | str, post_id: int | str) -> dict:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{user_id}/post/{post_id}")
        return res.json()


class Client:
    def __init__(self):
        self.api = Api()
        self.queue = queue.Queue()

    def download(self):
        if not self.queue.empty():
            for i in tqdm(range(self.queue.qsize()), "Queue", leave=True):
                data = self.queue.get()
                path = os.path.join("./img/", data["service"], data["user_id"], f"{data['title']}[{data['post_id']}]")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                for attachment in data["attachments"]:
                    url = f"{self.api.base_url}/data/{attachment['path']}"
                    name = str(attachment["name"] or os.path.basename(url))
                    file = os.path.join(path, name)
                    if os.path.exists(file):
                        continue
                    while True:
                        try:
                            with requests.get(url, stream=True) as res:
                                with open(file, "wb") as f:
                                    shutil.copyfileobj(res.raw, f)
                            if attachment["type"] == "archive":
                                self.unpack(file)
                            elif attachment["type"] == "image":
                                Image.open(file)
                        except UnidentifiedImageError:
                            time.sleep(10)
                        except Exception as e:
                            print(type(e))
                            input()
                            exit()
                        else:
                            time.sleep(1)
                            break

    def unpack(self, archive: str):
        extract_dir = os.path.splitext(archive)[0]
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                info.filename = info.orig_filename.encode('cp437').decode('cp932')
                if os.sep != "/" and os.sep in info.filename:
                    info.filename = info.filename.replace(os.sep, "/")
                z.extract(info, extract_dir)

    def parse(self, post: dict):
        title = post["title"].translate(
            str.maketrans({'\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”', '<': '＜', '>': '＞', '|': '｜'}))
        user_id = post["user"]
        post_id = post["id"]
        service = post["service"]
        attachments = list()
        page = 0
        for attachment in post["attachments"]:
            name = attachment["name"]
            path = attachment["path"]
            ext = os.path.splitext(name)[1]
            if re.match(r"\w{8}-\w{4}-\w{4}-\w{4}-\w{12}", name) is not None:
                name = f"{post_id}_p{page}{ext}"
                page = page + 1
                type = "image"
            else:
                if ext == ".jpg" or ext == ".jpeg" or ext == ".png" or ext == "gif":
                    type = "image"
                elif ext == ".zip" or ext == ".rar":
                    type = "archive"
                elif ext == ".mp4" or ext == ".mov":
                    type = "movie"
                else:
                    type = "unknown"
            attachments.append({"name": name, "path": path, "type": type})
        data = {
            "title": title,
            "user_id": user_id,
            "post_id": post_id,
            "service": service,
            "attachments": attachments
        }
        self.queue.put(data)

    def creators(self) -> dict:
        print_("[*] Checking creators list update...")
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
        else:
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
        return creators_

    def search_creator(self, word: str):
        creators = self.api.search_ceator(word)
        digits = len(str(len(creators)))
        for creator, i in zip(creators, range(len(creators))):
            print_(f"[{str(i+1).zfill(digits)}] {creator['name']}@{creator['service']}[{creator['id']}]")

    def user(self, service: str, user_id: int | str):
        offset = 0
        while True:
            posts = self.api.user(service, user_id, offset=offset)
            if not posts:
                break
            for post in posts:
                self.parse(post)
            offset = offset + 50

    def post(self, service: str, user_id: int | str, post_id: int | str):
        post = self.api.post(service, user_id, post_id)
        self.parse(post)


def print_(text: str):
    print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(text, spaces=28), 1))


def input_(text: str):
    return Write.Input(Center.XCenter(text, spaces=28), Colors.yellow_to_red,
                       interval=0, hide_cursor=True)


os.chdir(os.path.dirname(os.path.abspath(__file__)))
warnings.simplefilter("ignore", category=TqdmExperimentalWarning)

client = Client()
console = Console()

banner = r"""
  ________  _______   _______  ___      ___  __      ___       
 /"       )/"     "| /"      \|"  \    /"  |/""\    |"  |      
(:   \___/(: ______)|:        |\   \  //  //    \   ||  |      
 \___  \   \/    |  |_____/   ) \\  \/. .//' /\  \  |:  |      
  __/  \\  // ___)_  //      /   \.    ////  __'  \  \  |___   
 /" \   :)(:      "||:  __   \    \\   //   /  \\  \( \_|:  \  
(_______/  \_______)|__|  \___)    \__/(___/    \___)\_______) 
                                                               
"""

menu = "[D] Download    [S] Search    [U] Update    [G] GitHub"

version = 1.0

System.Title(f"serval v{version}")

System.Clear()
print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
#creators = client.creators()
with open("creators.json", "r", encoding="utf-8") as f:
    creators = json.load(f)
input_("")

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
            m = re.match(r"https://kemono\.su/(\w+)/user/(\d+)", url)
            if m is None:
                print_("[!] ERROR.")
                input_("[*] Press ENTER to go back.")
                continue
            else:
                m_ = re.match(
                    r"https://kemono\.su/(\w+)/user/(\d+)/post/(\w+)", url)
                with console.status("[bold green]Fetching data...") as status:
                    if m_ is None:
                        client.user(m.group(1), m.group(2))
                    else:
                        client.post(m_.group(1), m_.group(2), m_.group(3))
                print_("[*] Fetch done.")

                # download
                print_("[*] Download started.")
                client.download()
                print_("[*] Download finished.")
                input_("[*] Press ENTER to go back.")
                notification.notify(title="Notice", message="Download finished.", app_name="serval",
                                    app_icon="./icon.ico")
        elif mode == "s":
            System.Clear()
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
            word = input_("[SEARCH] > ")
            client.search_creator(word)
            input_("[*] Press ENTER to go back.")
        elif mode == "u":
            client.creators()
            input_("[*] Press ENTER to go back.")
        elif mode == "g":
            webbrowser.open("https://github.com/k2angel/serval")
        else:
            print_("[!] ERROR.")
            input_("[*] Press ENTER to go back.")

