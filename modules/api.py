import shutil

import requests  # type: ignore


class Api:
    def __init__(self):
        self.base_url = "https://kemono.su"
        self.headers = {"Accept": "application/json"}
        self.cookies = None

    def creators(self) -> dict:
        res = requests.get(f"{self.base_url}/api/v1/creators.txt", headers=self.headers)
        res.encoding = "utf-8"
        return res.json()

    def post(self, service: str, creator_id: int | str, post_id: int | str) -> dict:
        res = requests.get(
            f"{self.base_url}/api/v1/{service}/user/{creator_id}/post/{post_id}",
            headers=self.headers,
        )
        return res.json()

    def creator(
        self,
        service: str,
        creator_id: int | str,
        offset: int | None,
        word: str | None,
    ) -> list:
        res = requests.get(
            f"{self.base_url}/api/v1/{service}/user/{creator_id}",
            params={"o": offset, "q": word},
            headers=self.headers,
        )
        return res.json()

    def discord_server(self, discord_server: int | str) -> list:
        res = requests.get(
            f"{self.base_url}/api/v1/discord/channel/lookup/{discord_server}",
            headers=self.headers,
        )
        return res.json()

    def discord_channel(self, channel_id: int | str, offset: int | None = None) -> list:
        res = requests.get(
            f"{self.base_url}/api/v1/discord/channel/{channel_id}", params={"o": offset}
        )
        return res.json()

    def favorites(self, _type: str) -> list:
        res = requests.get(
            f"{self.base_url}/api/v1/account/favorites",
            params={"type": _type},
            headers=self.headers,
            cookies=self.cookies,
        )
        return res.json()

    def download(self, url, file):
        with requests.get(
            url,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
            },
        ) as response:
            with open(file, "wb") as f:
                shutil.copyfileobj(response.raw, f)
