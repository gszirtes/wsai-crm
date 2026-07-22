from models import Milestone

# Starter milestone sets offered at project-creation time (plan 4.1) --
# mirrors the STAGE_PROBABILITY constant-map pattern (deals.py): a small,
# fixed, code-owned lookup rather than admin-configurable data, since these
# are just a convenience starting point the user edits afterward, not a
# business rule that needs to be tunable.
MILESTONE_TEMPLATES = {
    "single_final": [
        {"name": "Final delivery", "percentage": 100},
    ],
    "deposit_final": [
        {"name": "Deposit", "percentage": 50},
        {"name": "Final delivery", "percentage": 50},
    ],
    "milestones": [],  # free list -- no starter rows, user builds their own
}

DEFAULT_TEMPLATE = "single_final"


def instantiate_template(template_key: str, project_id: str) -> list[Milestone]:
    """Build (unsaved) Milestone rows for a newly-created project from a
    template key. Falls back to the default template for an unknown key
    instead of raising, since this only ever runs from project-creation
    convenience code, not from validated client input."""
    rows = MILESTONE_TEMPLATES.get(template_key, MILESTONE_TEMPLATES[DEFAULT_TEMPLATE])
    return [
        Milestone(project_id=project_id, name=row["name"], order_index=i,
                 percentage=row.get("percentage"), amount=row.get("amount"))
        for i, row in enumerate(rows)
    ]
