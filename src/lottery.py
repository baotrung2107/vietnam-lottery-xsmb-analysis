__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

import logging
import re
from copy import copy
from datetime import date, timedelta
from enum import StrEnum
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from cloudscraper import CloudScraper
from pydantic import ValidationError
from requests import Response
from requests.exceptions import RequestException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from dtos import Result, ResultList

logger = logging.getLogger(__name__)

# (connect, read) timeout — thiếu hai con số này thì một request treo có thể ghim job tới giới hạn 6 giờ.
REQUEST_TIMEOUT = (10.0, 30.0)

# Số phần tử bắt buộc của từng hạng giải trên trang nguồn. Trang trả thiếu hoặc thừa nghĩa là
# markup đã đổi hoặc đây không phải trang kết quả — không được lặng lẽ lấy vài phần tử đầu.
PRIZE_FIELDS: dict[str, tuple[str, ...]] = {
    'special-prize': ('special',),
    'prize1': ('prize1',),
    'prize2': ('prize2_1', 'prize2_2'),
    'prize3': tuple(f'prize3_{i}' for i in range(1, 7)),
    'prize4': tuple(f'prize4_{i}' for i in range(1, 5)),
    'prize5': tuple(f'prize5_{i}' for i in range(1, 7)),
    'prize6': tuple(f'prize6_{i}' for i in range(1, 4)),
    'prize7': tuple(f'prize7_{i}' for i in range(1, 5)),
}

DATE_PATTERN = re.compile(r'\b(\d{2})[-/](\d{2})[-/](\d{4})\b')


class FetchStatus(StrEnum):
    OK = 'ok'
    NO_DATA = 'no_data'
    ERROR = 'error'


class TransientError(Exception):
    """Lỗi tạm của trang nguồn (5xx, 429) — đáng thử lại."""


class PageNotFound(Exception):
    """Trang không tồn tại (404) — ngày này chưa có/không có kết quả."""


class NoResultYet(Exception):
    """Trang hợp lệ nhưng chưa đăng kết quả cho ngày này."""


class InvalidPage(Exception):
    """Trang trả về nội dung không dùng được: sai ngày, thiếu giải, số không đọc được."""


class Lottery:
    def __init__(self) -> None:
        self._http = CloudScraper()

        self._data: dict[date, Result] = {}
        # Chỉ mục 27-số -> ngày, để bắt trường hợp trang nguồn trả kết quả của ngày khác.
        self._by_prizes: dict[tuple[int, ...], date] = {}

        self._raw_data: pd.DataFrame = pd.DataFrame()
        self._2_digits_data: pd.DataFrame = pd.DataFrame()
        self._sparse_data: pd.DataFrame = pd.DataFrame()

        self._begin_date = date.today()
        self._last_date = date.today()

    def load(self) -> None:
        with open('data/xsmb.json', 'r', encoding='utf-8') as f:
            data = ResultList.model_validate_json(f.read())
        for d in data.root:
            self._data[d.date] = d
        self._rebuild_prize_index()

        for dates in self.find_duplicate_results().values():
            logger.warning('Các ngày sau đang lưu kết quả giống hệt nhau: %s', ', '.join(str(d) for d in dates))

        self.generate_dataframes()

    def dump(self) -> None:
        def _dump(df: pd.DataFrame, file_name: str) -> None:
            df.to_csv(f'data/{file_name}.csv', index=False)
            df.to_json(f'data/{file_name}.json', orient='records', date_format='iso', indent=2, index=False)
            df.to_parquet(f'data/{file_name}.parquet', index=False)

        _dump(self._raw_data, 'xsmb')
        _dump(self._2_digits_data, 'xsmb-2-digits')
        _dump(self._sparse_data, 'xsmb-sparse')

    def fetch(self, selected_date: date) -> FetchStatus:
        url = f'https://xoso.com.vn/xsmb-{selected_date:%d-%m-%Y}.html'

        try:
            resp = self._request(url)
        except PageNotFound:
            logger.info('%s: trang không tồn tại (404)', selected_date)
            return FetchStatus.NO_DATA
        except (TransientError, RequestException) as exc:
            logger.error('%s: không tải được trang - %s', selected_date, exc)
            return FetchStatus.ERROR

        try:
            result = self._parse(resp, selected_date)
        except NoResultYet:
            logger.info('%s: trang chưa có kết quả', selected_date)
            return FetchStatus.NO_DATA
        except (InvalidPage, ValidationError) as exc:
            logger.error('%s: dữ liệu không hợp lệ, bỏ qua - %s', selected_date, exc)
            return FetchStatus.ERROR

        self._store(result)
        logger.info('%s: đã lấy kết quả', selected_date)
        return FetchStatus.OK

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((TransientError, RequestException)),
    )
    def _request(self, url: str) -> Response:
        resp = self._http.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            raise PageNotFound(url)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f'HTTP {resp.status_code}')
        if resp.status_code != 200:
            raise TransientError(f'HTTP {resp.status_code}')
        return resp

    def _parse(self, resp: Response, selected_date: date) -> Result:
        # Cổng 1: trang nguồn có thể chuyển hướng sang kết quả của ngày khác mà vẫn trả HTTP 200.
        expected_path = f'/xsmb-{selected_date:%d-%m-%Y}.html'
        actual_path = urlparse(resp.url).path
        if actual_path != expected_path:
            raise InvalidPage(f'bị chuyển hướng sang {resp.url}')

        soup = BeautifulSoup(resp.text, 'lxml')

        found: dict[str, list[str]] = {
            css_class: [element.text.strip() for element in soup.find_all(attrs={'class': css_class})]
            for css_class in PRIZE_FIELDS
        }
        if not any(found.values()):
            raise NoResultYet(str(selected_date))

        # Cổng 2: ngày in trên trang phải khớp ngày đang xin. Trang không in ngày theo dạng nào
        # nhận ra được thì bỏ qua cổng này thay vì đoán bừa.
        if self._page_shows_other_date(soup, selected_date):
            raise InvalidPage(f'trang không nhắc tới ngày {selected_date:%d-%m-%Y}')

        # Cổng 3: đủ và đúng số lượng phần tử của từng hạng giải.
        wrong = {
            css_class: f'{len(values)}/{len(PRIZE_FIELDS[css_class])}'
            for css_class, values in found.items()
            if len(values) != len(PRIZE_FIELDS[css_class])
        }
        if wrong:
            raise InvalidPage(f'số lượng giải không khớp: {wrong}')

        values: dict[str, int | date] = {'date': selected_date}
        for css_class, texts in found.items():
            for field_name, text in zip(PRIZE_FIELDS[css_class], texts):
                try:
                    values[field_name] = int(text)
                except ValueError:
                    raise InvalidPage(f'{field_name} không phải số: {text!r}') from None

        # Cổng 4: miền giá trị của 27 con số (pydantic Field ge/le trong dtos.py).
        result = Result(**values)

        # Cổng 5: hai ngày không thể trùng nhau cả 27 giải — đây là dấu hiệu trang trả sai ngày.
        clash = self._by_prizes.get(result.prizes())
        if clash is not None and clash != result.date:
            raise InvalidPage(f'kết quả trùng khớp hoàn toàn với ngày {clash}')

        return result

    def _page_shows_other_date(self, soup: BeautifulSoup, selected_date: date) -> bool:
        dates_on_page = set(DATE_PATTERN.findall(soup.get_text(' ')))
        if not dates_on_page:
            return False
        expected = (f'{selected_date.day:02d}', f'{selected_date.month:02d}', f'{selected_date.year:04d}')
        return expected not in dates_on_page

    def _store(self, result: Result) -> None:
        previous = self._data.get(result.date)
        if previous is not None:
            self._by_prizes.pop(previous.prizes(), None)
        self._data[result.date] = result
        self._by_prizes[result.prizes()] = result.date

    def _rebuild_prize_index(self) -> None:
        self._by_prizes = {result.prizes(): result.date for result in self._data.values()}

    def find_duplicate_results(self) -> dict[tuple[int, ...], list[date]]:
        """Các bộ 27 số xuất hiện ở nhiều hơn một ngày — chắc chắn có ngày đang lưu kết quả sai."""
        seen: dict[tuple[int, ...], list[date]] = {}
        for result_date in sorted(self._data):
            seen.setdefault(self._data[result_date].prizes(), []).append(result_date)
        return {prizes: dates for prizes, dates in seen.items() if len(dates) > 1}

    def get_missing_dates(self, until: date, backfill_days: int | None = None) -> list[date]:
        """Mọi ngày chưa có trong kho, tính tới `until`.

        Không có hàm này thì một ngày cào hỏng sẽ bị nhảy qua vĩnh viễn, vì vòng lặp cào chỉ
        biết đi tới từ ngày mới nhất. `backfill_days` giới hạn phạm vi dò ngược tính từ ngày
        mới nhất đang có, để lần chạy hằng ngày không nã lại toàn bộ lịch sử; các ngày sau
        ngày mới nhất luôn được tính đủ dù cửa sổ có hẹp tới đâu.
        """
        if not self._data:
            return []

        last_stored = max(self._data)
        begin = min(self._data)
        if backfill_days is not None:
            begin = max(begin, last_stored - timedelta(days=backfill_days - 1))

        missing = []
        current = begin
        while current <= until:
            if current not in self._data:
                missing.append(current)
            current += timedelta(days=1)
        return missing

    def generate_dataframes(self) -> None:
        # Sắp theo ngày: cào bù chèn ngày cũ vào sau ngày mới, mà mọi thống kê phía sau
        # (delta, iloc[-1], thứ tự dòng trong file xuất) đều giả định dữ liệu theo trình tự thời gian.
        results = [self._data[result_date] for result_date in sorted(self._data)]

        self._raw_data = pd.DataFrame([d.model_dump() for d in results])
        self._raw_data['date'] = pd.to_datetime(self._raw_data['date'])
        self._raw_data.iloc[:, 1:] = self._raw_data.iloc[:, 1:].astype('int64')

        self._2_digits_data = copy(self._raw_data)
        self._2_digits_data.iloc[:, 1:] = self._2_digits_data.iloc[:, 1:].apply(lambda x: x % 100)

        self._sparse_data = pd.concat(
            [
                self._2_digits_data.iloc[:, 0:1],
                pd.DataFrame(np.zeros((self._2_digits_data.shape[0], 100), dtype=int)),
            ],
            axis=1,
        )
        self._sparse_data.iloc[:, 1:] = self._sparse_data.iloc[:, 1:].astype('int64')
        for i in range(self._2_digits_data.shape[0]):
            counts = self._2_digits_data.iloc[i, 1:].value_counts()
            for k, v in counts.items():
                self._sparse_data.iloc[i, k + 1] = int(v)

        begin_date = self._raw_data['date'].min()
        self._begin_date = begin_date.to_pydatetime().date()
        last_date = self._raw_data['date'].max()
        self._last_date = last_date.to_pydatetime().date()

    def get_raw_data(self) -> pd.DataFrame:
        return self._raw_data

    def get_2_digits_data(self) -> pd.DataFrame:
        return self._2_digits_data

    def get_sparse_data(self) -> pd.DataFrame:
        return self._sparse_data

    def get_last_date(self) -> date:
        return self._last_date
