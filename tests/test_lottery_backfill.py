from datetime import date, timedelta

from dtos import Result
from lottery import Lottery

BASE = {
    'special': 12345,
    'prize1': 54321,
    'prize2_1': 11111,
    'prize2_2': 22222,
    **{f'prize3_{i}': 30000 + i for i in range(1, 7)},
    **{f'prize4_{i}': 4000 + i for i in range(1, 5)},
    **{f'prize5_{i}': 5000 + i for i in range(1, 7)},
    **{f'prize6_{i}': 600 + i for i in range(1, 4)},
    **{f'prize7_{i}': 70 + i for i in range(1, 5)},
}


def make_result(day: date, offset: int = 0) -> Result:
    return Result(date=day, **{**BASE, 'special': (BASE['special'] + offset) % 100000})


def lottery_with(days: list[date]) -> Lottery:
    lottery = Lottery()
    for offset, day in enumerate(days):
        lottery._store(make_result(day, offset))
    return lottery


def test_gap_before_the_last_stored_day_is_reported_missing():
    """Đúng lỗi làm mất vĩnh viễn 3 ngày trong kho: ngày hỏng nằm giữa chuỗi bị nhảy qua."""
    days = [date(2026, 8, 20), date(2026, 8, 22), date(2026, 8, 23)]
    missing = lottery_with(days).get_missing_dates(date(2026, 8, 23))
    assert missing == [date(2026, 8, 21)]


def test_forward_days_are_always_included_even_beyond_the_window():
    days = [date(2026, 8, 1)]
    missing = lottery_with(days).get_missing_dates(date(2026, 8, 10), backfill_days=2)
    assert missing == [date(2026, 8, 2) + timedelta(days=i) for i in range(9)]


def test_window_limits_how_far_back_the_backfill_looks():
    days = [date(2026, 8, 1), date(2026, 8, 20)]
    lottery = lottery_with(days)

    narrow = lottery.get_missing_dates(date(2026, 8, 20), backfill_days=5)
    assert narrow == [date(2026, 8, 16) + timedelta(days=i) for i in range(4)]

    wide = lottery.get_missing_dates(date(2026, 8, 20), backfill_days=None)
    assert len(wide) == 18
    assert wide[0] == date(2026, 8, 2)


def test_no_missing_dates_when_history_is_complete():
    days = [date(2026, 8, 20) + timedelta(days=i) for i in range(3)]
    assert lottery_with(days).get_missing_dates(date(2026, 8, 22)) == []


def test_empty_store_reports_nothing_to_fetch():
    assert Lottery().get_missing_dates(date(2026, 8, 25)) == []


def test_dataframes_are_sorted_by_date_after_a_backfill():
    """Cào bù chèn ngày cũ vào sau ngày mới; mọi thống kê phía sau đòi dữ liệu theo trình tự thời gian."""
    lottery = lottery_with([date(2026, 8, 20), date(2026, 8, 22)])
    lottery._store(make_result(date(2026, 8, 21), offset=99))
    lottery.generate_dataframes()

    dates = lottery.get_raw_data()['date'].tolist()
    assert dates == sorted(dates)
    assert lottery.get_last_date() == date(2026, 8, 22)


def test_duplicate_results_across_days_are_reported():
    lottery = Lottery()
    lottery._store(make_result(date(2026, 8, 20), offset=0))
    lottery._store(make_result(date(2026, 8, 21), offset=0))

    duplicates = list(lottery.find_duplicate_results().values())
    assert duplicates == [[date(2026, 8, 20), date(2026, 8, 21)]]


def test_stored_history_contains_exactly_one_known_duplicate_pair():
    """Cặp 21/09/2006 và 25/09/2006 trùng nhau cả 27 giải — lỗi dữ liệu có sẵn, chưa sửa được."""
    lottery = Lottery()
    lottery.load()
    duplicates = list(lottery.find_duplicate_results().values())
    assert duplicates == [[date(2006, 9, 21), date(2006, 9, 25)]]
