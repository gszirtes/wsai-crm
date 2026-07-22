from models import Milestone
from utils import log_event

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
    instead of raising -- defensive only: the one caller that matters
    (routers/projects.py::create_project, via
    ProjectCreate.milestone_template) already types this as a Pydantic
    Literal, so a garbage value never reaches here from the public API and
    gets a 422 at the schema layer instead (see
    test_phase4.py::test_unrecognized_milestone_template_rejected_by_schema).
    This fallback only matters for a future caller that invokes this
    function directly with an unvalidated key."""
    rows = MILESTONE_TEMPLATES.get(template_key, MILESTONE_TEMPLATES[DEFAULT_TEMPLATE])
    return [
        Milestone(project_id=project_id, name=row["name"], order_index=i,
                 percentage=row.get("percentage"), amount=row.get("amount"))
        for i, row in enumerate(rows)
    ]


def seed_project_milestones(db, project, template_key: str, actor, note: str = None):
    """Instantiate `template_key`'s starter Milestone rows for a just-created
    project and log its "created" event -- the one piece of project-creation
    logic shared verbatim between the direct API
    (routers/projects.py::create_project) and the deal->won automation
    (deal_rules.py::create_project_from_won_deal). Assumes `project` is
    already flushed (has an id) but not yet committed."""
    for m in instantiate_template(template_key, project.id):
        db.add(m)
    log_event(db, "project", project.id, "created", actor, note=note)
