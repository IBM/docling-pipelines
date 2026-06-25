import unittest
from unittest.mock import call, patch

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.retry import retry_with_exponential_backoff


class RetriableException(Exception):
    pass


class TestRetryWithExponentialBackoff(unittest.TestCase):
    @staticmethod
    def should_retry_on_exception(result, exception):
        return isinstance(exception, RetriableException), "Use Exception message"

    @patch("time.sleep", return_value=None)
    def test_retries_then_fails_on_exception(self, mock_sleep):
        call_count = 0

        @retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=1,
            max_delay=5,
            retry_logic=self.should_retry_on_exception,
        )
        def flaky_function():
            nonlocal call_count
            call_count += 1
            raise RetriableException({"errorType": "TEMPORARY", "message": "Temporary failure"})

        with self.assertRaises(RetriableException):
            flaky_function()

        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1), call(2)])  # delay doubles until max_retries is hit

    @patch("time.sleep", return_value=None)
    def test_eventually_succeeds_on_exception(self, mock_sleep):
        call_count = 0

        @retry_with_exponential_backoff(
            max_retries=4,
            initial_delay=1,
            max_delay=4,
            retry_logic=self.should_retry_on_exception,
        )
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetriableException("Temporary failure")
            return "success"

        result = flaky_function()

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1), call(2)])

    @staticmethod
    def should_retry_on_result(result, exception):
        return "url" not in result, "Missing url field in the response data"

    @patch("time.sleep", return_value=None)
    def test_retries_then_fails_on_result(self, mock_sleep):
        call_count = 0

        @retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=1,
            max_delay=5,
            retry_logic=self.should_retry_on_result,
        )
        def flaky_function():
            nonlocal call_count
            call_count += 1
            return {"attachment_id": "abc", "asset_tye": "udp_flow"}

        try:
            flaky_function()
        except Exception as e:
            self.assertIsInstance(e, DocpipeException)
            self.assertEqual(
                str(e),
                "Retry logic indicated retry on successful call after 3 attempts:"
                + " Missing url field in the response data",
            )

        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1), call(2)])  # delay doubles until max_retries is hit

    @patch("time.sleep", return_value=None)
    def test_eventually_succeeds_on_result(self, mock_sleep):
        call_count = 0

        @retry_with_exponential_backoff(
            max_retries=4,
            initial_delay=1,
            max_delay=4,
            retry_logic=self.should_retry_on_result,
        )
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"attachment_id": "abc", "asset_tye": "udp_flow"}
            return {
                "attachment_id": "abc",
                "asset_tye": "udp_flow",
                "url": "https://test.cloud.ibm.com",
            }

        result = flaky_function()

        self.assertEqual(
            result,
            {
                "attachment_id": "abc",
                "asset_tye": "udp_flow",
                "url": "https://test.cloud.ibm.com",
            },
        )
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1), call(2)])


if __name__ == "__main__":
    unittest.main()
