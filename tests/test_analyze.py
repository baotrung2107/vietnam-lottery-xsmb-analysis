import pandas as pd
import pytest

import analyze


def make_history(rows: int = 1000) -> pd.DataFrame:
    """Chuỗi kỳ quay trong đó số 99 chỉ về đúng một lần ở kỳ thứ 4 rồi biến mất."""
    specials = [index % 99 for index in range(rows)]
    specials[3] = 99
    return pd.DataFrame(
        {
            'date': pd.date_range('2020-01-01', periods=rows, freq='D'),
            'special': specials,
        }
    )


def test_number_absent_for_years_keeps_its_real_delta():
    """Lỗi cũ: số vắng khỏi cửa sổ rơi khỏi groupby, fillna(0) biến nó thành 'vừa về'."""
    deltas = analyze.last_appearing(make_history(), ['special'])

    assert len(deltas) == 100
    assert deltas.loc[99, 'delta'] == 997
    assert deltas['delta'].idxmax() == 99


def test_number_absent_for_years_leads_the_top_10():
    deltas = analyze.last_appearing(make_history(), ['special'])
    top_10 = deltas.sort_values('delta', ascending=False).head(10)
    assert top_10.index[0] == 99


def test_number_never_drawn_gets_the_largest_delta():
    history = make_history()
    history['special'] = [index % 99 for index in range(len(history))]  # 99 không bao giờ về

    deltas = analyze.last_appearing(history, ['special'])
    assert deltas.loc[99, 'delta'] == len(history) + 1
    assert deltas['delta'].idxmax() == 99


def test_delta_matches_the_previous_formula_when_every_number_is_present():
    """Dữ liệu thật hôm nay đủ 100 số, nên kết quả phải khớp từng số với cách tính cũ."""
    data = pd.read_csv('data/xsmb.csv', parse_dates=['date'])

    numbers = data[['special']].reset_index(drop=True).reset_index()
    predict_index = numbers['index'].max() + 1
    melted = numbers.melt(id_vars='index', var_name='prize', value_name='value')
    melted['value'] = melted['value'] % 100
    legacy = predict_index - melted.groupby(['value'])['index'].max()

    current = analyze.last_appearing(data, ['special'])['delta']
    assert len(legacy) == 100
    assert current.reindex(legacy.index).equals(legacy.astype(int))


def test_plot_last_appearing_writes_both_images(tmp_path):
    heatmap = tmp_path / 'delta.jpg'
    top_10 = tmp_path / 'delta_top_10.jpg'
    analyze.plot_last_appearing(make_history(), ['special'], str(heatmap), str(top_10))

    assert heatmap.stat().st_size > 0
    assert top_10.stat().st_size > 0


def test_window_start_survives_the_leap_day():
    leap_day = pd.Timestamp('2028-02-29')
    assert analyze.window_start(leap_day, 1) == pd.Timestamp('2027-02-28')
    assert analyze.window_start(leap_day, 2) == pd.Timestamp('2026-02-28')

    with pytest.raises(ValueError):
        pd.Timestamp(year=leap_day.year - 1, month=leap_day.month, day=leap_day.day)


def test_colors_from_values_handles_a_flat_series():
    colors = analyze.colors_from_values(pd.Series([5, 5, 5, 5]), 'summer')
    assert colors.shape == (4, 3)


def test_detect_repo_prefers_the_github_environment(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'baotrung/xsmb')
    assert analyze.detect_repo() == 'baotrung/xsmb'


def test_detect_repo_falls_back_to_the_git_remote(monkeypatch):
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)
    assert '/' in analyze.detect_repo()


@pytest.mark.parametrize(
    ('remote', 'expected'),
    [
        ('https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis.git', 'khiemdoan/vietnam-lottery-xsmb-analysis'),
        ('https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis', 'khiemdoan/vietnam-lottery-xsmb-analysis'),
        ('git@github.com:baotrung/xsmb.git', 'baotrung/xsmb'),
    ],
)
def test_github_remote_pattern_reads_owner_and_name(remote, expected):
    assert analyze.GITHUB_REMOTE_PATTERN.search(remote)['repo'] == expected
