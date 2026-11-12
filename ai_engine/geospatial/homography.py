"""Planar camera calibration helpers; pixels are never coordinates by themselves."""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

EARTH_RADIUS_METERS = 6_378_137.0


def _latlon_to_local_meters(latitude: float, longitude: float, origin: tuple[float, float]) -> tuple[float, float]:
    origin_lat, origin_lon = origin
    east = EARTH_RADIUS_METERS * np.radians(longitude - origin_lon) * np.cos(np.radians(origin_lat))
    north = EARTH_RADIUS_METERS * np.radians(latitude - origin_lat)
    return float(east), float(north)


def fit_image_to_ground_homography(
    image_points: Sequence[Sequence[float]],
    geographic_points: Sequence[Sequence[float]],
) -> tuple[list[list[float]], tuple[float, float]]:
    """Fit pixel (x,y) to local east/north meters using >=4 paired points."""
    if len(image_points) != len(geographic_points) or len(image_points) < 4:
        raise ValueError("Camera calibration requires at least four paired image and GPS points.")
    image = np.asarray(image_points, dtype=np.float64)
    geographic = np.asarray(geographic_points, dtype=np.float64)
    if image.shape != (len(image_points), 2) or geographic.shape != (len(image_points), 2):
        raise ValueError("Calibration points must each contain exactly two numeric coordinates.")
    if not np.isfinite(image).all() or not np.isfinite(geographic).all():
        raise ValueError("Calibration coordinates must be finite numbers.")
    if np.any((geographic[:, 0] < -90) | (geographic[:, 0] > 90)) or np.any((geographic[:, 1] < -180) | (geographic[:, 1] > 180)):
        raise ValueError("Calibration latitude or longitude is outside valid geographic bounds.")
    if np.unique(image, axis=0).shape[0] < 4 or np.unique(geographic, axis=0).shape[0] < 4:
        raise ValueError("Calibration requires four distinct image points and four distinct geographic points.")
    if np.linalg.matrix_rank(image - image.mean(axis=0)) < 2:
        raise ValueError("Image calibration points must not be collinear.")

    origin = (float(geographic[0, 0]), float(geographic[0, 1]))
    local = np.asarray([_latlon_to_local_meters(lat, lon, origin) for lat, lon in geographic], dtype=np.float64)
    if np.linalg.matrix_rank(local - local.mean(axis=0)) < 2:
        raise ValueError("Geographic calibration points must not be collinear.")
    matrix, _ = cv2.findHomography(image, local, method=0)
    if matrix is None or not np.isfinite(matrix).all() or abs(float(np.linalg.det(matrix))) < 1e-12:
        raise ValueError("Could not calculate a stable image-to-ground homography from these points.")
    return matrix.tolist(), origin


def image_to_geographic(
    matrix: Sequence[Sequence[float]],
    origin: tuple[float, float],
    image_x: float,
    image_y: float,
) -> tuple[float, float]:
    """Project a calibrated pixel to latitude/longitude; caller must supply calibration."""
    transform = np.asarray(matrix, dtype=np.float64)
    if transform.shape != (3, 3) or not np.isfinite(transform).all():
        raise ValueError("Stored camera homography is invalid.")
    projected = transform @ np.asarray([image_x, image_y, 1.0], dtype=np.float64)
    if not np.isfinite(projected).all() or abs(float(projected[2])) < 1e-12:
        raise ValueError("Image point cannot be projected through the camera homography.")
    east, north = projected[:2] / projected[2]
    latitude = origin[0] + float(np.degrees(north / EARTH_RADIUS_METERS))
    longitude = origin[1] + float(np.degrees(east / (EARTH_RADIUS_METERS * np.cos(np.radians(origin[0])))))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Projected point falls outside geographic coordinate bounds.")
    return latitude, longitude
