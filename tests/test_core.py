import unittest
import numpy as np
from pycocotools import mask as coco_mask
from maskledger.metrics import compare_masks
from maskledger.rle import decode_rle
from maskledger.errors import InputError


class MetricsTests(unittest.TestCase):
    def test_filled_hole(self):
        a = np.ones((5, 5), dtype=bool)
        a[2, 2] = False
        b = np.ones_like(a)
        s = compare_masks(a, b)
        self.assertEqual(s.get('added_pixels'), 1)
        self.assertEqual(s['reference_holes'], 1)
        self.assertEqual(s['candidate_holes'], 0)
        self.assertEqual(s['iou'], 24 / 25)

    def test_bridge_changes_components(self):
        a = np.zeros((5, 7), bool)
        a[1:4, 0:2] = True
        a[1:4, 5:7] = True
        b = a.copy()
        b[2, 2:5] = True
        s = compare_masks(a, b)
        self.assertEqual(s.get('reference_components'), 2)
        self.assertEqual(s['candidate_components'], 1)
        self.assertEqual(s['added_pixels'], 3)

    def test_diagonal_foreground_eight_connected(self):
        a = np.eye(3, dtype=bool)
        self.assertEqual(compare_masks(a, a).get('reference_components'), 1)

    def test_background_four_connected(self):
        a = np.ones((3, 3), bool)
        a[0, 0] = a[1, 1] = False
        self.assertEqual(compare_masks(a, a).get('reference_holes'), 1)

    def test_equal_area_moved_still_changes(self):
        a = np.zeros((3, 5), bool)
        a[1, 1] = True
        b = np.zeros_like(a)
        b[1, 3] = True
        s = compare_masks(a, b)
        self.assertEqual(s.get('iou'), 0)
        self.assertEqual(s['added_pixels'], 1)
        self.assertEqual(s['removed_pixels'], 1)
        self.assertFalse(s['equal'])

    def test_empty_is_undefined_iou(self):
        s = compare_masks(np.zeros((2, 4), bool), np.zeros((2, 4), bool))
        self.assertTrue(s.get('equal'))
        self.assertIsNone(s['iou'])
        self.assertEqual(s['reference_holes'], 0)

    def test_identity(self):
        a = np.array([[0, 1, 0], [1, 0, 1]], dtype=bool)
        s = compare_masks(a, a)
        self.assertEqual(s.get('iou'), 1)
        self.assertEqual(s['intersection'], 3)
        self.assertTrue(s['equal'])

    def test_bad_arrays_rejected(self):
        for a, b in [(np.zeros((2, 2)), np.zeros((2, 2))),
                     (np.zeros((2, 2), bool), np.zeros((2, 3), bool)),
                     (np.zeros((0, 2), bool), np.zeros((0, 2), bool)),
                     (np.zeros((2, 2, 1), bool), np.zeros((2, 2, 1), bool))]:
            with self.subTest(shape=a.shape), self.assertRaises(InputError):
                compare_masks(a, b)


class RLETests(unittest.TestCase):
    def test_fortran_order(self):
        a = decode_rle({'size': [2, 3], 'counts': [1, 1, 4]}, 2, 3)
        self.assertTrue(np.array_equal(a, [[False, False, False], [True, False, False]]))

    def test_coco_compressed_oracle(self):
        rng = np.random.default_rng(1926)
        for shape in [(1, 1), (3, 7), (17, 9), (48, 64)]:
            for p in [0, .1, .5, .9, 1]:
                a = rng.random(shape) < p
                encoded = coco_mask.encode(np.asfortranarray(a.astype('uint8')))
                encoded['counts'] = encoded['counts'].decode('ascii')
                actual = decode_rle(encoded, *shape)
                self.assertTrue(np.array_equal(actual, a), (shape, p))

    def test_malformed_rles_rejected(self):
        bad = [None, {}, {'size': [2, 3], 'counts': [True, 5]},
               {'size': [2, 3], 'counts': [-1, 7]},
               {'size': [2, 3], 'counts': [5]},
               {'size': [2, 3], 'counts': [7]},
               {'size': [3, 2], 'counts': [6]},
               {'size': [2, 3], 'counts': 'o'},
               {'size': [2, 3], 'counts': 'x'},
               {'size': [2, 3], 'counts': ''},
               {'size': [2, 3], 'counts': [1.0, 5]}]
        for x in bad:
            with self.subTest(x=x), self.assertRaises(InputError):
                decode_rle(x, 2, 3)

    def test_dimension_budget(self):
        with self.assertRaises(InputError):
            decode_rle({'size': [2, 3], 'counts': [6]}, 2, 3, max_pixels=5)
        with self.assertRaises(InputError):
            decode_rle({'size': [True, 3], 'counts': [3]}, True, 3)


if __name__ == '__main__':
    unittest.main()
