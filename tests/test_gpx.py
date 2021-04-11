import unittest

import secretblog.gpx as gpx


class TestHelpers(unittest.TestCase):
    def test_neighbors_dont_wrap_at_start(self):
        self.assertEqual(gpx._neighbors(0, 5, 2, False), [0, 1, 2])

    def test_neighbors_dont_wrap_near_end(self):
        self.assertEqual(gpx._neighbors(3, 5, 2, False), [1, 2, 3, 4])

    def test_neighbors_wrap_near_start(self):
        self.assertEqual(gpx._neighbors(1, 6, 2, True), [5, 0, 1, 2, 3])

    def test_neighbors_wrap_at_end(self):
        self.assertEqual(gpx._neighbors(5, 6, 2, True), [3, 4, 5, 0, 1])

    def test_neighbors_fills_list(self):
        self.assertEqual(gpx._neighbors(2, 5, 2, True), [0, 1, 2, 3, 4])

    def test_neighbors_wrap_fills_list(self):
        self.assertEqual(gpx._neighbors(3, 5, 2, True), [1, 2, 3, 4, 0])

    def test_neighbors_wrap_overlaps_one(self):
        self.assertEqual(gpx._neighbors(3, 4, 2, True), [1, 2, 3, 0])

    def test_neighbors_wrap_overlaps_multiple(self):
        self.assertEqual(gpx._neighbors(3, 4, 3, True), [0, 1, 2, 3])

    def test_neighbors_wrap_multiple_times(self):
        self.assertEqual(gpx._neighbors(1, 3, 4, True), [0, 1, 2])
