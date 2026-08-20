"""Business-model taxonomy (Executive Discovery, Milestone 1,
docs/EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md) -- a real, stated, editable
list of business models ATLAS should compare before committing to any
one, independent of which of them ATLAS already has execution capability
for.

Deliberately NOT atlas.brain.confidence.CATEGORY_TASK_CATEGORIES -- that
map is scoped to what ATLAS can already dispatch a Task to, which is
exactly the capability-bounded anchoring bug this taxonomy exists to
break (docs/ATLAS_V1_FAILURE_ANALYSIS.md, Failure 1/2: v1 anchored on
Keto/Digistore24 without ever comparing against the wider field, and
even the categories it *could* evaluate were bounded by what already had
a dispatchable channel).

Same "stated, editable assumption" class as confidence.WEIGHTS /
influencer.factory.MARKET_LOCALE / affiliate_pipeline_advance.
ASSUMED_MONTHLY_LEADS -- not sacred, revisit as real evidence accumulates
about which models actually matter.
"""

BUSINESS_MODEL_CATEGORIES = [
    "affiliate",
    "digital_product",
    "content",
    "recruitment",
    "youtube",
    "ugc",
    "saas",
    "marketplace",
    "community",
    "email_marketing",
    "tiktok",
    "instagram",
    "service_business",
    "ecommerce",
]

# How many DISTINCT categories above must individually clear the same
# evidence bar decision_engine.MIN_INDEPENDENT_SOURCES already applies
# per-category, before Executive Decision is allowed to commit to ANY of
# them (Exploration Before Commitment, docs/EXECUTIVE_DISCOVERY_DESIGN_
# REVIEW.md Mechanism 1). A real, stated, editable number -- not sacred.
MIN_CATEGORIES_EXPLORED = 5

# How many times ATLAS will auto-trigger real research for one category
# before giving up on it for now and rendering an honest
# "insufficient_evidence_after_research" verdict instead of looping
# forever (Research Completion Threshold, Mechanism 3) -- the explicit
# stopping rule Mechanism 1+2's loop needs, per docs/
# EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md.
MAX_RESEARCH_ATTEMPTS = 3
