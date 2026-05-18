PROJECT_TYPES = ["new_construction", "existing_construction"]
TRADE_SCOPES = ["roofing", "siding", "masonry", "combination"]
TRADES = ["roofing", "siding", "masonry"]
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
