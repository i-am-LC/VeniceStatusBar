import unittest
from unittest.mock import MagicMock, patch

import requests
import venice_indicator as indicator


class BalanceTests(unittest.TestCase):
    def test_balances_and_allocation(self):
        self.assertEqual(indicator.balance_text({
            'balances': {'diem': 3.5, 'usd': 2}, 'diemEpochAllocation': 10
        }), 'Diem: 3.50 / 10.00  |  USD: $2.00')

    def test_null_and_zero_balances(self):
        self.assertEqual(indicator.balance_text({'balances': {'diem': None, 'usd': 0}}),
                         'Diem: unavailable  |  USD: $0.00')

    def test_invalid_numbers(self):
        for value in ('3', True, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                indicator.balance_text({'balances': {'diem': value}})


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(indicator.VeniceCreditIndicator)

    def test_http_and_response_errors(self):
        cases = [
            (200, {'balances': {'diem': None, 'usd': 5}}, 'USD: $5.00'),
            (401, {}, 'Authentication failed'),
            (403, {}, 'Authentication failed'),
            (429, {}, 'Rate limited'),
            (500, {}, 'Venice API error (500)'),
            (200, {'balances': None}, 'Unexpected response'),
        ]
        for status, payload, expected in cases:
            with self.subTest(status=status, payload=payload):
                response = MagicMock(status_code=status)
                response.json.return_value = payload
                response.__enter__.return_value = response
                with patch.object(indicator.requests, 'get', return_value=response) as get, \
                        patch.object(indicator.GLib, 'idle_add') as idle:
                    self.app.request_balance('dummy-test-key')
                    self.assertIn(expected, idle.call_args.args[2])
                    self.assertEqual(get.call_args.kwargs['headers'],
                                     {'Authorization': 'Bearer dummy-test-key'})

    def test_network_errors(self):
        for error, expected in [(requests.Timeout(), 'timed out'),
                                (requests.ConnectionError(), 'Connection failed')]:
            with self.subTest(error=error), \
                    patch.object(indicator.requests, 'get', side_effect=error), \
                    patch.object(indicator.GLib, 'idle_add') as idle:
                self.app.request_balance('dummy-test-key')
                self.assertIn(expected, idle.call_args.args[2])

    def test_invalid_json(self):
        response = MagicMock(status_code=200)
        response.__enter__.return_value = response
        response.json.side_effect = requests.exceptions.JSONDecodeError('invalid', '', 0)
        with patch.object(indicator.requests, 'get', return_value=response), \
                patch.object(indicator.GLib, 'idle_add') as idle:
            self.app.request_balance('dummy-test-key')
            self.assertIn('Unexpected response', idle.call_args.args[2])


if __name__ == '__main__':
    unittest.main()
