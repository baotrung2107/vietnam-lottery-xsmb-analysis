import pandas as pd
import pytest

import probability


def draws(specials: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            'date': pd.date_range('2026-01-01', periods=len(specials), freq='D'),
            'special': specials,
        }
    )


# --- đếm số thoả điều kiện ---


def test_each_digit_is_in_exactly_19_numbers():
    """10 số hàng chục + 10 số hàng đơn vị, trừ số bị đếm hai lần (55, 77...) — nên 19 chứ không 20."""
    for digit in range(10):
        assert len(probability.numbers_containing(digit)) == 19


def test_numbers_containing_five_lists_the_right_numbers():
    assert probability.numbers_containing(5) == [
        5,
        15,
        25,
        35,
        45,
        50,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        58,
        59,
        65,
        75,
        85,
        95,
    ]


def test_hit_probability_matches_the_default():
    assert probability.hit_probability(probability.numbers_containing(7)) == pytest.approx(
        probability.DIGIT_HIT_PROBABILITY
    )


def test_digit_outside_zero_to_nine_is_rejected():
    with pytest.raises(ValueError):
        probability.numbers_containing(10)


# --- công thức cơ bản ---


def test_zero_draws_never_hits():
    assert probability.probability_none(0) == 1.0
    assert probability.probability_at_least_once(0) == 0.0


def test_seven_draws_matches_the_published_numbers():
    assert probability.probability_none(7) == pytest.approx(0.2288, abs=1e-4)
    assert probability.probability_at_least_once(7) == pytest.approx(0.7712, abs=1e-4)


def test_first_hit_on_the_first_draw_is_the_base_probability():
    assert probability.probability_first_hit_on(1) == pytest.approx(probability.DIGIT_HIT_PROBABILITY)


def test_first_hit_probabilities_add_up_to_the_cumulative_one():
    total = sum(probability.probability_first_hit_on(draw) for draw in range(1, 15))
    assert total == pytest.approx(probability.probability_at_least_once(14))


def test_expected_wait_is_one_over_the_probability():
    assert probability.expected_wait() == pytest.approx(1 / 0.19)


@pytest.mark.parametrize('bad', [-1, -7])
def test_negative_draws_are_rejected(bad):
    with pytest.raises(ValueError):
        probability.probability_none(bad)


def test_first_hit_before_the_first_draw_is_rejected():
    with pytest.raises(ValueError):
        probability.probability_first_hit_on(0)


# --- điểm mấu chốt: kỳ đã trượt không được cộng vào số mũ ---


def test_only_future_draws_count_toward_the_exponent():
    """Đang trượt 20 kỳ mà muốn biết khả năng trượt tới kỳ 30 thì số mũ là 10, không phải 30."""
    wrong = probability.probability_none(30)
    right = probability.probability_none(10)
    assert right == pytest.approx(0.1216, abs=1e-4)
    assert wrong == pytest.approx(0.0018, abs=1e-4)
    assert right / wrong > 60


def test_the_streak_has_no_memory():
    """P(trượt thêm m kỳ) như nhau dù đang ở đầu chuỗi hay đã trượt rất lâu."""
    for already in [0, 7, 14, 20, 30]:
        conditional = probability.probability_none(already + 10) / probability.probability_none(already)
        assert conditional == pytest.approx(probability.probability_none(10))


# --- tình trạng từng chữ số ---


def test_digit_status_counts_the_current_streak():
    # 57 có chữ số 5, ba kỳ sau đó thì không
    data = draws([57, 80, 41, 22])
    status = probability.digit_status(data, 5)
    assert status.streak == 3
    assert status.last_seen == pd.Timestamp('2026-01-01').date()
    assert status.rarity == pytest.approx(probability.probability_none(3))


def test_digit_present_in_the_latest_draw_has_zero_streak():
    status = probability.digit_status(draws([80, 57]), 5)
    assert status.streak == 0
    assert status.rarity == 1.0
    assert not status.unusual


def test_digit_never_drawn_has_no_last_seen():
    status = probability.digit_status(draws([12, 34, 12]), 9)
    assert status.streak == 3
    assert status.last_seen is None


def test_long_streak_is_flagged_unusual():
    quiet = probability.digit_status(draws([57] + [80] * 15), 5)
    assert quiet.streak == 15
    assert quiet.rarity < 0.05
    assert quiet.unusual


def test_streak_just_below_the_threshold_is_not_flagged():
    status = probability.digit_status(draws([57] + [80] * 14), 5)
    assert status.streak == 14
    assert not status.unusual


def test_all_digit_statuses_covers_ten_digits_longest_first():
    statuses = probability.all_digit_statuses(draws([57, 80, 41, 22]))
    assert len(statuses) == 10
    assert sorted(status.digit for status in statuses) == list(range(10))

    streaks = [status.streak for status in statuses]
    assert streaks == sorted(streaks, reverse=True)


def test_statuses_on_the_real_dataset_are_consistent():
    data = pd.read_csv('data/xsmb.csv', parse_dates=['date'])
    statuses = probability.all_digit_statuses(data)
    assert len(statuses) == 10
    for status in statuses:
        assert status.streak >= 0
        assert status.rarity == pytest.approx(probability.probability_none(status.streak))
        assert status.unusual == (status.rarity < 0.05)


# --- bảng dự báo ---


def test_forecast_grows_toward_certainty_but_never_reaches_it():
    table = probability.forecast(7)
    assert len(table) == 7
    cumulative = [row[2] for row in table]
    assert cumulative == sorted(cumulative)
    assert cumulative[-1] == pytest.approx(0.7712, abs=1e-4)
    assert cumulative[-1] < 1


def test_forecast_first_hit_column_shrinks_every_draw():
    first = [row[1] for row in probability.forecast(10)]
    assert first == sorted(first, reverse=True)


# --- chữ số của giải bảy ---


def draws_with_prize7(specials: list[int], prize7: list[list[int]]) -> pd.DataFrame:
    data = {
        'date': pd.date_range('2026-01-01', periods=len(specials), freq='D'),
        'special': specials,
    }
    for position in range(1, 5):
        data[f'prize7_{position}'] = [row[position - 1] for row in prize7]
    return pd.DataFrame(data)


def test_distinct_digits_deduplicates_and_sorts():
    assert probability.distinct_digits([91, 9, 45, 84]) == [0, 1, 4, 5, 8, 9]
    assert probability.distinct_digits([55, 55]) == [5]


def test_latest_prize7_reads_the_newest_draw():
    data = draws_with_prize7([12, 80], [[11, 22, 33, 44], [91, 9, 45, 84]])
    assert probability.latest_prize7(data) == [91, 9, 45, 84]


def test_prize7_digit_statuses_covers_every_digit_of_the_latest_draw():
    data = draws_with_prize7([57, 80, 41, 22], [[11, 22, 33, 44]] * 3 + [[91, 9, 45, 84]])
    numbers, statuses = probability.prize7_digit_statuses(data)

    assert numbers == [91, 9, 45, 84]
    assert [status.digit for status in statuses] == sorted(
        [s.digit for s in statuses], key=lambda d: -next(s.streak for s in statuses if s.digit == d)
    )
    assert sorted(status.digit for status in statuses) == [0, 1, 4, 5, 8, 9]


def test_prize7_statuses_are_sorted_longest_streak_first():
    data = draws_with_prize7([57, 80, 41, 22], [[11, 22, 33, 44]] * 3 + [[91, 9, 45, 84]])
    _, statuses = probability.prize7_digit_statuses(data)
    streaks = [status.streak for status in statuses]
    assert streaks == sorted(streaks, reverse=True)


def test_prize7_digit_streak_is_measured_against_the_special_tail_not_prize7():
    """Chữ số 5 nằm trong giải bảy kỳ này, nhưng chuỗi vắng đếm trên 2 số cuối giải đặc biệt."""
    data = draws_with_prize7([57, 80, 41, 22], [[11, 22, 33, 44]] * 3 + [[91, 9, 45, 84]])
    _, statuses = probability.prize7_digit_statuses(data)
    five = next(status for status in statuses if status.digit == 5)
    assert five.streak == 3
    assert five.last_seen == pd.Timestamp('2026-01-01').date()


# --- chu kỳ A, B của giải bảy thứ nhất ---


def test_a_and_b_hits_check_each_digit_separately():
    data = draws_with_prize7(
        [17, 80, 91, 55],
        [[19, 85, 40, 71], [91, 9, 45, 84], [19, 85, 40, 71], [23, 85, 40, 71]],
    )
    # 17: G7=19 -> A=1 trúng, B=9 trượt | 80: G7=91 -> A=9 trượt, B=1 trượt
    # 91: G7=19 -> A=1 trúng, B=9 trúng | 55: G7=23 -> A=2 trượt, B=3 trượt
    assert probability.prize7_a_hits(data).tolist() == [True, False, True, False]
    assert probability.prize7_b_hits(data).tolist() == [False, False, True, False]
    assert probability.prize7_ab_hits(data).tolist() == [True, False, True, False]


def test_cycle_counts_the_current_miss_streak():
    data = draws_with_prize7([17, 80, 55], [[19, 85, 40, 71]] * 3)
    cycle = probability.prize7_ab_cycle(data, hit_rate=0.35)
    assert cycle.streak == 2
    assert cycle.last_hit == pd.Timestamp('2026-01-01').date()
    assert cycle.rarity == pytest.approx(0.65**2)
    assert not cycle.unusual


def test_ab_cycle_alerts_early_at_five_misses():
    """Người dùng chọn báo sớm: A hoặc B trượt 5 kỳ là kêu, dù độ hiếm mới ~11,6%."""
    specials = [17] + [80] * 5
    data = draws_with_prize7(specials, [[19, 85, 40, 71]] * len(specials))
    cycle = probability.prize7_ab_cycle(data, hit_rate=0.35)
    assert cycle.alert_streak == 5
    assert cycle.streak == 5
    assert cycle.unusual


def test_ab_cycle_stays_quiet_at_four_misses():
    specials = [17] + [80] * 4
    data = draws_with_prize7(specials, [[19, 85, 40, 71]] * len(specials))
    assert not probability.prize7_ab_cycle(data, hit_rate=0.35).unusual


def test_single_digit_cycles_keep_the_rarity_threshold():
    """A và B riêng lẻ (19%/kỳ) vẫn theo mức hiếm 5% -> 15 kỳ, không ăn theo ngưỡng báo sớm 5."""
    data = draws_with_prize7([17, 80], [[19, 85, 40, 71]] * 2)
    assert probability.prize7_a_cycle(data, hit_rate=0.19).alert_streak == 15
    assert probability.prize7_b_cycle(data, hit_rate=0.19).alert_streak == 15
    assert probability.default_alert_streak(0.19) == 15
    assert 0.81**15 < 0.05 <= 0.81**14


def test_prize7_cycles_returns_a_b_then_combined():
    data = draws_with_prize7([17, 80], [[19, 85, 40, 71]] * 2)
    names = [cycle.name for cycle in probability.prize7_cycles(data)]
    assert names == ['Chỉ A', 'Chỉ B', 'A hoặc B']


def test_cycles_on_the_real_dataset_match_the_known_rhythm():
    data = pd.read_csv('data/xsmb.csv', parse_dates=['date'])
    a, b, ab = probability.prize7_cycles(data)

    assert ab.hit_rate == pytest.approx(0.35, abs=0.02)
    assert ab.mean_gap == pytest.approx(2.86, abs=0.1)
    assert ab.alert_streak == 5

    for single in (a, b):
        assert single.hit_rate == pytest.approx(0.19, abs=0.01)
        assert single.mean_gap == pytest.approx(5.2, abs=0.2)
        assert single.alert_streak == 15
        assert single.hits == pytest.approx(1448, abs=5)
    assert a.hits + b.hits >= ab.hits  # A và B có thể cùng trúng một kỳ, biến cố gộp chỉ đếm 1
