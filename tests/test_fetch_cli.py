from datetime import date, datetime

import pytest

import fetch
from fetch import DEFAULT_BACKFILL_DAYS, TIMEZONE, annotate, latest_expected_date, parse_args
from lottery import FetchStatus


class FakeLottery:
    """Thay Lottery thật trong test: không chạm mạng và không ghi đè file data của dự án."""

    def __init__(self, targets: list[date], statuses: list[FetchStatus]) -> None:
        self.targets = targets
        self.statuses = list(statuses)
        self.dumps = 0

    def load(self) -> None:
        pass

    def get_missing_dates(self, until, backfill_days=None) -> list[date]:
        return self.targets

    def fetch(self, selected_date) -> FetchStatus:
        return self.statuses.pop(0)

    def generate_dataframes(self) -> None:
        pass

    def dump(self) -> None:
        self.dumps += 1


def run_main(monkeypatch, targets, statuses) -> tuple[int, FakeLottery]:
    fake = FakeLottery(targets, statuses)
    monkeypatch.setattr(fetch, 'Lottery', lambda: fake)
    return fetch.main(['--delay', '0']), fake


@pytest.mark.parametrize(
    ('now', 'expected'),
    [
        (datetime(2026, 8, 25, 18, 35, tzinfo=TIMEZONE), date(2026, 8, 25)),
        (datetime(2026, 8, 25, 23, 59, tzinfo=TIMEZONE), date(2026, 8, 25)),
        (datetime(2026, 8, 25, 18, 34, tzinfo=TIMEZONE), date(2026, 8, 24)),
        (datetime(2026, 8, 25, 0, 1, tzinfo=TIMEZONE), date(2026, 8, 24)),
    ],
)
def test_latest_expected_date_waits_for_the_draw(now, expected):
    assert latest_expected_date(now) == expected


def test_default_arguments_backfill_a_short_window():
    args = parse_args([])
    assert args.backfill_days == DEFAULT_BACKFILL_DAYS
    assert args.backfill_all is False


def test_backfill_all_can_be_requested():
    assert parse_args(['--backfill-all']).backfill_all is True


def test_backfill_window_and_backfill_all_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args(['--backfill-all', '--backfill-days', '5'])


def test_annotate_is_silent_outside_github_actions(monkeypatch, capsys):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    annotate('warning', 'không nên in ra ở máy cá nhân')
    assert capsys.readouterr().out == ''


def test_annotate_reports_to_github_actions(monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    annotate('warning', '1/1 ngày cào lỗi')
    assert capsys.readouterr().out.strip() == '::warning::1/1 ngày cào lỗi'


def test_nothing_to_fetch_finishes_without_rewriting_the_data_files(monkeypatch):
    exit_code, fake = run_main(monkeypatch, [], [])
    assert exit_code == 0
    assert fake.dumps == 0


def test_a_successful_run_rewrites_the_data_files_once(monkeypatch):
    exit_code, fake = run_main(monkeypatch, [date(2026, 8, 25)], [FetchStatus.OK])
    assert exit_code == 0
    assert fake.dumps == 1


def test_one_bad_day_among_good_ones_does_not_fail_the_job(monkeypatch):
    """Một ngày hỏng lẻ chỉ là cảnh báo — cào bù sẽ thử lại ngày đó trong cửa sổ 30 ngày."""
    targets = [date(2026, 8, 24), date(2026, 8, 25)]
    exit_code, fake = run_main(monkeypatch, targets, [FetchStatus.ERROR, FetchStatus.OK])
    assert exit_code == 0
    assert fake.dumps == 1


def test_every_day_failing_fails_the_job(monkeypatch):
    """Hỏng toàn bộ nghĩa là bị chặn hoặc trang đổi cấu trúc — phải báo đỏ thay vì im lặng."""
    targets = [date(2026, 8, 24), date(2026, 8, 25)]
    exit_code, _ = run_main(monkeypatch, targets, [FetchStatus.ERROR, FetchStatus.ERROR])
    assert exit_code == 1


def test_days_without_a_result_yet_are_not_a_failure(monkeypatch):
    targets = [date(2026, 8, 25)]
    exit_code, _ = run_main(monkeypatch, targets, [FetchStatus.NO_DATA])
    assert exit_code == 0
