"""Request validation for manually labeled ANPR evaluation samples."""
from pydantic import BaseModel, Field, field_validator, model_validator

from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate


class PlateBoxInput(BaseModel):
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(gt=0)
    y2: float = Field(gt=0)

    @model_validator(mode="after")
    def positive_area(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Plate bounding box must have positive width and height.")
        return self


class GroundTruthPlateInput(BaseModel):
    registration_number: str = Field(min_length=1, max_length=50)
    bbox: PlateBoxInput

    @field_validator("registration_number")
    @classmethod
    def valid_indian_registration_format(cls, value: str) -> str:
        _candidate, status = normalize_registration_candidate(value)
        if status != "valid_indian_format":
            raise ValueError("Enter a valid Indian registration number format.")
        return value.strip()


class GroundTruthSampleInput(BaseModel):
    frame_number: int = Field(ge=1)
    ground_truth_plates: list[GroundTruthPlateInput] = Field(default_factory=list, max_length=50)


class ANPREvaluationRequest(BaseModel):
    samples: list[GroundTruthSampleInput] = Field(min_length=1, max_length=3000)
    iou_threshold: float = Field(default=0.5, gt=0, le=1)

