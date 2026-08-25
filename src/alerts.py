"""Theo dõi chữ số 0-9 ở 2 số cuối giải đặc biệt và báo khi có chữ số vắng mặt bất thường lâu.

Chạy sau src/analyze.py trong workflow. Luôn in bảng tình trạng 10 chữ số ra log; khi có chữ số
vượt ngưỡng hiếm thì đặt output `alert=true` để workflow mở (hoặc cập nhật) một issue nhắc.

Lưu ý về ý nghĩa: cả 10 chữ số đều nằm trong đúng 19/100 số, nên xác suất mỗi kỳ luôn là 19% cho
mọi chữ số và KHÔNG đổi theo chuỗi vắng mặt. Cảnh báo ở đây mô tả chuyện đã xảy ra là hiếm, chứ
không có nghĩa chữ số đó sắp về.
"""

__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

from probability import DIGIT_HIT_PROBABILITY, UNUSUAL_RARITY, DigitStatus, all_digit_statuses, expected_wait, forecast

DATA_FILE = 'data/xsmb.csv'
FORECAST_DRAWS = 7
ISSUE_TITLE = 'Cảnh báo: chữ số vắng mặt bất thường ở 2 số cuối giải đặc biệt'


def load_results(path: str = DATA_FILE) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=['date'])


def format_table(statuses: list[DigitStatus]) -> str:
    lines = [
        '| Chữ số | Vắng liên tiếp | Lần cuối xuất hiện | Độ hiếm của chuỗi này |',
        '|:------:|:--------------:|:------------------:|:---------------------:|',
    ]
    for status in statuses:
        last_seen = f'{status.last_seen:%d/%m/%Y}' if status.last_seen else 'chưa từng'
        flag = ' ⚠️' if status.unusual else ''
        lines.append(f'| **{status.digit}**{flag} | {status.streak} kỳ | {last_seen} | {status.rarity:.2%} |')
    return '\n'.join(lines)


def format_forecast() -> str:
    lines = [
        '| Kỳ tới | Trúng đúng kỳ này (lần đầu) | Đã trúng ít nhất một lần |',
        '|:------:|:---------------------------:|:------------------------:|',
    ]
    for draw, first, cumulative in forecast(FORECAST_DRAWS):
        lines.append(f'| {draw} | {first:.2%} | {cumulative:.2%} |')
    return '\n'.join(lines)


def build_report(statuses: list[DigitStatus], last_date: pd.Timestamp) -> str:
    unusual = [status for status in statuses if status.unusual]

    parts = [
        f'Tính tới kỳ quay **{last_date:%d/%m/%Y}**.',
        '',
        '## Chữ số đang vắng mặt bất thường',
        '',
    ]
    if unusual:
        for status in unusual:
            parts.append(
                f'- **Chữ số {status.digit}** vắng mặt **{status.streak} kỳ** liên tiếp. '
                f'Một chuỗi dài như vậy chỉ xuất hiện với khả năng {status.rarity:.2%}.'
            )
    else:
        parts.append(f'- Không có chữ số nào vượt ngưỡng hiếm {UNUSUAL_RARITY:.0%}.')

    parts += [
        '',
        '## Tình trạng cả 10 chữ số',
        '',
        format_table(statuses),
        '',
        f'## Xác suất {FORECAST_DRAWS} kỳ tới (đúng cho mọi chữ số)',
        '',
        format_forecast(),
        '',
        '## Đọc cho đúng',
        '',
        f'Mỗi chữ số 0-9 nằm trong đúng **19/100** số hai chữ số, nên xác suất mỗi kỳ luôn là '
        f'**{DIGIT_HIT_PROBABILITY:.0%}** — giống hệt nhau cho cả mười chữ số và **không đổi** dù đang '
        f'vắng mặt bao lâu. Trung bình phải chờ {expected_wait():.1f} kỳ mới có một lần, tính từ hôm nay '
        f'chứ không tính ngược lại.',
        '',
        'Cảnh báo này nói rằng chuyện **đã xảy ra** là hiếm. Nó không nói chữ số đó sắp về.',
    ]
    return '\n'.join(parts)


def write_output(name: str, value: str) -> None:
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f'{name}={value}\n')


def main() -> int:
    results = load_results()
    last_date = results['date'].max()
    statuses = all_digit_statuses(results)
    unusual = [status for status in statuses if status.unusual]

    print(f'Tình trạng chữ số ở 2 số cuối giải đặc biệt, tính tới {last_date:%d/%m/%Y}:')
    for status in statuses:
        last_seen = f'{status.last_seen:%d/%m/%Y}' if status.last_seen else 'chưa từng'
        mark = '  <-- bất thường' if status.unusual else ''
        print(
            f'  chữ số {status.digit}: vắng {status.streak:3d} kỳ | lần cuối {last_seen} | '
            f'độ hiếm {status.rarity:7.2%}{mark}'
        )

    report = build_report(statuses, last_date)

    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(report + '\n')

    body_path = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'gan-alert.md'
    body_path.write_text(report, encoding='utf-8')

    write_output('alert', 'true' if unusual else 'false')
    write_output('title', ISSUE_TITLE)
    write_output('body_path', str(body_path))

    if unusual:
        digits = ', '.join(str(status.digit) for status in unusual)
        message = f'Chữ số {digits} đang vắng mặt bất thường ở 2 số cuối giải đặc biệt'
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print(f'::warning::{message}')
        else:
            print(f'CẢNH BÁO: {message}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
