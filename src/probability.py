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
