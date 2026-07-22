from pathlib import Path

import yaml


REQUIRED_ACTIONS = {
    "discover_partners",
    "research_company",
    "accept_evidence",
    "score_company",
    "identify_contact",
    "generate_outreach",
    "send_email",
    "classify_reply",
    "propose_meeting",
    "create_calendar_event",
    "create_meeting_brief",
}

policy = yaml.safe_load(Path("policies/autonomy.yaml").read_text())
assert policy["defaults"]["decision"] == "DENY", "Policy must default to DENY"
missing = REQUIRED_ACTIONS - set(policy["actions"])
assert not missing, f"Missing governed actions: {sorted(missing)}"
for name, rule in policy["actions"].items():
    assert rule.get("risk") in {"low", "medium", "high"}, f"Invalid risk for {name}"
    assert rule.get("requirements"), f"Action {name} has no authorization requirements"
print(f"Validated {len(policy['actions'])} autonomous ArmorIQ action policies")
