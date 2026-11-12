"""Accuracy metrics are scored only against manually supplied labeled boxes."""
import unittest

from ai_engine.evaluation.anpr_evaluator import evaluate_anpr
from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate


def box(x1, y1, x2, y2):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def label(number, bounds):
    return {"registration_number": number, "bbox": bounds}


def prediction(identifier, bounds, text, normalized, plate_score, ocr_score, validation="valid_indian_format"):
    return {
        "id": identifier, "frame_number": 1, **bounds,
        "raw_ocr_text": text, "normalized_ocr_text": normalized,
        "plate_validation_status": validation,
        "plate_confidence": plate_score, "ocr_confidence": ocr_score,
    }


class ANPREvaluatorTests(unittest.TestCase):
    def test_normalization_accepts_common_indian_formats_without_correcting_characters(self):
        cases = [
            ("ka 01 ab 1234", "KA01AB1234"),
            ("DL 8 CAF 1234", "DL8CAF1234"),
            ("MH12-EF-9012", "MH12EF9012"),
            ("22 BH 1234 AA", "22BH1234AA"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_registration_candidate(raw), (expected, "valid_indian_format"))
        self.assertEqual(normalize_registration_candidate("KA01AB12O4"), ("KA01AB12O4", "invalid_indian_format"))

    def test_metrics_identify_misses_false_positives_duplicates_and_ocr_errors(self):
        samples = [
            {"frame_number": 1, "ground_truth_plates": [
                label("KA 01 AB 1234", box(0, 0, 100, 30)),
                label("DL8CAF1234", box(200, 0, 300, 30)),
            ]},
            {"frame_number": 61, "ground_truth_plates": [
                label("22 BH 1234 AA", box(10, 10, 110, 40)),
            ]},
        ]
        predictions = [
            prediction(1, box(0, 0, 100, 30), "KA 01 AB 1234", "KA01AB1234", 0.8, 0.95),
            prediction(2, box(200, 0, 300, 30), "DL8CAF1235", "DL8CAF1235", 0.6, 0.5),
            prediction(3, box(1, 1, 101, 31), "KA01AB1234", "KA01AB1234", 0.3, 0.9),
            prediction(4, box(400, 100, 500, 130), "TN09GH3456", "TN09GH3456", 0.2, 0.4),
        ]
        report = evaluate_anpr(samples, predictions, iou_threshold=0.5)
        aggregate = report["aggregate"]
        self.assertEqual((aggregate["true_positives"], aggregate["false_positives"], aggregate["false_negatives"]), (2, 2, 1))
        self.assertAlmostEqual(aggregate["precision"], 0.5)
        self.assertAlmostEqual(aggregate["recall"], 2 / 3)
        self.assertAlmostEqual(aggregate["f1_score"], 4 / 7)
        self.assertEqual(aggregate["ocr_exact_matches"], 1)
        self.assertAlmostEqual(aggregate["ocr_exact_match_accuracy"], 1 / 3)
        self.assertAlmostEqual(aggregate["character_error_rate"], 11 / 30)
        self.assertEqual(aggregate["duplicate_detection_count"], 1)
        self.assertEqual(aggregate["ocr_failure_count"], 1)
        self.assertEqual(aggregate["incorrect_ocr_count"], 1)
        self.assertEqual(report["samples"][0]["predictions"][2]["match_status"], "duplicate")
        self.assertEqual(report["samples"][1]["ground_truth"][0]["ocr_status"], "missed_plate_detection")
        confidence = report["confidence_analysis"]
        self.assertAlmostEqual(confidence["plate_detection_confidence"]["true_positive"]["mean"], 0.7)
        self.assertAlmostEqual(confidence["ocr_confidence"]["exact_match"]["mean"], 0.95)
        self.assertAlmostEqual(confidence["ocr_confidence"]["incorrect"]["mean"], 0.5)

    def test_missed_ocr_is_an_empty_prediction_and_invalid_ground_truth_is_rejected(self):
        report = evaluate_anpr(
            [{"frame_number": 1, "ground_truth_plates": [label("KA01AB1234", box(0, 0, 100, 30))]}],
            [prediction(1, box(0, 0, 100, 30), None, None, 0.7, None, validation="empty")],
        )
        self.assertEqual(report["aggregate"]["true_positives"], 1)
        self.assertEqual(report["aggregate"]["ocr_exact_match_accuracy"], 0)
        self.assertEqual(report["aggregate"]["character_error_rate"], 1)
        self.assertEqual(report["aggregate"]["ocr_failure_count"], 1)
        with self.assertRaisesRegex(ValueError, "valid Indian registration"):
            evaluate_anpr([{"frame_number": 1, "ground_truth_plates": [label("KA01AB12O4", box(0, 0, 10, 5))]}], [])

    def test_frame_sample_must_be_unique(self):
        samples = [
            {"frame_number": 1, "ground_truth_plates": []},
            {"frame_number": None, "ground_truth_plates": []},
        ]
        with self.assertRaisesRegex(ValueError, "annotated more than once"):
            evaluate_anpr(samples, [])


if __name__ == "__main__":
    unittest.main()
