"""Ensure unrelated failures cannot satisfy CLI smoke negative controls."""
import unittest
from test_smoke import DIAGNOSTICS, require_rejection


class Diagnostics(unittest.TestCase):
    def test_intended_failures(self):
        for expected in DIAGNOSTICS.values():
            require_rejection(dict(classification='exited', exit_code=2), expected, expected)

    def test_unrelated_exit_two(self):
        for expected in DIAGNOSTICS.values():
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, 'intended rejection'):
                require_rejection(dict(classification='exited', exit_code=2),
                                  'experiment error: file does not exist', expected)

    def test_wrong_exit_and_unlaunched(self):
        for receipt in (dict(classification='exited', exit_code=0),
                        dict(classification='launch-error', exit_code=None)):
            with self.assertRaisesRegex(ValueError, 'intended rejection'):
                require_rejection(receipt, DIAGNOSTICS['missing-timing'], DIAGNOSTICS['missing-timing'])


if __name__ == '__main__':
    unittest.main()
