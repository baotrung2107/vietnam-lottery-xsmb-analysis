__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

import os
import re
import subprocess

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from lottery import Lottery
from probability import DIGIT_HIT_PROBABILITY, all_digit_statuses, expected_wait, forecast
from templates import Render

# Số kỳ tới hiển thị trong bảng dự báo của README.
FORECAST_DRAWS = 7

# Kho dùng khi không đoán được kho đang chạy (chạy tay ngoài git, hoặc remote không phải GitHub).
DEFAULT_REPO = 'khiemdoan/vietnam-lottery-xsmb-analysis'
GITHUB_REMOTE_PATTERN = re.compile(r'github\.com[:/](?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$')


def detect_repo() -> str:
    """Kho GitHub đang chạy, để README sinh ra trỏ link data về chính kho này thay vì kho gốc."""
    repo = os.environ.get('GITHUB_REPOSITORY')
    if repo:
        return repo

    try:
        completed = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True)
    except OSError:
        return DEFAULT_REPO
    if completed.returncode != 0:
        return DEFAULT_REPO

    matched = GITHUB_REMOTE_PATTERN.search(completed.stdout.strip())
    return matched['repo'] if matched else DEFAULT_REPO


def window_start(last_date: pd.Timestamp, years: int) -> pd.Timestamp:
    """Mốc đầu cửa sổ thời gian tính lùi từ `last_date`.

    Dùng DateOffset thay vì dựng thẳng pd.Timestamp(year=last_date.year - years, ...): ngày 29/02
    không tồn tại ở năm thường, nên cách dựng thẳng ném ValueError đúng vào mỗi ngày nhuận.
    """
    return last_date - pd.DateOffset(years=years)


def colors_from_values(values, palette_name):
    low, high = min(values), max(values)
    # Mọi giá trị bằng nhau thì không có gì để chuẩn hoá — chia cho 0 sẽ cho NaN và làm hỏng astype.
    normalized = np.zeros(len(values)) if high == low else np.asarray((values - low) / (high - low))
    indices = np.round(normalized * (len(values) - 1)).astype(np.int32)
    palette = sns.color_palette(palette_name, len(values))
    return np.array(palette).take(indices, axis=0)


def last_appearing(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Số kỳ quay tính từ lần xuất hiện gần nhất của từng số 00-99, tới kỳ dự đoán kế tiếp.

    Tính trên toàn bộ lịch sử được truyền vào. Nếu cắt cửa sổ thời gian trước khi tính thì số nào
    vắng mặt suốt cửa sổ sẽ rơi khỏi groupby, pivot tạo ô rỗng và fillna(0) biến nó thành delta=0
    — tức số gan nhất lại hiện lên như số vừa về, đồng thời bị loại khỏi biểu đồ Top 10.
    """
    numbers = data[columns].reset_index(drop=True).reset_index()
    predict_index = numbers['index'].max() + 1

    numbers = numbers.melt(id_vars='index', var_name='prize', value_name='value')
    numbers['value'] = numbers['value'] % 100

    # reindex giữ đủ 100 số kể cả số chưa từng xuất hiện; số đó nhận delta lớn hơn mọi delta thật.
    appearing = numbers.groupby(['value'])['index'].max().reindex(range(100))
    appearing.index.name = 'value'

    result = appearing.to_frame()
    result['delta'] = (predict_index - result['index']).fillna(predict_index + 1).astype(int)
    return result.drop('index', axis=1)


def plot_last_appearing(data: pd.DataFrame, columns: list[str], heatmap_file: str, top_10_file: str) -> None:
    deltas = last_appearing(data, columns)

    heatmap_data = deltas.copy()
    heatmap_data['tens'] = heatmap_data.index // 10
    heatmap_data['ones'] = heatmap_data.index % 10
    heatmap_data = heatmap_data[['tens', 'ones', 'delta']]
    heatmap_data = heatmap_data.pivot(index='tens', columns='ones', values='delta')
    heatmap_data = heatmap_data.astype(int)

    bar_data = deltas.sort_values('delta', ascending=False)
    bar_data = bar_data.iloc[:10, :]
    bar_data.reset_index(inplace=True)
    bar_data['value'] = bar_data['value'].apply(lambda r: f'{r:02d}')

    fig, ax = plt.subplots()
    sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='RdYlGn', ax=ax)
    ax.set_title('Delta')
    fig.savefig(heatmap_file)
    plt.close(fig)

    fig, ax = plt.subplots()
    palette = reversed(colors_from_values(bar_data['delta'], 'summer'))
    sns.barplot(bar_data, x='value', y='delta', hue='value', palette=palette, ax=ax)
    for bar in ax.containers:
        ax.bar_label(bar, fmt='%d')
    ax.set_title('Top 10')
    fig.savefig(top_10_file)
    plt.close(fig)


if __name__ == '__main__':
    lottery = Lottery()
    lottery.load()

    results = lottery.get_raw_data()
    sparse_results = lottery.get_sparse_data()

    prize_columns = [column for column in results.columns if column != 'date']

    # Last appearing Special price
    plot_last_appearing(results, ['special'], 'images/special_delta.jpg', 'images/special_delta_top_10.jpg')

    latest_result = results.iloc[-1]
    recent_results = latest_result.values[1:] % 100
    loto_result = []
    for i in range(10):
        category = sorted([d for d in recent_results if d // 10 == i])
        category = [f'{d % 10:1d}' for d in category]
        category = ', '.join(category) if len(category) > 0 else '-'
        loto_result.append(category)

    last_date = sparse_results['date'].max()

    start_date = window_start(last_date, 1)
    sparse_results_1_year = sparse_results[
        (start_date < sparse_results['date']) & (sparse_results['date'] <= last_date)
    ]
    sparse_results_1_year.reset_index(drop=True, inplace=True)

    sparse_results_1_year = sparse_results_1_year.drop(columns=['date'])
    counts = sparse_results_1_year.sum(axis=0)

    max_count = counts.max().round(2)
    min_count = counts.min().round(2)
    mean = counts.mean().round(2)
    std = counts.std().round(2)

    render = Render()
    context = {
        'repo': detect_repo(),
        'digit_statuses': all_digit_statuses(results),
        'digit_forecast': forecast(FORECAST_DRAWS),
        'hit_probability': DIGIT_HIT_PROBABILITY,
        'expected_wait': expected_wait(),
        'loto_result': loto_result,
        'max_count': max_count,
        'min_count': min_count,
        'mean': mean,
        'std': std,
        **latest_result,
    }
    content = render('README.j2', context)
    with open('README.md', 'w', encoding='utf-8') as outfile:
        outfile.write(content)

    counts = counts.reset_index()
    counts.columns = ['value', 'freq']
    counts = counts.astype({'value': int})
    counts.sort_values('freq', ascending=False, inplace=True)

    # Detail plot

    heatmap_data = counts.copy()
    heatmap_data['tens'] = heatmap_data['value'] // 10
    heatmap_data['ones'] = heatmap_data['value'] % 10
    heatmap_data = heatmap_data[['tens', 'ones', 'freq']]
    heatmap_data = heatmap_data.pivot(index='tens', columns='ones', values='freq').fillna(0)
    heatmap_data = heatmap_data.astype(int)

    fig, ax = plt.subplots()
    sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='RdYlGn', ax=ax)
    ax.set_title('Detail')
    fig.savefig('images/heatmap.jpg')

    # Top 10 plot

    bar_data = counts[:10].copy()
    bar_data['value'] = bar_data['value'].apply(lambda r: f'{r:02d}')

    fig, ax = plt.subplots()
    palette = reversed(colors_from_values(bar_data['freq'], 'summer'))
    sns.barplot(bar_data, x='value', y='freq', hue='value', palette=palette, ax=ax)
    for bar in ax.containers:
        ax.bar_label(bar, fmt='%d')
    ax.set_title('Top 10')
    fig.savefig('images/top-10.jpg')

    # Distribution

    data = counts[['freq']].copy()
    bins = data.max().iloc[0] - data.min().iloc[0] + 1

    fig, ax = plt.subplots()
    sns.histplot(data, kde=True, bins=bins, fill=False, ax=ax)
    kdeline = ax.lines[0]
    xs = kdeline.get_xdata()
    ys = kdeline.get_ydata()
    ax.vlines(mean, 0, np.interp(mean, xs, ys), color='red', linestyles='solid')
    ax.vlines(mean - std, 0, np.interp(mean - std, xs, ys), color='red', linestyles='dashed')
    ax.vlines(mean + std, 0, np.interp(mean + std, xs, ys), color='red', linestyles='dashed')
    ax.vlines(mean - 2 * std, 0, np.interp(mean - 2 * std, xs, ys), color='red', linestyles='dotted')
    ax.vlines(mean + 2 * std, 0, np.interp(mean + 2 * std, xs, ys), color='red', linestyles='dotted')
    ax.set_title('Distribution')
    fig.savefig('images/distribution.jpg')

    # Last appearing Loto
    plot_last_appearing(results, prize_columns, 'images/delta.jpg', 'images/delta_top_10.jpg')
