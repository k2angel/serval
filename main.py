import json
import os
import pickle
import pprint
import queue
import re
import shutil
import threading
import time
import warnings
import webbrowser
import zipfile

import chardet
import requests
from PIL import Image, UnidentifiedImageError
from plyer import notification
from pystyle import *
from rich.console import Console
from tqdm import TqdmExperimentalWarning, tqdm
#from tqdm.rich import tqdm
from urllib3.exceptions import ProtocolError


class Api:
    def __init__(self):
        self.base_url = "https://kemono.su"
        self.headers = {"accept": "application/json"}
        self.cookies = None

    def creators(self) -> list:
        res = requests.get(f"{self.base_url}/api/v1/creators.txt", headers=self.headers)
        return res.json()

    def creator_info(self, user_id: int | str) -> dict:
        return creators["creators"][user_id]

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

    def user(self, service: str, user_id: int | str, offset: int | None = None) -> list:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{user_id}", params={"o": offset},
                           headers=self.headers)
        return res.json()

    def post(self, service: str, user_id: int | str, post_id: int | str) -> dict:
        res = requests.get(f"{self.base_url}/api/v1/{service}/user/{user_id}/post/{post_id}", headers=self.headers)
        return res.json()

    def login(self, session: str):
        self.cookies = {"session": session}

    def favorites(self, type_: str) -> list:
        res = requests.get(f"{self.base_url}/api/v1/account/favorites", params={"type": type_},
                           headers=self.headers, cookies=self.cookies)
        return res.json()

class Client:
    def __init__(self):
        self.api = Api()
        self.queue = queue.Queue()
        self.logged = False

    def download(self):
        global posts
        if not self.queue.empty():
            print_("[*] Download started.")
            qsize = self.queue.qsize()
            if qsize != 1:
                qbar = tqdm(range(qsize), Center.XCenter("Queue", spaces=14))
            for i in range(qsize):
                data = self.queue.get()
                path = os.path.join("./img/", data["service"], f"{data['user_name']}[{data['user_id']}]",
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
                            with open(file, "wb") as f:
                                dlbar = tqdm(desc=Center.XCenter("Download", spaces=14), total=attachment["content-length"], unit="B", unit_scale=True, leave=False)
                                for chunk in requests.get(url, stream=True).iter_content(chunk_size=1024):
                                    f.write(chunk)
                                    dlbar.update(len(chunk))
                                dlbar.close()
                            if attachment["type"] == "archive":
                                self.unpack(file)
                            elif attachment["type"] == "image":
                                Image.open(file)
                        except (ProtocolError, UnidentifiedImageError, zipfile.BadZipFile):
                            dlbar.close()
                            error_count = error_count+1
                            if error_count > 10:
                                break
                            time.sleep(10)
                        except Exception as e:
                            dlbar.close()
                            print(type(e))
                            print(str(e))
                            input()
                            exit()
                        else:
                            break
                #time.sleep(1)
                if "qbar" in locals():
                    qbar.update()
                posts.append(f"{data['post_id']}@{data['service']}[{data['user_id']}]")
                with open("posts", "wb") as f:
                    pickle.dump(posts, f)
            print_("[*] Download finished.")
            notification.notify(title="Notice", message="Download finished.", app_name="serval",
                                app_icon="./icon.ico")

        else:
            print_("[!] There is nothing in the queue.")

    def unpack(self, archive: str):
        extract_dir = os.path.splitext(archive)[0]
        extract_dir_name = os.path.basename(extract_dir) + "/"
        os.makedirs(extract_dir, exist_ok=True)
        password = False
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
                    password = True
        if not password:
            os.remove(archive)

    def parse(self, post: dict):
        title = post["title"].translate(
            str.maketrans({'\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”', '<': '＜', '>': '＞', '|': '｜'}))
        user_id = post["user"]
        user_name = self.api.creator_info(user_id)["name"].translate(
            str.maketrans({'\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”', '<': '＜', '>': '＞', '|': '｜'}))
        post_id = post["id"]
        service = post["service"]
        if f"{post_id}@{service}[{user_id}]" in posts or not post["attachments"]:
            return
        attachments = list()
        page = 0
        for attachment in post["attachments"]:
            name = attachment["name"]
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

            url = requests.head(f"{self.api.base_url}/data/{attachment['path']}").headers["Location"]
            content_length = int(requests.head(url).headers["content-length"])
            attachments.append({"name": name, "url": url, "content-length": content_length, "type": type})
        data = {
            "title": title,
            "user_id": user_id,
            "user_name": user_name,
            "post_id": post_id,
            "service": service,
            "attachments": attachments
        }
        self.queue.put(data)

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
            print_(f"[{str(i+1).zfill(digits)}] {creator['name']}@{creator['service']}[{creator['id']}]")
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


    def user(self, service: str, user_id: int | str):
        offset = 0
        while True:
            posts = self.api.user(service, user_id, offset=offset)
            if not posts:
                break
            for post in posts:
                self.parse(post)
            offset = offset + 50
        creator = self.api.creator_info(user_id)
        info = f"NAME: {creator['name']}\nPOSTS: {self.queue.qsize()}\nSERVICE: {creator['service']}"
        print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(Box.DoubleCube(info)), speed=1))

    def post(self, service: str, user_id: int | str, post_id: int | str):
        post = self.api.post(service, user_id, post_id)
        self.parse(post)
        creator = self.api.creator_info(post["user"])
        info = f"NAME: {creator['name']}\nTITLE: {post['title']}\nSERVICE: {creator['service']}"
        print(Colorate.Horizontal(Colors.yellow_to_red, Center.XCenter(info), speed=1))

    def login(self):
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
                        cookie = {
                        "session": session_key,
                        "expires": session_expires
                        }
                        with open("./cookie", "wb") as f:
                            pickle.dump(cookie, f)
                        return session_key

        if os.path.exists("./cookie"):
            with open("./cookie", "rb") as f:
                cookie = pickle.load(f)
            if int(time.time()) > cookie["expires"]:
                session_key = get_session()
                self.api.login(session_key)
            else:
                self.api.login(cookie["session"])
                print_("[*] Login successfully!")
        else:
            session_key = get_session()
            self.api.login(session_key)
        self.logged = True

    def favorites(self, type_: str):
        if type_ == "artist":
            creators = self.api.favorites(type_)
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
        elif type_ == "post":
            with console.status("[bold green]Fetching data..."):
                posts = self.api.favorites(type_)
                if not posts:
                    print_("[!] Not found.")
                    return
                for post in posts:
                    self.parse(post)
            print_("[*] Fetch done.")
            self.download()
        else:
            print_("[!] ERROR.")
            return


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

menu = "[D] Download   [S] Search   [U] Update   [L] Login   [F] Favorite"

version = 1.2

System.Title(f"serval v{version}")

System.Clear()
print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
creators = client.creators(update=False)
with open("posts", "rb") as f:
    posts = pickle.load(f)
#input_("")

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
            else:
                m_ = re.match(
                    r"https://kemono\.su/(\w+)/user/(\d+)/post/(\w+)", url)
                with console.status("[bold green]Fetching data...") as status:
                    if m_ is None:
                        client.user(m.group(1), m.group(2))
                    else:
                        client.post(m_.group(1), m_.group(2), m_.group(3))
                print_("[*] Fetch done.")
                client.download()
        elif mode == "s":
            System.Clear()
            print(Colorate.Horizontal(Colors.yellow_to_red, Center.Center(banner, yspaces=2), 1))
            word = input_("[SEARCH] > ")
            client.search_creator(word)
        elif mode == "u":
            client.creators(update=True)
        elif mode == "l":
            client.login()
        elif mode == "f":
            if not client.logged:
                print_("[!] Not logging in.")
                continue
            else:
                type_ = input_("[?] Artist OR Post > ").lower()
                client.favorites(type_)
        else:
            print_("[!] ERROR.")
        input_("[*] Press ENTER to go back.")

