import shutil

import requests
import requests.adapters

from .global_var import base_url, user_agent

headers = {"Accept": "application/json"}
error_messages = {"503": "API is in maintenance or not available."}


def error_hooks(r: requests.Response, *args, **kwargs):
    if r.status_code == 503:
        APIError("API is in maintenance or not available.")


class APIError(Exception):
    pass


class Api:
    def __init__(self):
        self.cookies = None

    def creators(self) -> dict:
        res = requests.get(f"{base_url}/api/v1/creators.txt", headers=headers, hooks={"response": error_hooks})
        res.encoding = "utf-8"
        return res.json()

    def post(self, service: str, creator_id: int | str, post_id: int | str) -> dict:
        res = requests.get(
            f"{base_url}/api/v1/{service}/user/{creator_id}/post/{post_id}",
            headers=headers,
            hooks={"response": error_hooks},
        )
        return res.json()

    def creator(
        self, service: str, creator_id: int | str, offset: int | None, word: str | None, tag: str | None
    ) -> list:
        res = requests.get(
            f"{base_url}/api/v1/{service}/user/{creator_id}/posts",
            params={"o": offset, "q": word, "tag": tag},
            headers=headers,
            hooks={"response": error_hooks},
        )
        return res.json()

    def discord_server(self, discord_server: int | str) -> list:
        res = requests.get(
            f"{base_url}/api/v1/discord/channel/lookup/{discord_server}",
            headers=headers,
            hooks={"response": error_hooks},
        )
        return res.json()

    def discord_channel(self, channel_id: int | str, offset: int | None = None) -> list:
        res = requests.get(f"{base_url}/api/v1/discord/channel/{channel_id}", params={"o": offset})
        return res.json()

    def favorites(self, _type: str) -> list:
        res = requests.get(
            f"{base_url}/api/v1/account/favorites",
            params={"type": _type},
            headers=headers,
            cookies=self.cookies,
            hooks={"response": error_hooks},
        )
        return res.json()

    def download(self, url, file):
        retry = requests.adapters.Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session = requests.Session()
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
        with session.get(
            url,
            stream=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "*/*",
            },
        ) as response:
            with open(file, "wb") as f:
                shutil.copyfileobj(response.raw, f)

    def get_content(self, url):
        res = requests.get(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "*/*",
            },
        )
        return res.content
