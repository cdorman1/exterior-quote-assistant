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
