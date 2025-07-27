from argparse import Namespace


sld = "kemono"
tld = ["party", "su", "cr"]
domain = f"{sld}.{tld[-1]}"
base_url = "https://" + domain

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"

args = Namespace()
args_dict = {}
enable_filter = False

types = {
    "image": {"short": "i", "help": "画像", "ext": ["jpg", "jpeg", "jpe", "png", "gif"]},
    "archive": {"short": "a", "help": "書庫", "ext": ["zip", "rar", "7z", "zipmod"]},
    "movie": {"short": "m", "help": "動画", "ext": ["mp4", "mov", "mkv"]},
    "sound": {"short": "s", "help": "音声", "ext": ["mp3", "m4a", "ogg", "flac", "wav"]},
    "psd": {"short": None, "help": "psd", "ext": ["psd"]},
    "pdf": {"short": None, "help": "pdf", "ext": ["pdf"]},
}
exts = {}
for k, v in types.items():
    for _ext in v["ext"]:
        exts[_ext] = k
