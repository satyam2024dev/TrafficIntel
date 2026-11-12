import unittest

from ai_engine.geospatial.homography import fit_image_to_ground_homography, image_to_geographic


class CameraHomographyTests(unittest.TestCase):
    def test_calibrated_image_point_maps_to_ground_coordinates(self):
        image = [(0, 0), (100, 0), (100, 100), (0, 100)]
        ground = [(12.0, 77.0), (12.0, 77.0001), (12.0001, 77.0001), (12.0001, 77.0)]
        matrix, origin = fit_image_to_ground_homography(image, ground)
        latitude, longitude = image_to_geographic(matrix, origin, 50, 50)
        self.assertAlmostEqual(latitude, 12.00005, places=7)
        self.assertAlmostEqual(longitude, 77.00005, places=7)

    def test_insufficient_and_collinear_control_points_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least four"):
            fit_image_to_ground_homography([(0, 0), (1, 0), (0, 1)], [(12, 77), (12, 77.1), (12.1, 77)])
        with self.assertRaisesRegex(ValueError, "collinear"):
            fit_image_to_ground_homography([(0, 0), (1, 0), (2, 0), (3, 0)], [(12, 77), (12, 77.1), (12.1, 77), (12.1, 77.1)])

    def test_invalid_geographic_points_are_not_projected(self):
        with self.assertRaisesRegex(ValueError, "outside valid geographic bounds"):
            fit_image_to_ground_homography([(0, 0), (1, 0), (1, 1), (0, 1)], [(91, 77), (12, 77.1), (12.1, 77), (12.1, 77.1)])


if __name__ == "__main__":
    unittest.main()
