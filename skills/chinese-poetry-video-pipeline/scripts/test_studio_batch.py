import unittest
from export_studio_batch import studio_line, export_lines


class StudioBatchTests(unittest.TestCase):
    def test_mixed_durations_not_default_ten(self):
        lines = export_lines(['first\nbody', 'second body'], [6, 13])
        self.assertEqual(lines, ['6秒，first body', '13秒，second body'])

    def test_decimal_and_bounds(self):
        for n in [2, 6.5, 15]:
            self.assertTrue(studio_line('body', n).startswith(f'{n:g}秒，'))
        for n in [1.9, 15.1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError): studio_line('body', n)

    def test_missing_duration_never_falls_back(self):
        with self.assertRaises(ValueError): export_lines(['one', 'two'], [10])
        with self.assertRaises(ValueError): export_lines([], [])

    def test_double_prefix_rejected(self):
        with self.assertRaises(ValueError): studio_line('6秒，body', 6)

    def test_total_and_window_conflicts(self):
        with self.assertRaises(ValueError): studio_line('[Shot 1] 13-second continuous shot', 10)
        with self.assertRaises(ValueError): studio_line('From 1.00 to 11.00 seconds', 10)

    def test_speech_unchanged(self):
        body = 'instruction\n\n(S1) says: <d>[Chinese] 你好。</d>'
        self.assertEqual(studio_line(body, 6), '6秒，instruction (S1) says: <d>[Chinese] 你好。</d>')

    def test_multishot_durations_are_not_total(self):
        body = '[Shot 1] 3-second shot. [Shot 2] 5-second shot.'
        self.assertTrue(studio_line(body, 8).startswith('8秒，'))


if __name__ == '__main__': unittest.main()
