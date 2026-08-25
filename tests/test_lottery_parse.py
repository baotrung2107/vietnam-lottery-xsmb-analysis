from datetime import date

import pytest
from pydantic import ValidationError

from lottery import InvalidPage, Lottery, NoResultYet
from tests.pages import SELECTED, VALID_PRIZES, response


def test_valid_page_is_parsed():
    result = Lottery()._parse(response(), SELECTED)
    assert result.date == SELECTED
    assert result.special == 12345
    assert result.prize7_4 == 74


def test_redirect_to_another_day_is_rejected():
    """Trang nguồn chuyển hướng sang ngày khác vẫn trả HTTP 200 — đây là cách dữ liệu sai lọt vào."""
    redirected = response(url='https://xoso.com.vn/xsmb-24-08-2026.html')
    with pytest.raises(InvalidPage, match='chuyển hướng'):
        Lottery()._parse(redirected, SELECTED)


def test_page_showing_only_another_date_is_rejected():
    with pytest.raises(InvalidPage, match='không nhắc tới ngày'):
        Lottery()._parse(response(date_text='24-08-2026'), SELECTED)


def test_page_without_any_recognisable_date_is_accepted():
    """Không đọc được ngày nào trên trang thì bỏ qua cổng này, không đoán bừa rồi loại oan."""
    result = Lottery()._parse(response(date_text='ngay 25 thang 8 nam 2026'), SELECTED)
    assert result.special == 12345


def test_missing_prize_element_is_rejected():
    broken = {**VALID_PRIZES, 'prize3': [f'3000{i}' for i in range(1, 6)]}
    with pytest.raises(InvalidPage, match='số lượng giải không khớp'):
        Lottery()._parse(response(broken), SELECTED)


def test_extra_prize_element_is_rejected():
    broken = {**VALID_PRIZES, 'prize7': VALID_PRIZES['prize7'] + ['75']}
    with pytest.raises(InvalidPage, match='số lượng giải không khớp'):
        Lottery()._parse(response(broken), SELECTED)


def test_non_numeric_prize_is_rejected():
    broken = {**VALID_PRIZES, 'prize1': ['...']}
    with pytest.raises(InvalidPage, match='không phải số'):
        Lottery()._parse(response(broken), SELECTED)


def test_out_of_range_prize_is_rejected():
    broken = {**VALID_PRIZES, 'prize7': ['123', '72', '73', '74']}
    with pytest.raises(ValidationError):
        Lottery()._parse(response(broken), SELECTED)


def test_empty_page_reports_no_result_yet():
    empty = {css_class: [] for css_class in VALID_PRIZES}
    with pytest.raises(NoResultYet):
        Lottery()._parse(response(empty), SELECTED)


def test_result_identical_to_another_day_is_rejected():
    """Hai ngày trùng nhau cả 27 giải là dấu hiệu trang trả kết quả của ngày khác."""
    lottery = Lottery()
    lottery._store(lottery._parse(response(), SELECTED))

    next_day = response(date_text='26-08-2026', url='https://xoso.com.vn/xsmb-26-08-2026.html')
    with pytest.raises(InvalidPage, match='trùng khớp hoàn toàn'):
        lottery._parse(next_day, date(2026, 8, 26))


def test_refetching_the_same_day_is_allowed():
    lottery = Lottery()
    lottery._store(lottery._parse(response(), SELECTED))
    again = lottery._parse(response(), SELECTED)
    assert again.date == SELECTED
