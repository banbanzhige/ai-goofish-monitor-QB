import unittest

from src.scraper import _build_extra_headers, _capture_new_request_response


class _FakeRequest:
    def __init__(self, url, response):
        self.url = url
        self._response = response

    async def response(self):
        return self._response


class _FakeRequestInfo:
    def __init__(self, page):
        self._page = page

    @property
    async def value(self):
        return self._page.captured_request


class _FakeExpectRequest:
    def __init__(self, page, predicate):
        self._page = page
        self._predicate = predicate

    async def __aenter__(self):
        self._page.active_predicate = self._predicate
        return _FakeRequestInfo(self._page)

    async def __aexit__(self, exc_type, exc, traceback):
        self._page.active_predicate = None


class _FakePage:
    def __init__(self):
        self.active_predicate = None
        self.captured_request = None

    def expect_request(self, predicate, timeout):
        return _FakeExpectRequest(self, predicate)

    def emit_request(self, request):
        if self.active_predicate and self.active_predicate(request):
            self.captured_request = request


class ScraperRequestBindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_response_bound_to_new_submit_request(self):
        page = _FakePage()
        stale_response = object()
        submitted_response = object()

        async def submit_action():
            # 旧请求的 response 即使此时到达，也没有新的 request 事件，不能被选中。
            _ = stale_response
            page.emit_request(_FakeRequest("https://example.test/search-api", submitted_response))

        actual = await _capture_new_request_response(
            page,
            "search-api",
            submit_action,
        )

        self.assertIs(actual, submitted_response)

    async def test_ignores_unrelated_new_requests(self):
        page = _FakePage()
        submitted_response = object()

        async def submit_action():
            page.emit_request(_FakeRequest("https://example.test/analytics", object()))
            page.emit_request(_FakeRequest("https://example.test/search-api", submitted_response))

        actual = await _capture_new_request_response(page, "search-api", submit_action)

        self.assertIs(actual, submitted_response)

    def test_final_header_boundary_removes_browser_managed_headers(self):
        headers = _build_extra_headers(
            {
                "Host": "wrong.test",
                "Sec-Fetch-Site": "same-origin",
                "sec-fetch-mode": "navigate",
                "Cookie": "secret",
                "X-Test": "ok",
            }
        )

        self.assertEqual(headers, {"X-Test": "ok"})


if __name__ == "__main__":
    unittest.main()
