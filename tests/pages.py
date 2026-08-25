"""Trang kết quả giả lập, dùng chung cho các test cào dữ liệu — không chạm mạng."""

from dataclasses import dataclass
from datetime import date

SELECTED = date(2026, 8, 25)
URL = f'https://xoso.com.vn/xsmb-{SELECTED:%d-%m-%Y}.html'

VALID_PRIZES = {
    'special-prize': ['12345'],
    'prize1': ['54321'],
    'prize2': ['11111', '22222'],
    'prize3': [f'3000{i}' for i in range(1, 7)],
    'prize4': [f'400{i}' for i in range(1, 5)],
    'prize5': [f'500{i}' for i in range(1, 7)],
    'prize6': [f'60{i}' for i in range(1, 4)],
    'prize7': [f'7{i}' for i in range(1, 5)],
}


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200


def build_page(prizes: dict[str, list[str]] | None = None, date_text: str = '25-08-2026') -> str:
    prizes = VALID_PRIZES if prizes is None else prizes
    blocks = ''.join(
        f'<span class="{css_class}">{value}</span>' for css_class, values in prizes.items() for value in values
    )
    return f'<html><body><p>KQXSMB ngay {date_text}</p>{blocks}</body></html>'


def response(prizes=None, date_text: str = '25-08-2026', url: str = URL) -> FakeResponse:
    return FakeResponse(url=url, text=build_page(prizes, date_text))
