PROJECT_TYPES = ["new_construction", "existing_construction"]
TRADE_SCOPES = ["roofing", "siding", "combination"]
TRADES = ["roofing", "siding"]
LABOR_METHODS = ["unit_based", "crew_day", "hourly", "subcontractor"]
LABOR_METHOD_LABELS = {
    "unit_based": "Unit based labor",
    "crew_day": "Crew day labor",
    "hourly": "Hourly labor",
    "subcontractor": "Subcontractor quote",
}
LABOR_DIFFICULTY_MULTIPLIERS = {
    "simple": 1.00,
    "moderate": 1.15,
    "difficult": 1.30,
    "very_difficult": 1.50,
}
LABOR_CONDITION_MULTIPLIERS = {
    "roofing": {
        "two_story": 1.15,
        "three_story": 1.30,
        "steep_pitch": 1.25,
        "complex_roof": 1.20,
        "poor_access": 1.20,
        "multiple_layers": 1.20,
    },
    "siding": {
        "two_story": 1.15,
        "three_story": 1.30,
        "many_openings": 1.10,
        "complex_gables": 1.15,
        "fiber_cement": 1.35,
        "poor_access": 1.20,
        "tear_off_required": 1.10,
    },
}
QUOTE_STATUSES = ["draft", "sent", "accepted", "rejected"]
PROJECT_STATUSES = ["lead", "estimating", "quoted", "won", "lost", "completed"]
TAKEOFF_SOURCES = ["manual", "pdf_assisted", "field_measurement", "openai_vision_extracted", "manual_overlay_adjusted", "ai_suggested_future", "cad_extracted_future"]
TAKEOFF_REVIEW_IMAGE_WIDTH = 1000
TAKEOFF_REVIEW_COORDINATE_SPACE = f"review_display_px_{TAKEOFF_REVIEW_IMAGE_WIDTH}w"
TAKEOFF_NATIVE_COORDINATE_SPACE = "native_rendered_image_px"
OPENAI_VISION_MODEL_DEFAULT = "gpt-5.5"
MEASUREMENT_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]
ROOFING_AREA_MEASUREMENT_TYPES = ["roof_area"]
ROOFING_LINEAR_MEASUREMENT_TYPES = [
    "ridge_length",
    "valley_length",
    "hip_length",
    "rake_length",
    "eave_length",
    "drip_edge_length",
    "flashing_length",
    "roof_penetration_count",
]
SIDING_AREA_MEASUREMENT_TYPES = ["siding_wall_area", "gable_area"]
SIDING_LINEAR_MEASUREMENT_TYPES = [
    "soffit_length",
    "fascia_length",
    "j_channel_length",
    "outside_corner_count",
    "inside_corner_count",
    "trim_length",
]
GENERAL_MEASUREMENT_TYPES = ["general_measurement"]

DEFAULT_ASSUMPTIONS = [
    "Pricing is based on the measurements and scope available at the time of quote.",
    "Hidden damage, code-required upgrades, and owner-requested changes are handled by change order.",
    "Blueprint upload and automated measurement extraction are planned for a future version.",
]

DEFAULT_EXCLUSIONS = [
    "Structural engineering, architectural revisions, and permit expediting unless listed in the quote.",
    "Electrical, plumbing, HVAC, painting, landscaping, and interior repairs unless specifically included.",
    "Hazardous material testing or remediation.",
]
