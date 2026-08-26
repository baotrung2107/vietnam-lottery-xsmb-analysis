import pandas as pd

import alerts
import probability as probability_cycle
from probability import DigitStatus, probability_none

QUIET = DigitStatus(
    digit=5, streak=15, last_seen=pd.Timestamp('2026-08-10').date(), rarity=probability_none(15), unusual=True
)
NORMAL = DigitStatus(digit=8, streak=0, last_seen=pd.Timestamp('2026-08-25').date(), rarity=1.0, unusual=False)
NEVER = DigitStatus(digit=3, streak=4, last_seen=None, rarity=probability_none(4), unusual=False)


def test_table_marks_only_the_unusual_digit():
    table = alerts.format_table([QUIET, NORMAL])
    assert '⚠️' in table.splitlines()[2]
    assert '⚠️' not in table.splitlines()[3]
    assert '10/08/2026' in table


def test_table_handles_a_digit_that_never_appeared():
    assert 'chưa từng' in alerts.format_table([NEVER])


def test_report_names_the_unusual_digit_and_its_streak():
    report = alerts.build_report([QUIET, NORMAL], pd.Timestamp('2026-08-25'))
    assert 'Chữ số 5' in report
    assert '15 kỳ' in report
    assert '25/08/2026' in report


def test_report_says_so_when_nothing_is_unusual():
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'))
    assert 'Không có chữ số nào vượt ngưỡng' in report


def test_report_always_warns_against_reading_it_as_a_prediction():
    """Cảnh báo mô tả quá khứ; nếu bỏ câu này người đọc sẽ hiểu thành 'sắp về'."""
    report = alerts.build_report([QUIET], pd.Timestamp('2026-08-25'))
    assert 'không đổi' in report
    assert 'không nói chữ số đó sắp về' in report
    assert '19%' in report


def test_forecast_table_has_one_row_per_forecast_draw():
    rows = alerts.format_forecast().splitlines()
    assert len(rows) == alerts.FORECAST_DRAWS + 2  # 2 dòng tiêu đề


def test_main_reports_status_and_sets_outputs(monkeypatch, tmp_path, capsys):
    output = tmp_path / 'github_output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)

    assert alerts.main() == 0

    printed = capsys.readouterr().out
    assert 'Tình trạng chữ số' in printed
    for digit in range(10):
        assert f'chữ số {digit}:' in printed

    written = dict(line.split('=', 1) for line in output.read_text(encoding='utf-8').splitlines())
    assert written['alert'] in {'true', 'false'}
    assert written['title'] == alerts.ISSUE_TITLE
    assert (tmp_path / 'gan-alert.md').read_text(encoding='utf-8').startswith('Tính tới kỳ quay')


def test_main_writes_the_step_summary_when_github_provides_one(monkeypatch, tmp_path):
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)

    alerts.main()
    assert 'Tình trạng cả 10 chữ số' in summary.read_text(encoding='utf-8')


def test_load_results_reads_the_published_dataset():
    data = alerts.load_results()
    assert {'date', 'special'} <= set(data.columns)
    assert len(data) > 7000


def test_report_includes_the_prize7_section_when_given_one():
    report = alerts.build_report([QUIET, NORMAL], pd.Timestamp('2026-08-25'), [91, 9, 45, 84], [QUIET, NORMAL])
    assert 'Chữ số của giải bảy kỳ mới nhất' in report
    assert '`91`' in report and '`09`' in report
    assert 'chữ số **5** đang vắng mặt bất thường' in report


def test_report_says_when_no_prize7_digit_is_unusual():
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'), [11, 22, 33, 44], [NORMAL])
    assert 'Không chữ số nào trong giải bảy kỳ này đang vắng mặt bất thường' in report


def test_report_omits_the_prize7_section_when_not_given():
    report = alerts.build_report([QUIET], pd.Timestamp('2026-08-25'))
    assert 'Chữ số của giải bảy' not in report


def test_report_states_that_prize7_carries_no_signal():
    """Không có câu này thì bảng giải bảy sẽ bị đọc thành gợi ý cho giải đặc biệt."""
    report = alerts.build_report([QUIET], pd.Timestamp('2026-08-25'), [91, 9, 45, 84], [QUIET])
    assert 'quay trước giải đặc biệt vài phút' in report
    assert 'bằng đúng mức của một chữ số lấy ngẫu nhiên' in report


def test_main_prints_the_prize7_digits(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    alerts.main()
    assert 'Giải bảy kỳ mới nhất:' in capsys.readouterr().out


def make_cycle(name: str, streak: int, alert_streak: int) -> probability_cycle.CycleStatus:
    return probability_cycle.CycleStatus(
        name=name,
        streak=streak,
        last_hit=pd.Timestamp('2026-08-24').date(),
        hits=2634,
        hit_rate=0.35,
        mean_gap=2.9,
        median_gap=2.0,
        p90_gap=6,
        max_gap=21,
        rarity=0.65**streak,
        alert_streak=alert_streak,
        unusual=streak >= alert_streak,
    )


def test_report_includes_the_cycle_table_when_given_cycles():
    cycles = [make_cycle('Chỉ A', 1, 15), make_cycle('Chỉ B', 2, 15), make_cycle('A hoặc B', 1, 5)]
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'), cycles=cycles)
    assert 'Chu kỳ A, B của giải bảy thứ nhất' in report
    assert '**Chỉ A** | 35.0% | 2634' in report
    assert 'mức báo sớm 5 kỳ' in report


def test_cycle_at_the_threshold_adds_the_warning_and_the_honest_caveat():
    cycles = [make_cycle('A hoặc B', 5, 5)]
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'), cycles=cycles)
    assert 'đã trượt **5 kỳ** liên tiếp — chạm ngưỡng 5 kỳ' in report
    assert 'KHÔNG làm kỳ tới dễ trúng hơn' in report


def test_report_omits_the_cycle_section_when_not_given():
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'))
    assert 'Chu kỳ A, B' not in report


def make_break(kind: str, label: str, missed: int, rarity: float) -> probability_cycle.DroughtBreak:
    return probability_cycle.DroughtBreak(
        kind=kind,
        label=label,
        missed=missed,
        rarity=rarity,
        previous_seen=pd.Timestamp('2026-08-05').date(),
        returned=pd.Timestamp('2026-08-25').date(),
    )


def test_report_lists_the_drought_breaks():
    breaks = [make_break('chữ số', '0', 19, 0.018)]
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'), breaks=breaks)
    assert 'Số khan vừa về kỳ này' in report
    assert 'chữ số **0** ⚠️ | 19 kỳ' in report
    assert 'không làm số vừa về dễ hay khó ra hơn' in report


def test_report_says_when_no_drought_break_happened():
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'), breaks=[])
    assert 'không có số khan nào vừa về' in report


def test_report_omits_the_break_section_when_not_given():
    report = alerts.build_report([NORMAL], pd.Timestamp('2026-08-25'))
    assert 'Số khan vừa về' not in report
