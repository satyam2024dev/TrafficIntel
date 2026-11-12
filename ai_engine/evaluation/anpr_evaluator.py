"""Ground-truth evaluation for plate localization and OCR.

Detection metrics use one-to-one IoU matching between manually labeled plate
boxes and real pipeline predictions. OCR metrics use every labeled plate,
including missed detections as empty predictions.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate


def intersection_over_union(first: dict[str, float], second: dict[str, float]) -> float:
    left = max(first["x1"], second["x1"])
    top = max(first["y1"], second["y1"])
    right = min(first["x2"], second["x2"])
    bottom = min(first["y2"], second["y2"])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first["x2"] - first["x1"]) * max(0.0, first["y2"] - first["y1"])
    second_area = max(0.0, second["x2"] - second["x1"]) * max(0.0, second["y2"] - second["y1"])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _edit_distance(first: str, second: str) -> int:
    previous = list(range(len(second) + 1))
    for row, char_a in enumerate(first, start=1):
        current = [row]
        for column, char_b in enumerate(second, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _sample_key(frame_number: int | None) -> int:
    # Image results store NULL for their frame number; image labels use frame 1.
    return frame_number if frame_number is not None else 1


def evaluate_anpr(
    samples: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Score annotated samples without modifying their source or predictions.

    Each sample has ``frame_number`` and ``ground_truth_plates`` entries with
    ``registration_number`` and ``bbox`` (x1/y1/x2/y2). Predictions use the
    same frame and box fields plus stored OCR and confidence values.
    """
    if not 0 < iou_threshold <= 1:
        raise ValueError("IoU threshold must be greater than 0 and at most 1.")
    sample_map: dict[int, dict[str, Any]] = {}
    for sample in samples:
        key = _sample_key(sample.get("frame_number"))
        if key in sample_map:
            raise ValueError(f"Frame {key} is annotated more than once.")
        labels = []
        for label_index, label in enumerate(sample.get("ground_truth_plates", [])):
            raw_gt = str(label.get("registration_number", ""))
            normalized_gt, validation = normalize_registration_candidate(raw_gt)
            if validation != "valid_indian_format":
                raise ValueError(f"Ground truth '{raw_gt}' is not a valid Indian registration format.")
            bbox = {axis: float(label["bbox"][axis]) for axis in ("x1", "y1", "x2", "y2")}
            if bbox["x2"] <= bbox["x1"] or bbox["y2"] <= bbox["y1"]:
                raise ValueError("Ground-truth plate boxes must have positive width and height.")
            labels.append({
                "label_index": label_index,
                "registration_number": raw_gt,
                "normalized_registration_number": normalized_gt,
                "validation_status": validation,
                "bbox": bbox,
            })
        sample_map[key] = {"frame_number": key, "ground_truth": labels, "predictions": []}

    for prediction in predictions:
        key = _sample_key(prediction.get("frame_number"))
        if key not in sample_map:
            continue
        raw_ocr_text = prediction.get("raw_ocr_text")
        normalized_ocr_text = prediction.get("normalized_ocr_text") or ""
        inferred_candidate, inferred_validation = normalize_registration_candidate(raw_ocr_text)
        if not normalized_ocr_text:
            normalized_ocr_text = inferred_candidate
        _candidate, normalized_validation = normalize_registration_candidate(normalized_ocr_text)
        validation_status = prediction.get("plate_validation_status") or normalized_validation or inferred_validation
        sample_map[key]["predictions"].append({
            **prediction,
            "bbox": {axis: float(prediction[axis]) for axis in ("x1", "y1", "x2", "y2")},
            "raw_ocr_text": raw_ocr_text,
            "normalized_ocr_text": normalized_ocr_text,
            "plate_validation_status": validation_status,
        })

    total_tp = total_fp = total_fn = exact_matches = total_edit_distance = total_gt_characters = 0
    plate_confidence: dict[str, list[float]] = defaultdict(list)
    ocr_confidence: dict[str, list[float]] = defaultdict(list)
    sample_reports = []
    for frame_number in sorted(sample_map):
        sample = sample_map[frame_number]
        labels, candidates = sample["ground_truth"], sample["predictions"]
        pairings = []
        for gt_index, label in enumerate(labels):
            for pred_index, prediction in enumerate(candidates):
                overlap = intersection_over_union(label["bbox"], prediction["bbox"])
                if overlap >= iou_threshold:
                    pairings.append((overlap, gt_index, pred_index))
        pairings.sort(key=lambda pair: (-pair[0], pair[1], pair[2]))
        matched_gt: dict[int, tuple[int, float]] = {}
        matched_predictions: dict[int, tuple[int, float]] = {}
        for overlap, gt_index, pred_index in pairings:
            if gt_index not in matched_gt and pred_index not in matched_predictions:
                matched_gt[gt_index] = (pred_index, overlap)
                matched_predictions[pred_index] = (gt_index, overlap)

        prediction_reports = []
        for pred_index, prediction in enumerate(candidates):
            raw = prediction.get("raw_ocr_text")
            normalized = prediction.get("normalized_ocr_text") or ""
            validation = prediction.get("plate_validation_status")
            validated_registration = normalized if validation == "valid_indian_format" else None
            if pred_index in matched_predictions:
                gt_index, overlap = matched_predictions[pred_index]
                label = labels[gt_index]
                exact = normalized == label["normalized_registration_number"]
                ocr_state = "exact_match" if exact else "incorrect" if normalized else "unreadable"
                match_state = "true_positive"
                ocr_group = "exact_match" if exact else "incorrect" if normalized else "unreadable"
                if prediction.get("ocr_confidence") is not None:
                    ocr_confidence[ocr_group].append(prediction["ocr_confidence"])
                if prediction.get("plate_confidence") is not None:
                    plate_confidence["true_positive"].append(prediction["plate_confidence"])
                prediction_reports.append({
                    "prediction_id": prediction.get("id"), "bbox": prediction["bbox"],
                    "match_status": match_state, "matched_ground_truth": label["normalized_registration_number"],
                    "iou": overlap, "raw_ocr_text": raw, "normalized_ocr_text": normalized or None,
                    "validated_registration_number": validated_registration,
                    "plate_validation_status": validation, "ocr_status": ocr_state,
                    "plate_confidence": prediction.get("plate_confidence"),
                    "ocr_confidence": prediction.get("ocr_confidence"),
                })
            else:
                duplicate_of = None
                for previous_index, previous in enumerate(candidates):
                    if previous_index == pred_index:
                        continue
                    same_candidate = bool(normalized and normalized == (previous.get("normalized_ocr_text") or ""))
                    overlap = intersection_over_union(prediction["bbox"], previous["bbox"])
                    if same_candidate or overlap >= 0.8:
                        duplicate_of = previous.get("id")
                        break
                match_state = "duplicate" if duplicate_of is not None else "false_positive"
                if prediction.get("plate_confidence") is not None:
                    plate_confidence[match_state].append(prediction["plate_confidence"])
                prediction_reports.append({
                    "prediction_id": prediction.get("id"), "bbox": prediction["bbox"],
                    "match_status": match_state, "duplicate_of_prediction_id": duplicate_of,
                    "matched_ground_truth": None, "iou": None, "raw_ocr_text": raw,
                    "normalized_ocr_text": normalized or None,
                    "validated_registration_number": validated_registration,
                    "plate_validation_status": validation,
                    "ocr_status": "not_scored_without_ground_truth_match",
                    "plate_confidence": prediction.get("plate_confidence"),
                    "ocr_confidence": prediction.get("ocr_confidence"),
                })

        gt_reports = []
        sample_edits = sample_characters = sample_exact = 0
        for gt_index, label in enumerate(labels):
            if gt_index in matched_gt:
                pred_index, overlap = matched_gt[gt_index]
                prediction = candidates[pred_index]
                candidate = prediction.get("normalized_ocr_text") or ""
                exact = candidate == label["normalized_registration_number"]
                if not candidate:
                    ocr_state = "unreadable_ocr"
                elif exact:
                    ocr_state = "exact_match"
                else:
                    ocr_state = "incorrect_ocr"
                matched_prediction_id = prediction.get("id")
                ocr_score = prediction.get("ocr_confidence")
                raw_ocr = prediction.get("raw_ocr_text")
                normalized_ocr = prediction.get("normalized_ocr_text") or None
                validated_ocr = normalized_ocr if prediction.get("plate_validation_status") == "valid_indian_format" else None
                plate_score = prediction.get("plate_confidence")
            else:
                candidate = ""
                exact = False
                ocr_state = "missed_plate_detection"
                matched_prediction_id = None
                overlap = None
                ocr_score = None
                raw_ocr = normalized_ocr = validated_ocr = plate_score = None
            distance = _edit_distance(label["normalized_registration_number"], candidate)
            total_edit_distance += distance
            sample_edits += distance
            total_gt_characters += len(label["normalized_registration_number"])
            sample_characters += len(label["normalized_registration_number"])
            if exact:
                exact_matches += 1
                sample_exact += 1
            gt_reports.append({
                "registration_number": label["registration_number"],
                "normalized_registration_number": label["normalized_registration_number"],
                "validated_registration_number": label["normalized_registration_number"],
                "validation_status": label["validation_status"], "bbox": label["bbox"],
                "matched_prediction_id": matched_prediction_id, "iou": overlap,
                "ocr_status": ocr_state, "ocr_exact_match": exact,
                "ocr_edit_distance": distance, "raw_ocr_text": raw_ocr,
                "normalized_ocr_text": normalized_ocr,
                "predicted_validated_registration_number": validated_ocr,
                "plate_confidence": plate_score, "ocr_confidence": ocr_score,
            })

        tp, fp, fn = len(matched_gt), len(candidates) - len(matched_predictions), len(labels) - len(matched_gt)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        sample_precision = _rate(tp, tp + fp)
        sample_recall = _rate(tp, tp + fn)
        sample_f1 = _rate(2 * tp, 2 * tp + fp + fn)
        sample_reports.append({
            "frame_number": frame_number, "ground_truth_count": len(labels), "prediction_count": len(candidates),
            "detection": {"true_positives": tp, "false_positives": fp, "false_negatives": fn,
                          "precision": sample_precision, "recall": sample_recall, "f1_score": sample_f1},
            "ocr": {"exact_matches": sample_exact, "count": len(labels),
                    "exact_match_accuracy": _rate(sample_exact, len(labels)),
                    "character_error_rate": _rate(sample_edits, sample_characters)},
            "ground_truth": gt_reports, "predictions": prediction_reports,
        })

    precision = _rate(total_tp, total_tp + total_fp)
    recall = _rate(total_tp, total_tp + total_fn)
    f1 = _rate(2 * total_tp, 2 * total_tp + total_fp + total_fn)
    return {
        "methodology": {
            "detection_matching": "one-to-one greedy IoU matching",
            "iou_threshold": iou_threshold,
            "ocr_comparison": "separator-normalized registration candidate; no character correction",
            "character_error_rate": "corpus edit distance divided by total ground-truth characters; missed plates count as empty OCR",
            "format_validation": "syntactic Indian registration format only; no RTO registry lookup",
        },
        "aggregate": {
            "sample_count": len(sample_reports), "ground_truth_plate_count": total_tp + total_fn,
            "prediction_count": total_tp + total_fp, "true_positives": total_tp,
            "false_positives": total_fp, "false_negatives": total_fn,
            "precision": precision, "recall": recall, "f1_score": f1,
            "ocr_exact_matches": exact_matches, "ocr_exact_match_accuracy": _rate(exact_matches, total_tp + total_fn),
            "character_error_rate": _rate(total_edit_distance, total_gt_characters),
            "duplicate_detection_count": sum(
                prediction["match_status"] == "duplicate"
                for sample in sample_reports for prediction in sample["predictions"]
            ),
            "incorrect_detection_count": total_fp,
            "ocr_failure_count": sum(
                ground_truth["ocr_status"] in {"unreadable_ocr", "missed_plate_detection"}
                for sample in sample_reports for ground_truth in sample["ground_truth"]
            ),
            "incorrect_ocr_count": sum(
                ground_truth["ocr_status"] == "incorrect_ocr"
                for sample in sample_reports for ground_truth in sample["ground_truth"]
            ),
        },
        "confidence_analysis": {
            "plate_detection_confidence": {
                key: {"count": len(values), "mean": _mean(values)}
                for key, values in sorted(plate_confidence.items())
            },
            "ocr_confidence": {
                key: {"count": len(values), "mean": _mean(values)}
                for key, values in sorted(ocr_confidence.items())
            },
            "confidence_semantics": "plate confidence scores localization; OCR confidence scores recognized text; they are not combined",
        },
        "samples": sample_reports,
    }
