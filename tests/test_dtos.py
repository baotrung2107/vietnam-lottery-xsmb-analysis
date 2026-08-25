from datetime import date

import pytest
from pydantic import ValidationError

from dtos import Result, ResultList

VALID = {
    'date': date(2026, 8, 25),
    'special': 85080,
    'prize1': 76371,
    'prize2_1': 11111,
    'prize2_2': 22222,
    **{f'prize3_{i}': 30000 + i for i in range(1, 7)},
    **{f'prize4_{i}': 4000 + i for i in range(1, 5)},
    **{f'prize5_{i}': 5000 + i for i in range(1, 7)},
    **{f'prize6_{i}': 600 + i for i in range(1, 4)},
    **{f'prize7_{i}': 70 + i for i in range(1, 5)},
}


def test_valid_result_is_accepted():
    result = Result(**VALID)
    assert result.special == 85080


def test_prizes_returns_27_numbers_without_date():
    prizes = Result(**VALID).prizes()
    assert len(prizes) == 27
    assert date(2026, 8, 25) not in prizes


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('special', 100000),  # giải đặc biệt chỉ có 5 chữ số
        ('special', -1),
        ('prize4_1', 10000),  # giải tư 4 chữ số
        ('prize6_1', 1000),  # giải sáu 3 chữ số
        ('prize7_1', 100),  # giải bảy 2 chữ số
    ],
)
def test_out_of_range_prize_is_rejected(field, value):
    with pytest.raises(ValidationError):
        Result(**{**VALID, field: value})


def test_every_stored_record_still_validates():
    """Ràng buộc miền giá trị mới không được làm hỏng bất kỳ kỳ quay nào đã lưu."""
    with open('data/xsmb.json', 'r', encoding='utf-8') as f:
        data = ResultList.model_validate_json(f.read())
    assert len(data.root) > 7000
