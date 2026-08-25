from dataclasses import dataclass, field
from datetime import date

import pytest
from requests.exceptions import ConnectionError
from tenacity import wait_none

from lottery import REQUEST_TIMEOUT, FetchStatus, InvalidPage, Lottery, NoResultYet, PageNotFound, TransientError
from tests.pages import SELECTED, build_page

# Bỏ thời gian chờ giữa các lần thử lại, nếu không mỗi test retry mất vài giây.
request_without_waiting = Lottery._request.retry_with(wait=wait_none())


@dataclass
class FakeSession:
    status_code: int = 200
    raises: Exception | None = None
    calls: list[dict] = field(default_factory=list)

    def get(self, url, timeout=None):
        self.calls.append({'url': url, 'timeout': timeout})
        if self.raises is not None:
            raise self.raises
        return FakeHttpResponse(url=url, status_code=self.status_code, text=build_page())


@dataclass
class FakeHttpResponse:
    url: str
    status_code: int
    text: str


def lottery_with_session(session: FakeSession) -> Lottery:
    lottery = Lottery()
    lottery._http = session
    return lottery


def test_request_always_passes_a_timeout():
    """Không có timeout thì một request treo có thể ghim job Actions tới giới hạn 6 giờ."""
    session = FakeSession()
    request_without_waiting(lottery_with_session(session), 'https://xoso.com.vn/x.html')
    assert session.calls[0]['timeout'] == REQUEST_TIMEOUT


def test_missing_page_is_not_retried():
    session = FakeSession(status_code=404)
    with pytest.raises(PageNotFound):
        request_without_waiting(lottery_with_session(session), 'https://xoso.com.vn/x.html')
    assert len(session.calls) == 1


@pytest.mark.parametrize('status_code', [429, 500, 503])
def test_transient_failures_are_retried_three_times(status_code):
    session = FakeSession(status_code=status_code)
    with pytest.raises(TransientError):
        request_without_waiting(lottery_with_session(session), 'https://xoso.com.vn/x.html')
    assert len(session.calls) == 3


def test_network_errors_are_retried_three_times():
    session = FakeSession(raises=ConnectionError('mất mạng'))
    with pytest.raises(ConnectionError):
        request_without_waiting(lottery_with_session(session), 'https://xoso.com.vn/x.html')
    assert len(session.calls) == 3


def test_fetch_reports_ok_and_stores_the_result():
    lottery = Lottery()
    lottery._request = lambda url: FakeHttpResponse(
        url=f'https://xoso.com.vn/xsmb-{SELECTED:%d-%m-%Y}.html', status_code=200, text=build_page()
    )
    assert lottery.fetch(SELECTED) is FetchStatus.OK
    assert lottery._data[SELECTED].special == 12345


def raising(exception):
    def _raise(*args):
        raise exception

    return _raise


@pytest.mark.parametrize(
    ('exception', 'expected'),
    [
        (PageNotFound('x'), FetchStatus.NO_DATA),
        (NoResultYet('x'), FetchStatus.NO_DATA),
        (TransientError('HTTP 503'), FetchStatus.ERROR),
        (ConnectionError('mất mạng'), FetchStatus.ERROR),
        (InvalidPage('sai ngày'), FetchStatus.ERROR),
    ],
)
def test_fetch_maps_every_failure_to_a_status_instead_of_crashing(exception, expected):
    """Trước đây lỗi parse ném thẳng ra ngoài và làm đỏ cả job; giờ phải thành trạng thái đọc được."""
    lottery = Lottery()
    lottery._request = raising(exception)
    if isinstance(exception, (NoResultYet, InvalidPage)):
        lottery._request = lambda url: FakeHttpResponse(url=url, status_code=200, text=build_page())
        lottery._parse = raising(exception)

    assert lottery.fetch(date(2026, 8, 25)) is expected
    assert date(2026, 8, 25) not in lottery._data
