# Re-gen Environmental Activity Verification Rules
Version: MVP 1.0

## Purpose

These rules define the minimum information required before an
environmental activity can be forwarded to a human field verifier.

The AI agent does not approve or reject environmental activities.
Final verification is performed by an authorized human field verifier.

---

## Tree Planting

Activity type: tree_planting

Required information:

- activity type
- number of seedlings planted
- activity date
- planting location
- evidence of the activity

Optional information:

- exact species name
- species category
- additional field notes
- GPS coordinates
- photo captions
- geotagging information

Evidence:

At least one piece of activity evidence should be reported.

Photographs may be reported as evidence.

The AI must not claim to have inspected photographs unless the image
files were actually supplied to the system.

If the required information is complete:

Recommendation:
READY_FOR_HUMAN_REVIEW

If required information is missing:

Recommendation:
NEEDS_CLARIFICATION

If submitted information conflicts:

Recommendation:
FLAG_FOR_REVIEW

Example conflict:

The activity description states that 100 seedlings were planted while
another submitted record states 150 seedlings.

---

## Seedling Production

Activity type: seedling_production

Required information:

- activity type
- number of seedlings produced
- activity date
- nursery or production location

Optional information:

- species
- batch identifier
- evidence photographs
- production notes

Missing required information should result in:

NEEDS_CLARIFICATION

---

## Nursery Maintenance

Activity type: nursery_maintenance

Required information:

- maintenance activity performed
- activity date
- nursery location

Examples of nursery maintenance include:

- watering
- weeding
- potting
- seedbed preparation
- seedling care

Quantity is optional unless the maintenance activity specifically
involves a measurable quantity of seedlings.

---

## Site Preparation

Activity type: site_preparation

Required information:

- type of site preparation
- activity date
- site location

Examples:

- clearing
- hole preparation
- layout preparation

Evidence may be requested according to programme procedures.

---

## Human Verification

The Re-gen AI agent must never return:

VERIFIED
APPROVED
REJECTED
REWARDED

as an authoritative decision.

The valid AI recommendations are only:

NEEDS_CLARIFICATION
READY_FOR_HUMAN_REVIEW
FLAG_FOR_REVIEW

Final approval or rejection belongs to the human field verifier.

---

## Green Merit Rewards

The AI agent must not calculate or issue Green Merit points or tokens.

Green Merit calculations may only occur after human verification and
must be performed using deterministic programme rules.