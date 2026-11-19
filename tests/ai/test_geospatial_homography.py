import math
import unittest
from datetime import datetime, timedelta, timezone

from ai_engine.geospatial.homography import fit_image_to_ground_homography, image_to_geographic
from ai_engine.route_engine.route_reconstructor import RouteReconstructor, DEFAULT_CAMERA_TOPOLOGY


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
        with self.assertRaisesRegex(ValueError, "collinear"):
            fit_image_to_ground_homography([(0, 0), (10, 0), (10, 10), (0, 10)], [(12.0, 77.0), (12.0, 77.1), (12.0, 77.2), (12.0, 77.3)])

    def test_invalid_geographic_points_are_not_projected(self):
        with self.assertRaisesRegex(ValueError, "outside valid geographic bounds"):
            fit_image_to_ground_homography([(0, 0), (1, 0), (1, 1), (0, 1)], [(91, 77), (12, 77.1), (12.1, 77), (12.1, 77.1)])
        with self.assertRaisesRegex(ValueError, "outside valid geographic bounds"):
            fit_image_to_ground_homography([(0, 0), (1, 0), (1, 1), (0, 1)], [(12, -181), (12, 77.1), (12.1, 77), (12.1, 77.1)])

    def test_bengaluru_silk_board_ground_contact_projection(self):
        # Realistic 1920x1080 camera calibration for Bengaluru Silk Board intersection
        # Surveyed control points on intersection road plane
        image_pts = [(400.0, 300.0), (1500.0, 300.0), (1800.0, 1000.0), (100.0, 1000.0)]
        ground_pts = [
            (12.91745, 77.62270),  # Far left
            (12.91745, 77.62310),  # Far right
            (12.91700, 77.62315),  # Near right
            (12.91700, 77.62265),  # Near left
        ]
        matrix, origin = fit_image_to_ground_homography(image_pts, ground_pts)

        # Tall vehicle (e.g., BMTC bus) bounding box: [x1, y1, x2, y2]
        x1, y1, x2, y2 = 800.0, 400.0, 1100.0, 950.0
        contact_x = (x1 + x2) / 2.0  # 950.0
        contact_y = y2              # 950.0 (ground plane contact)
        center_y = (y1 + y2) / 2.0  # 675.0 (mid-chassis, above ground plane)

        lat_ground, lon_ground = image_to_geographic(matrix, origin, contact_x, contact_y)
        lat_mid, lon_mid = image_to_geographic(matrix, origin, contact_x, center_y)

        # Ground contact point must fall accurately inside the intersection latitude/longitude range
        self.assertTrue(12.91700 <= lat_ground <= 12.91745)
        self.assertTrue(77.62265 <= lon_ground <= 77.62315)

        # The mid-chassis point projects significantly farther north/up-road than the true tire ground contact
        self.assertNotEqual(round(lat_ground, 6), round(lat_mid, 6))
        self.assertGreater(lat_mid, lat_ground)

    def test_multi_point_route_reconstruction_chronology_and_source_labeling(self):
        router = RouteReconstructor()
        now = datetime.now(timezone.utc)

        # Provide sightings deliberately OUT OF ORDER with mixed naive & aware timestamps
        sightings = [
            ("C03", now, 52.0, "calibrated_camera_homography", 12.92601, 77.67623),
            ("C01", (now - timedelta(minutes=20)).replace(tzinfo=None), 48.0, "calibrated_camera_homography", 12.91721, 77.62285),
            ("C02", now - timedelta(minutes=10), 55.0, "imported_gps", 12.91163, 77.64382),
        ]

        route = router.reconstruct("KA-01-EQ-5544", sightings)

        # Must be sorted chronologically C01 -> C02 -> C03
        self.assertEqual(route.cameras_visited, ["C01", "C02", "C03"])
        self.assertEqual(route.start_camera_id, "C01")
        self.assertEqual(route.end_camera_id, "C03")
        self.assertEqual(len(route.waypoints), 3)

        # Check waypoint timestamps are strictly non-decreasing and UTC-aware
        for i in range(len(route.waypoints) - 1):
            self.assertLessEqual(route.waypoints[i].timestamp, route.waypoints[i + 1].timestamp)
            self.assertIsNotNone(route.waypoints[i].timestamp.tzinfo)

        # Check distance & duration
        self.assertGreater(route.distance_km, 6.0)  # Silk Board to Bellandur via HSR is ~7-8 km
        self.assertAlmostEqual(route.duration_minutes, 20.0, delta=0.5)

        # Check source labeling
        self.assertEqual(route.coordinate_space, "WGS84 latitude/longitude")
        self.assertIn("calibrated_camera_homography", route.source_types)
        self.assertIn("imported_gps", route.source_types)
        self.assertEqual(route.waypoints[0].source_type, "calibrated_camera_homography")
        self.assertEqual(route.waypoints[1].source_type, "imported_gps")
        self.assertEqual(route.waypoints[2].source_type, "calibrated_camera_homography")


if __name__ == "__main__":
    unittest.main()
