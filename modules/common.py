import unicodedata
from logging import DEBUG, FileHandler, Formatter, getLogger


class Color:
    BLACK = "\033[30m"  # (文字)黒
    RED = "\033[31m"  # (文字)赤
    GREEN = "\033[32m"  # (文字)緑
    YELLOW = "\033[33m"  # (文字)黄
    BLUE = "\033[34m"  # (文字)青
    MAGENTA = "\033[35m"  # (文字)マゼンタ
    CYAN = "\033[36m"  # (文字)シアン
    WHITE = "\033[37m"  # (文字)白
    COLOR_DEFAULT = "\033[39m"  # 文字色をデフォルトに戻す
    BOLD = "\033[1m"  # 太字
    UNDERLINE = "\033[4m"  # 下線
    INVISIBLE = "\033[08m"  # 不可視
    REVERCE = "\033[07m"  # 文字色と背景色を反転
    BG_BLACK = "\033[40m"  # (背景)黒
    BG_RED = "\033[41m"  # (背景)赤
    BG_GREEN = "\033[42m"  # (背景)緑
    BG_YELLOW = "\033[43m"  # (背景)黄
    BG_BLUE = "\033[44m"  # (背景)青
    BG_MAGENTA = "\033[45m"  # (背景)マゼンタ
    BG_CYAN = "\033[46m"  # (背景)シアン
    BG_WHITE = "\033[47m"  # (背景)白
    BG_DEFAULT = "\033[49m"  # 背景色をデフォルトに戻す
    RESET = "\033[0m"  # 全てリセット

    @staticmethod
    def info(message):
        print(Color.GREEN + message + Color.RESET)

    @staticmethod
    def warn(message):
        print(Color.YELLOW + message + Color.RESET)

    @staticmethod
    def error(message):
        print(Color.RED + message + Color.RESET)


class Table:
    def __init__(self):
        self.columns = []
        self.rows = []
        self.rows_len = {}

    def text_counter(self, t):
        _text_counter = 0
        for c in t:
            j = unicodedata.east_asian_width(c)
            if "F" == j:
                _text_counter = _text_counter + 2
            elif "H" == j:
                _text_counter = _text_counter + 1
            elif "W" == j:
                _text_counter = _text_counter + 2
            elif "Na" == j:
                _text_counter = _text_counter + 1
            elif "A" == j:
                _text_counter = _text_counter + 2
            else:
                _text_counter = _text_counter + 1

        return _text_counter

    def add_column(self, header: str):
        self.columns.append(header)
        self.rows_len[header] = []

    def add_row(self, *row: str):
        self.rows.append(row)
        for colum, value in zip(self.columns, row):
            self.rows_len[colum].append(self.text_counter(value))

    def grid(self, row):
        grid_data = []
        for row_len_max, value in zip(self.rows_len_max, row):
            grid_data.append(value + (row_len_max - self.text_counter(value)) * " ")
        return " ".join(grid_data)

    def print(self):
        self.rows_len_max = []
        for column in self.columns:
            row_len_max = max(self.rows_len[column])
            if row_len_max < len(column):
                self.rows_len_max.append(len(column))
            else:
                self.rows_len_max.append(row_len_max)
        print(Color.GREEN + self.grid(self.columns) + Color.RESET)
        print(Color.GREEN + self.grid([len(border_line) * "-" for border_line in self.columns]) + Color.RESET)
        for row in self.rows:
            print(self.grid(row))


def make_logger(name):
    logger = getLogger(name)
    logger.setLevel(DEBUG)

    fl_handler = FileHandler(filename=".log", encoding="utf-8", mode="w")
    fl_handler.setLevel(DEBUG)
    fl_handler.setFormatter(Formatter("[{levelname}] {asctime} [{filename}:{lineno}] {message}", style="{"))
    logger.addHandler(fl_handler)

    return logger


logger = make_logger(__name__)
