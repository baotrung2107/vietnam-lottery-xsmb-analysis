__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

import argparse
import logging
import os
import sys
from datetime import date, datetime, time, timedelta
from time import sleep
from zoneinfo import ZoneInfo

from lottery import FetchStatus, Lottery

logger = logging.getLogger('fetch')

TIMEZONE = ZoneInfo('Asia/Ho_Chi_Minh')
RESULT_TIME = time(18, 35)

# Dò ngược bao nhiêu ngày để cào bù trong lần chạy hằng ngày. Đủ rộng để một ngày hỏng tạm
# thời được thử lại nhiều lần, đủ hẹp để không nã lại toàn bộ lịch sử mỗi ngày.
DEFAULT_BACKFILL_DAYS = 30

# Nghỉ giữa hai request để không dội vào trang nguồn khi cào bù nhiều ngày.
DEFAULT_DELAY = 1.0

# Lưu tạm sau mỗi bấy nhiêu ngày cào được, để một lần cào dài bị gãy giữa chừng không mất trắng.
CHECKPOINT_EVERY = 100


def annotate(level: str, message: str) -> None:
    """In chú thích để GitHub Actions hiện cảnh báo trên giao diện, thay vì hỏng mà im lặng."""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print(f'::{level}::{message}')


def latest_expected_date(now: datetime) -> date:
    last_date = now.date()
    if now.time() < RESULT_TIME:
        last_date -= timedelta(days=1)
    return last_date


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Cào các kỳ XSMB còn thiếu rồi xuất lại toàn bộ file dữ liệu.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--backfill-days',
        type=int,
        default=DEFAULT_BACKFILL_DAYS,
        metavar='N',
        help=f'dò ngược N ngày để cào bù các ngày còn thiếu (mặc định: {DEFAULT_BACKFILL_DAYS})',
    )
    group.add_argument(
        '--backfill-all',
        action='store_true',
        help='dò lại toàn bộ lịch sử để cào bù mọi ngày còn thiếu (chạy tay, rất lâu)',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=DEFAULT_DELAY,
        metavar='GIÂY',
        help=f'nghỉ giữa hai request (mặc định: {DEFAULT_DELAY})',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    lottery = Lottery()
    lottery.load()

    until = latest_expected_date(datetime.now(TIMEZONE))
    backfill_days = None if args.backfill_all else args.backfill_days
    targets = lottery.get_missing_dates(until, backfill_days)

    if not targets:
        logger.info('Không có ngày nào cần cào (tính tới %s)', until)
        return 0

    logger.info('Cần cào %d ngày, từ %s tới %s', len(targets), targets[0], targets[-1])

    counts = dict.fromkeys(FetchStatus, 0)
    since_checkpoint = 0

    for index, selected_date in enumerate(targets):
        if index:
            sleep(args.delay)
        status = lottery.fetch(selected_date)
        counts[status] += 1

        if status is not FetchStatus.OK:
            continue
        since_checkpoint += 1
        if since_checkpoint >= CHECKPOINT_EVERY and len(targets) > CHECKPOINT_EVERY:
            logger.info('Lưu tạm sau %d ngày cào được', since_checkpoint)
            lottery.generate_dataframes()
            lottery.dump()
            since_checkpoint = 0

    lottery.generate_dataframes()
    lottery.dump()

    logger.info(
        'Tổng kết: lấy được %d, chưa có kết quả %d, lỗi %d (trên %d ngày cần cào)',
        counts[FetchStatus.OK],
        counts[FetchStatus.NO_DATA],
        counts[FetchStatus.ERROR],
        len(targets),
    )

    errors = counts[FetchStatus.ERROR]
    if errors:
        message = f'{errors}/{len(targets)} ngày cào lỗi — xem log để biết ngày nào'
        # Mọi ngày đều lỗi nghĩa là hỏng có hệ thống (bị chặn, đổi markup), phải báo đỏ.
        if counts[FetchStatus.OK] == 0 and counts[FetchStatus.NO_DATA] == 0:
            annotate('error', message)
            logger.error('Không cào được ngày nào — nhiều khả năng trang nguồn đã chặn hoặc đổi cấu trúc')
            return 1
        annotate('warning', message)

    return 0


if __name__ == '__main__':
    sys.exit(main())
