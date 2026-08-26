"""Công thức xác suất cho 2 số cuối của giải đặc biệt.

Mỗi kỳ quay lấy ra một số hai chữ số trong 100 khả năng 00-99, các kỳ độc lập hoàn toàn với nhau.
Từ đó mọi câu hỏi dạng "n kỳ tới có ra không" đều quy về hai phép tính:

    P(n kỳ tới đều trượt)      = (1 - p) ^ n
    P(ít nhất một lần trúng)   = 1 - (1 - p) ^ n

trong đó p là số lượng số thoả điều kiện chia cho 100.

Chỗ sai kinh điển là cộng cả những kỳ ĐÃ trượt vào số mũ n. Không được: kỳ đã quay không còn là
khả năng nữa. Đang trượt 20 kỳ mà muốn biết khả năng trượt tới kỳ thứ 30 thì số mũ là 10, không
phải 30 — chênh nhau 68 lần. Vì vậy mọi hàm ở đây chỉ nhận số kỳ CHƯA quay.

Hệ quả trực tiếp: chuỗi trượt dài không làm kỳ kế tiếp dễ trúng hơn. Đo trên 20 năm dữ liệu, sau
0, 3, 6, 9 hay 12 kỳ trượt liên tiếp thì kỳ kế tiếp vẫn trúng khoảng 19%.
"""

__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

from datetime import date
from typing import NamedTuple

import numpy as np
import pandas as pd

# Mỗi chữ số 0-9 nằm trong đúng 19 số hai chữ số: 10 số ở hàng chục cộng 10 số ở hàng đơn vị,
# trừ đi số có cả hai chữ số giống nhau bị đếm hai lần (55 với chữ số 5, 77 với chữ số 7...).
DIGIT_HIT_PROBABILITY = 0.19

# Chuỗi trượt hiếm tới mức này thì coi là bất thường và đáng báo. 0.81^15 = 4.24%.
UNUSUAL_RARITY = 0.05


def numbers_containing(digit: int) -> list[int]:
    """Các số 00-99 có chứa chữ số đã cho."""
    if not 0 <= digit <= 9:
        raise ValueError(f'chữ số phải nằm trong 0-9, nhận được {digit}')
    return [value for value in range(100) if str(digit) in f'{value:02d}']


def hit_probability(numbers: list[int]) -> float:
    """Xác suất một kỳ rơi vào tập số đã cho."""
    return len(set(numbers)) / 100


def probability_none(draws: int, probability: float = DIGIT_HIT_PROBABILITY) -> float:
    """Khả năng `draws` kỳ TỚI đều trượt. Chỉ đếm kỳ chưa quay, không cộng kỳ đã trượt."""
    if draws < 0:
        raise ValueError(f'số kỳ không thể âm, nhận được {draws}')
    return (1 - probability) ** draws


def probability_at_least_once(draws: int, probability: float = DIGIT_HIT_PROBABILITY) -> float:
    """Khả năng trúng ít nhất một lần trong `draws` kỳ tới."""
    return 1 - probability_none(draws, probability)


def probability_first_hit_on(draw: int, probability: float = DIGIT_HIT_PROBABILITY) -> float:
    """Khả năng kỳ thứ `draw` là lần trúng ĐẦU TIÊN: trượt hết các kỳ trước rồi trúng đúng kỳ này."""
    if draw < 1:
        raise ValueError(f'kỳ phải tính từ 1, nhận được {draw}')
    return probability_none(draw - 1, probability) * probability


def expected_wait(probability: float = DIGIT_HIT_PROBABILITY) -> float:
    """Trung bình phải chờ bao nhiêu kỳ mới có một lần trúng — không đổi theo chuỗi trượt hiện tại."""
    return 1 / probability


class DigitStatus(NamedTuple):
    digit: int
    streak: int  # số kỳ liên tiếp vắng mặt, tính tới kỳ mới nhất
    last_seen: date | None
    rarity: float  # khả năng một chuỗi trượt dài bằng chừng này xuất hiện, tính từ điểm bất kỳ
    unusual: bool

    @property
    def label(self) -> str:
        return f'{self.digit}'


def digit_status(results: pd.DataFrame, digit: int, unusual_rarity: float = UNUSUAL_RARITY) -> DigitStatus:
    """Tình trạng vắng mặt của một chữ số trong 2 số cuối giải đặc biệt."""
    tails = (results['special'] % 100).to_numpy()
    dates = results['date'].to_numpy()

    streak = 0
    last_seen = None
    for index in range(len(tails) - 1, -1, -1):
        if str(digit) in f'{tails[index]:02d}':
            last_seen = pd.Timestamp(dates[index]).date()
            break
        streak += 1

    rarity = probability_none(streak)
    return DigitStatus(
        digit=digit,
        streak=streak,
        last_seen=last_seen,
        rarity=rarity,
        unusual=rarity < unusual_rarity,
    )


def all_digit_statuses(results: pd.DataFrame, unusual_rarity: float = UNUSUAL_RARITY) -> list[DigitStatus]:
    """Tình trạng của cả 10 chữ số, số vắng lâu nhất xếp trước."""
    statuses = [digit_status(results, digit, unusual_rarity) for digit in range(10)]
    return sorted(statuses, key=lambda status: -status.streak)


def forecast(draws: int, probability: float = DIGIT_HIT_PROBABILITY) -> list[tuple[int, float, float]]:
    """Bảng dự báo cho `draws` kỳ tới: (kỳ thứ mấy, trúng đúng kỳ này, đã trúng ít nhất một lần)."""
    return [
        (draw, probability_first_hit_on(draw, probability), probability_at_least_once(draw, probability))
        for draw in range(1, draws + 1)
    ]


def distinct_digits(numbers: list[int]) -> list[int]:
    """Các chữ số phân biệt tạo nên một nhóm số hai chữ số, xếp tăng dần."""
    found: set[int] = set()
    for value in numbers:
        found.add(value // 10)
        found.add(value % 10)
    return sorted(found)


def latest_prize7(results: pd.DataFrame) -> list[int]:
    """Bốn số của giải bảy ở kỳ mới nhất."""
    latest = results.iloc[-1]
    return [int(latest[f'prize7_{position}']) % 100 for position in range(1, 5)]


def prize7_digit_statuses(
    results: pd.DataFrame, unusual_rarity: float = UNUSUAL_RARITY
) -> tuple[list[int], list[DigitStatus]]:
    """Giải bảy kỳ mới nhất, kèm tình trạng vắng mặt của từng chữ số tạo nên nó.

    Giải bảy quay trước giải đặc biệt vài phút trong cùng buổi, nên hay bị nghĩ là có liên hệ.
    Đo trên toàn bộ lịch sử thì không: mỗi chữ số của giải bảy xuất hiện ở 2 số cuối giải đặc biệt
    đúng 19% số kỳ, bằng nền ngẫu nhiên. Bảng này để theo dõi, không phải để dự đoán.
    """
    numbers = latest_prize7(results)
    statuses = [digit_status(results, digit, unusual_rarity) for digit in distinct_digits(numbers)]
    return numbers, sorted(statuses, key=lambda status: -status.streak)


def prize7_ab_hits(results: pd.DataFrame) -> pd.Series:
    """Chuỗi trúng/trượt theo kỳ: A HOẶC B của số giải bảy thứ nhất có mặt trong 2 số cuối giải đặc biệt."""
    return prize7_a_hits(results) | prize7_b_hits(results)


def prize7_a_hits(results: pd.DataFrame) -> pd.Series:
    """A (chữ số hàng chục của số giải bảy thứ nhất) có mặt trong 2 số cuối giải đặc biệt."""
    tails = results['special'] % 100
    a = (results['prize7_1'] % 100) // 10
    return (a == tails // 10) | (a == tails % 10)


def prize7_b_hits(results: pd.DataFrame) -> pd.Series:
    """B (chữ số hàng đơn vị của số giải bảy thứ nhất) có mặt trong 2 số cuối giải đặc biệt."""
    tails = results['special'] % 100
    b = (results['prize7_1'] % 100) % 10
    return (b == tails // 10) | (b == tails % 10)


# Ngưỡng báo sớm cho biến cố gộp A hoặc B, theo yêu cầu người dùng: từ 5 kỳ trượt liên tiếp.
# Với tỉ lệ 35%/kỳ, chuỗi 5 kỳ có độ hiếm 0,65^5 ≈ 11,6% — tức cảnh báo sẽ sáng khá thường xuyên;
# đây là lựa chọn chủ động đánh đổi ồn lấy sớm. Các biến cố đơn A, B giữ ngưỡng theo độ hiếm 5%.
PRIZE7_AB_ALERT_STREAK = 5


def default_alert_streak(hit_rate: float, unusual_rarity: float = UNUSUAL_RARITY) -> int:
    """Chuỗi trượt ngắn nhất có độ hiếm dưới `unusual_rarity` với tỉ lệ trúng đã cho.

    hit_rate = 0 (biến cố chưa từng trúng — gặp được trên mẫu nhỏ) thì không chuỗi nào là hiếm:
    trả về một ngưỡng không bao giờ chạm tới, thay vì lặp vô hạn.
    """
    if hit_rate <= 0:
        return 10**9
    if hit_rate >= 1:
        return 1
    streak = 0
    while (1 - hit_rate) ** streak >= unusual_rarity:
        streak += 1
    return streak


class CycleStatus(NamedTuple):
    name: str  # tên biến cố, dùng để hiển thị
    streak: int  # số kỳ trượt liên tiếp tính tới kỳ mới nhất
    last_hit: date | None
    hits: int  # tổng số lượt trúng trong toàn lịch sử
    hit_rate: float  # tỉ lệ trúng đo trên toàn lịch sử
    mean_gap: float  # trung bình cách bao nhiêu kỳ giữa hai lần trúng
    median_gap: float
    p90_gap: int  # 90% các lần chờ đều ngắn hơn hoặc bằng mức này
    max_gap: int  # lần chờ dài nhất từng ghi nhận
    rarity: float  # độ hiếm của chuỗi trượt hiện tại: (1 - hit_rate) ^ streak
    alert_streak: int  # trượt từ mức này trở lên thì cảnh báo
    unusual: bool


def _cycle(
    name: str,
    hit_series: pd.Series,
    dates,
    hit_rate: float | None,
    alert_streak: int | None,
    unusual_rarity: float,
) -> CycleStatus:
    hits = hit_series.to_numpy()

    streak = 0
    last_hit = None
    for index in range(len(hits) - 1, -1, -1):
        if hits[index]:
            last_hit = pd.Timestamp(dates[index]).date()
            break
        streak += 1

    if hit_rate is None:
        hit_rate = float(hits.mean())
    if alert_streak is None:
        alert_streak = default_alert_streak(hit_rate, unusual_rarity)

    positions = np.flatnonzero(hits)
    gaps = np.diff(positions) if len(positions) > 1 else np.array([1])

    return CycleStatus(
        name=name,
        streak=streak,
        last_hit=last_hit,
        hits=int(hits.sum()),
        hit_rate=hit_rate,
        mean_gap=float(gaps.mean()),
        median_gap=float(np.median(gaps)),
        p90_gap=int(np.percentile(gaps, 90)),
        max_gap=int(gaps.max()),
        rarity=(1 - hit_rate) ** streak,
        alert_streak=alert_streak,
        unusual=streak >= alert_streak,
    )


def prize7_ab_cycle(
    results: pd.DataFrame,
    unusual_rarity: float = UNUSUAL_RARITY,
    hit_rate: float | None = None,
    alert_streak: int | None = PRIZE7_AB_ALERT_STREAK,
) -> CycleStatus:
    """Chu kỳ biến cố gộp: A hoặc B của giải bảy thứ nhất có mặt trong 2 số cuối giải đặc biệt.

    Ngưỡng mặc định 5 kỳ là mức BÁO SỚM người dùng chọn (độ hiếm ~11,6%), không phải mức hiếm 5%.
    Cảnh báo mô tả chuỗi chờ đã dài so với nhịp lịch sử — xác suất kỳ tới vẫn bằng hit_rate.
    """
    return _cycle(
        'A hoặc B', prize7_ab_hits(results), results['date'].to_numpy(), hit_rate, alert_streak, unusual_rarity
    )


def prize7_a_cycle(
    results: pd.DataFrame,
    unusual_rarity: float = UNUSUAL_RARITY,
    hit_rate: float | None = None,
    alert_streak: int | None = None,
) -> CycleStatus:
    """Chu kỳ riêng của A (hàng chục giải bảy 1) trong 2 số cuối giải đặc biệt — tỉ lệ ~19%/kỳ."""
    return _cycle('Chỉ A', prize7_a_hits(results), results['date'].to_numpy(), hit_rate, alert_streak, unusual_rarity)


def prize7_b_cycle(
    results: pd.DataFrame,
    unusual_rarity: float = UNUSUAL_RARITY,
    hit_rate: float | None = None,
    alert_streak: int | None = None,
) -> CycleStatus:
    """Chu kỳ riêng của B (hàng đơn vị giải bảy 1) trong 2 số cuối giải đặc biệt — tỉ lệ ~19%/kỳ."""
    return _cycle('Chỉ B', prize7_b_hits(results), results['date'].to_numpy(), hit_rate, alert_streak, unusual_rarity)


def prize7_cycles(results: pd.DataFrame) -> list[CycleStatus]:
    """Cả ba chu kỳ để hiển thị chung một bảng: A, B, và A hoặc B."""
    return [prize7_a_cycle(results), prize7_b_cycle(results), prize7_ab_cycle(results)]


# "Khan" định nghĩa theo nhịp chờ của chính loại biến cố: vắng dài hơn 90% các lần chờ lịch sử.
# Chữ số trong XY (19%/kỳ): p90 ≈ 10 kỳ. Một số 00-99 cụ thể (1%/kỳ): p90 ≈ 230 kỳ.
DIGIT_BREAK_STREAK = 10
NUMBER_BREAK_STREAK = 230
NUMBER_HIT_PROBABILITY = 0.01


class DroughtBreak(NamedTuple):
    kind: str  # 'chữ số' hoặc 'số'
    label: str
    missed: int  # số kỳ vắng ngay trước khi về lại
    rarity: float  # độ hiếm của chuỗi vắng đó
    previous_seen: date | None  # lần xuất hiện gần nhất trước chuỗi vắng
    returned: date  # ngày về lại


def drought_breaks(
    results: pd.DataFrame,
    digit_streak: int = DIGIT_BREAK_STREAK,
    number_streak: int = NUMBER_BREAK_STREAK,
) -> list[DroughtBreak]:
    """Các số khan vừa về ở kỳ MỚI NHẤT: chữ số và con số XY kết thúc một chuỗi vắng dài.

    Chạy sau khi dữ liệu ngày mới đã vào kho, nên "kỳ mới nhất" chính là kỳ vừa quay xong.
    Báo cáo mô tả chuỗi vắng vừa kết thúc — nó không nói gì về các kỳ sắp tới.
    """
    tails = (results['special'] % 100).to_numpy()
    dates = results['date'].to_numpy()
    today_index = len(tails) - 1
    today_tail = int(tails[today_index])
    returned = pd.Timestamp(dates[today_index]).date()

    breaks: list[DroughtBreak] = []

    for digit in sorted({today_tail // 10, today_tail % 10}):
        missed = 0
        previous_seen = None
        for index in range(today_index - 1, -1, -1):
            if str(digit) in f'{tails[index]:02d}':
                previous_seen = pd.Timestamp(dates[index]).date()
                break
            missed += 1
        if missed >= digit_streak:
            breaks.append(
                DroughtBreak(
                    kind='chữ số',
                    label=str(digit),
                    missed=missed,
                    rarity=(1 - DIGIT_HIT_PROBABILITY) ** missed,
                    previous_seen=previous_seen,
                    returned=returned,
                )
            )

    previous = np.flatnonzero(tails[:today_index] == today_tail)
    missed = today_index - int(previous[-1]) - 1 if len(previous) else today_index
    if missed >= number_streak:
        breaks.append(
            DroughtBreak(
                kind='số',
                label=f'{today_tail:02d}',
                missed=missed,
                rarity=(1 - NUMBER_HIT_PROBABILITY) ** missed,
                previous_seen=pd.Timestamp(dates[int(previous[-1])]).date() if len(previous) else None,
                returned=returned,
            )
        )

    return sorted(breaks, key=lambda item: item.rarity)
