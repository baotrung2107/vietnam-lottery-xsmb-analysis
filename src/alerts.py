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

import probability

DATA_FILE = 'data/xsmb.csv'
FORECAST_DRAWS = 7
ISSUE_TITLE = 'Cảnh báo: chữ số vắng mặt bất thường ở 2 số cuối giải đặc biệt'


def load_results(path: str = DATA_FILE) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=['date'])


def format_table(statuses: list[probability.DigitStatus]) -> str:
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
    for draw, first, cumulative in probability.forecast(FORECAST_DRAWS):
        lines.append(f'| {draw} | {first:.2%} | {cumulative:.2%} |')
    return '\n'.join(lines)


def format_prize7(numbers: list[int], statuses: list[probability.DigitStatus]) -> str:
    """Bảng chữ số của giải bảy kỳ mới nhất kèm tình trạng vắng mặt ở 2 số cuối giải đặc biệt."""
    drawn = ', '.join(f'`{value:02d}`' for value in numbers)
    lines = [
        f'Giải bảy kỳ mới nhất: {drawn} — gồm các chữ số '
        + ', '.join(f'**{status.digit}**' for status in sorted(statuses, key=lambda s: s.digit))
        + '.',
        '',
        '| Chữ số | Vắng liên tiếp | Lần cuối xuất hiện | Độ hiếm của chuỗi này |',
        '|:------:|:--------------:|:------------------:|:---------------------:|',
    ]
    for status in statuses:
        last_seen = f'{status.last_seen:%d/%m/%Y}' if status.last_seen else 'chưa từng'
        flag = ' ⚠️' if status.unusual else ''
        lines.append(f'| **{status.digit}**{flag} | {status.streak} kỳ | {last_seen} | {status.rarity:.2%} |')
    return '\n'.join(lines)


def format_cycles(cycles: list[probability.CycleStatus]) -> str:
    """Bảng chu kỳ ba biến cố của giải bảy thứ nhất: chỉ A, chỉ B, và A hoặc B."""
    lines = [
        'Biến cố theo dõi: chữ số **A** (hàng chục) và **B** (hàng đơn vị) của số giải bảy '
        'THỨ NHẤT có mặt trong 2 số cuối giải đặc biệt cùng kỳ.',
        '',
        '| Biến cố | Tỉ lệ/kỳ | Lượt trúng | Đang trượt | TB cách | Trung vị | 90% ≤ | Dài nhất | Ngưỡng báo |',
        '|:-------:|:--------:|:----------:|:----------:|:-------:|:--------:|:-----:|:--------:|:----------:|',
    ]
    for cycle in cycles:
        flag = ' ⚠️' if cycle.unusual else ''
        lines.append(
            f'| **{cycle.name}**{flag} | {cycle.hit_rate:.1%} | {cycle.hits} | **{cycle.streak} kỳ** '
            f'| {cycle.mean_gap:.1f} kỳ | {cycle.median_gap:.0f} | {cycle.p90_gap} | {cycle.max_gap} '
            f'| {cycle.alert_streak} kỳ |'
        )
    ab = cycles[-1]
    lines += [
        '',
        f'Ngưỡng của **A hoặc B** đặt ở mức báo sớm {ab.alert_streak} kỳ theo yêu cầu '
        f'(độ hiếm {(1 - ab.hit_rate) ** ab.alert_streak:.1%} — sẽ kêu vài lần mỗi tháng); '
        f'ngưỡng của A và B riêng lẻ theo mức hiếm 5%.',
    ]
    return '\n'.join(lines)


def format_breaks(breaks: list[probability.DroughtBreak]) -> str:
    """Mục "số khan vừa về": các chuỗi vắng dài vừa kết thúc ở kỳ mới nhất."""
    if not breaks:
        return 'Kỳ này không có số khan nào vừa về (ngưỡng: chữ số vắng ≥ 10 kỳ, con số vắng ≥ 230 kỳ).'
    lines = [
        '| Vừa về | Vắng trước đó | Lần cuối trước chuỗi | Độ hiếm của chuỗi vừa dứt |',
        '|:------:|:-------------:|:--------------------:|:-------------------------:|',
    ]
    for item in breaks:
        previous = f'{item.previous_seen:%d/%m/%Y}' if item.previous_seen else 'chưa từng'
        flag = ' ⚠️' if item.rarity < probability.UNUSUAL_RARITY else ''
        lines.append(f'| {item.kind} **{item.label}**{flag} | {item.missed} kỳ | {previous} | {item.rarity:.1%} |')
    lines += [
        '',
        'Chuỗi khan đã KẾT THÚC — bảng này tổng kết quá khứ. Nó không làm số vừa về dễ hay khó ra hơn ở các kỳ tới.',
    ]
    return '\n'.join(lines)


def build_report(
    statuses: list[probability.DigitStatus],
    last_date: pd.Timestamp,
    prize7_numbers: list[int] | None = None,
    prize7_statuses: list[probability.DigitStatus] | None = None,
    cycles: list[probability.CycleStatus] | None = None,
    breaks: list[probability.DroughtBreak] | None = None,
) -> str:
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
        parts.append(f'- Không có chữ số nào vượt ngưỡng hiếm {probability.UNUSUAL_RARITY:.0%}.')

    if prize7_numbers and prize7_statuses:
        quiet = [status for status in prize7_statuses if status.unusual]
        parts += ['', '## Chữ số của giải bảy kỳ mới nhất', '', format_prize7(prize7_numbers, prize7_statuses), '']
        if quiet:
            digits = ', '.join(str(status.digit) for status in quiet)
            parts.append(f'Trong đó chữ số **{digits}** đang vắng mặt bất thường.')
        else:
            parts.append('Không chữ số nào trong giải bảy kỳ này đang vắng mặt bất thường.')

    if breaks is not None:
        parts += ['', '## Số khan vừa về kỳ này', '', format_breaks(breaks)]

    if cycles:
        parts += ['', '## Chu kỳ A, B của giải bảy thứ nhất', '', format_cycles(cycles)]
        for cycle in cycles:
            if cycle.unusual:
                parts.append('')
                parts.append(
                    f'Biến cố **{cycle.name}** đã trượt **{cycle.streak} kỳ** liên tiếp — chạm ngưỡng '
                    f'{cycle.alert_streak} kỳ. Điều đó KHÔNG làm kỳ tới dễ trúng hơn: xác suất kỳ tới '
                    f'vẫn là {cycle.hit_rate:.1%}.'
                )

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
        f'**{probability.DIGIT_HIT_PROBABILITY:.0%}** — giống hệt nhau cho cả mười chữ số và **không đổi** dù đang '
        f'vắng mặt bao lâu. Trung bình phải chờ {probability.expected_wait():.1f} kỳ mới có một lần, tính từ hôm nay '
        f'chứ không tính ngược lại.',
        '',
        'Cảnh báo này nói rằng chuyện **đã xảy ra** là hiếm. Nó không nói chữ số đó sắp về.',
        '',
        'Giải bảy quay trước giải đặc biệt vài phút nên hay bị nghĩ là có liên hệ. Đo trên toàn bộ '
        'lịch sử thì không có: mỗi chữ số của giải bảy xuất hiện ở 2 số cuối giải đặc biệt đúng 19% '
        'số kỳ, bằng đúng mức của một chữ số lấy ngẫu nhiên.',
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
    statuses = probability.all_digit_statuses(results)
    unusual = [status for status in statuses if status.unusual]
    prize7_numbers, prize7_statuses = probability.prize7_digit_statuses(results)
    cycles = probability.prize7_cycles(results)
    breaks = probability.drought_breaks(results)

    print(f'Tình trạng chữ số ở 2 số cuối giải đặc biệt, tính tới {last_date:%d/%m/%Y}:')
    for status in statuses:
        last_seen = f'{status.last_seen:%d/%m/%Y}' if status.last_seen else 'chưa từng'
        mark = '  <-- bất thường' if status.unusual else ''
        print(
            f'  chữ số {status.digit}: vắng {status.streak:3d} kỳ | lần cuối {last_seen} | '
            f'độ hiếm {status.rarity:7.2%}{mark}'
        )

    print()
    drawn = ', '.join(f'{value:02d}' for value in prize7_numbers)
    print(f'Giải bảy kỳ mới nhất: {drawn}')
    for status in prize7_statuses:
        mark = '  <-- bất thường' if status.unusual else ''
        print(f'  chữ số {status.digit}: vắng {status.streak:3d} kỳ | độ hiếm {status.rarity:7.2%}{mark}')

    print()
    print('Chu kỳ A, B của giải bảy 1 (so với 2 số cuối giải đặc biệt):')
    for cycle in cycles:
        mark = '  <-- chạm ngưỡng' if cycle.unusual else ''
        print(
            f'  {cycle.name}: trượt {cycle.streak} kỳ liên tiếp | nhịp TB {cycle.mean_gap:.1f} kỳ | '
            f'lượt trúng {cycle.hits} | ngưỡng báo {cycle.alert_streak} kỳ{mark}'
        )

    print()
    if breaks:
        print('Số khan vừa về kỳ này:')
        for item in breaks:
            print(f'  {item.kind} {item.label}: về sau {item.missed} kỳ vắng (độ hiếm {item.rarity:.1%})')
    else:
        print('Số khan vừa về kỳ này: không có')

    report = build_report(statuses, last_date, prize7_numbers, prize7_statuses, cycles, breaks)

    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(report + '\n')

    body_path = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'gan-alert.md'
    body_path.write_text(report, encoding='utf-8')

    cycle_alerts = [cycle for cycle in cycles if cycle.unusual]
    rare_breaks = [item for item in breaks if item.rarity < probability.UNUSUAL_RARITY]
    write_output('alert', 'true' if (unusual or cycle_alerts or rare_breaks) else 'false')
    write_output('title', ISSUE_TITLE)
    write_output('body_path', str(body_path))

    messages = []
    if unusual:
        digits = ', '.join(str(status.digit) for status in unusual)
        messages.append(f'Chữ số {digits} đang vắng mặt bất thường ở 2 số cuối giải đặc biệt')
    for item in rare_breaks:
        messages.append(f'{item.kind} {item.label} vừa về sau chuỗi khan {item.missed} kỳ (độ hiếm {item.rarity:.1%})')
    for cycle in cycle_alerts:
        messages.append(
            f'Biến cố {cycle.name} của giải bảy 1 đã trượt {cycle.streak} kỳ liên tiếp — chạm ngưỡng {cycle.alert_streak} kỳ'
        )
    for message in messages:
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print(f'::warning::{message}')
        else:
            print(f'CẢNH BÁO: {message}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
