"""Build the reproducible, human-authored demo benchmark from source facts."""
import json
from pathlib import Path


# Each question was written against the exact passage below and checked for a
# matching source phrase. The corpus is fictional demo content, not real policy.
FACTS = [
    ("security_policy.md", "within 24 hours of discovery", [
        "By when must an employee report a suspected security incident?",
        "What is the reporting deadline after discovering a possible security incident?",
        "How soon does Security Operations need to hear about an incident?",
        "What time limit applies to reporting suspected security events?",
        "When should staff report a security incident they have discovered?",
    ]),
    ("security_policy.md", "the time observed, the affected system, and a short description", [
        "Which details belong in a suspected incident report?",
        "What information should an employee provide when reporting a security event?",
        "What must be recorded about an incident when it is reported?",
        "Which three details does the incident report need?",
        "What should I include when I notify the security team?",
    ]),
    ("security_policy.md", "Passwords must be at least 14 characters long", [
        "What is the minimum permitted password length?",
        "How many characters must a password contain at minimum?",
        "What password length does the example policy require?",
        "Are passwords shorter than fourteen characters permitted?",
        "How long should an account password be?",
    ]),
    ("security_policy.md", "Multi-factor authentication is required for remote access", [
        "Is multi-factor authentication mandatory when accessing remotely?",
        "What login protection is required for remote access?",
        "Do remote users have to use MFA?",
        "Which authentication requirement applies outside the office?",
        "Is a second authentication factor needed for remote connections?",
    ]),
    ("records_policy.md", "retained for 180 days after closure", [
        "How long are closed support tickets kept?",
        "What is the retention period for a support ticket after closure?",
        "When can a closed support request be deleted?",
        "For how many days are support tickets retained once closed?",
        "How long does the records policy keep completed support cases?",
    ]),
    ("records_policy.md", "retained for 7 years", [
        "How long must security incident records be retained?",
        "What is the retention period for incident records?",
        "When may a security incident record be deleted under the example policy?",
        "For how many years are security event records kept?",
        "How long does the example records policy preserve incident files?",
    ]),
    ("records_policy.md", "retained for 12 months after the hiring decision", [
        "How long are unsuccessful applicants' recruitment records retained?",
        "When can records for applicants who were not hired be deleted?",
        "What is the retention period after a hiring decision for unsuccessful candidates?",
        "For how many months are rejected-candidate records kept?",
        "How long does the example policy preserve unsuccessful applicant files?",
    ]),
    ("records_policy.md", "Legal holds suspend normal deletion schedules", [
        "What effect does a legal hold have on normal deletion?",
        "Are regular deletion schedules followed during a legal hold?",
        "How does a legal hold change records disposal?",
        "What happens to ordinary retention deletion while records are under legal hold?",
        "Does the policy pause deletion when a legal hold applies?",
    ]),
    ("leave_policy.md", "25 days of annual leave per calendar year", [
        "How much annual leave does a full-time employee receive each year?",
        "What is the annual leave allowance for full-time staff?",
        "How many vacation days are provided per calendar year?",
        "What yearly leave entitlement does the example policy set?",
        "How many annual leave days does a full-time worker get?",
    ]),
    ("leave_policy.md", "at least 10 calendar days before the first day requested", [
        "How far ahead should staff submit an annual leave request?",
        "What is the notice period for requesting leave?",
        "When should a vacation request be filed relative to its start date?",
        "How many days in advance should leave be requested?",
        "What lead time does the example policy ask for annual leave?",
    ]),
    ("leave_policy.md", "A maximum of 5 unused days may be carried over, and those days must be used by 31 March", [
        "How many unused annual leave days may be carried forward, and by when must they be used?",
        "What is the leave carryover limit and its expiry date?",
        "How many vacation days can roll into the next year, and when do they expire?",
        "When must carried-over leave be taken?",
        "What happens to unused leave at year end?",
    ]),
    ("leave_policy.md", "notify their manager by 9:00 a.m. local time on the first day of absence", [
        "By what time should an ill employee tell their manager on day one?",
        "When must sickness absence be reported to a manager?",
        "What is the first-day illness notification deadline?",
        "How early does an employee need to notify their manager if sick?",
        "When should staff call in sick on the first day they cannot work?",
    ]),
    ("it_support_policy.md", "within 1 business hour during support hours", [
        "What is the initial response target for a critical incident during support hours?",
        "How quickly should IT first respond to a critical issue?",
        "What response time applies to critical support cases?",
        "When should a critical incident receive its first response?",
        "How long is the target initial response for a critical IT incident?",
    ]),
    ("it_support_policy.md", "within 2 business days", [
        "What is the initial response target for a standard service request?",
        "How soon should IT first respond to a normal service request?",
        "What response time applies to non-critical service requests?",
        "When should a standard request receive its first reply?",
        "How many business days is the standard response target?",
    ]),
    ("it_support_policy.md", "lock automatically after 5 minutes of inactivity", [
        "After how long should a managed device lock itself when idle?",
        "What is the automatic screen-lock timeout for managed devices?",
        "How many inactive minutes are allowed before a device locks?",
        "When should a managed computer's idle lock activate?",
        "What inactivity timeout does the device policy require?",
    ]),
    ("it_support_policy.md", "installed within 14 calendar days of release", [
        "How soon must critical security updates be installed?",
        "What is the deadline for installing a critical update after release?",
        "Within how many days should a critical security patch be applied?",
        "When must critical updates reach managed devices?",
        "What update installation window does the example IT policy set?",
    ]),
    ("travel_policy.md", "at least 14 calendar days before departure", [
        "How early should business travel be booked when practical?",
        "What advance booking period does the travel policy recommend?",
        "How many days before departure should a trip be arranged?",
        "When should employees book a business trip?",
        "What is the recommended lead time for travel reservations?",
    ]),
    ("travel_policy.md", "A manager must approve travel before any booking is made", [
        "Who must approve a trip, and when must approval happen?",
        "Can employees book business travel before manager approval?",
        "What approval is needed before making a travel reservation?",
        "When does a manager need to sign off on travel?",
        "Is prior manager approval required for bookings?",
    ]),
    ("travel_policy.md", "Itemised receipts are required for expenses greater than €25", [
        "When does a travel expense require an itemised receipt?",
        "What is the receipt threshold for expenses?",
        "Do claims above 25 euros need itemised receipts?",
        "Which expenses must be supported by an itemised receipt?",
        "At what amount does the travel policy require a receipt?",
    ]),
    ("travel_policy.md", "reimbursed at €0.35 per kilometre", [
        "What rate applies to approved personal-car business mileage?",
        "How much is reimbursed for each business kilometre driven in a personal vehicle?",
        "What is the mileage reimbursement rate?",
        "How is approved personal vehicle travel compensated per kilometre?",
        "What amount can an employee claim per kilometre for business driving?",
    ]),
]

UNANSWERABLE = [
    "What is the company's headquarters street address?",
    "Who is the current chief executive?",
    "Which health insurer covers employees?",
    "What is the approved hotel price cap for business trips?",
    "How many employees work for the organisation?",
    "What is the office cafeteria menu today?",
    "Which vendor provides the payroll system?",
    "What is the employee bonus percentage this year?",
    "Where is the nearest fire extinguisher in the office?",
    "When is the next company-wide town hall?",
    "What is the company tax identification number?",
    "Which bank account receives customer payments?",
    "What is the current stock price of the company?",
    "Who won the internal football tournament?",
    "What is the guest Wi-Fi password?",
    "How many vacation days does a part-time employee receive?",
    "Which airline should employees use for long-haul flights?",
    "What is the exact date of the next security audit?",
    "Does the policy reimburse home internet bills?",
    "What is the required office dress code?",
]


def build() -> list[dict]:
    rows = []
    for fact_no, (source, expected, questions) in enumerate(FACTS, start=1):
        for variant, question in enumerate(questions, start=1):
            rows.append({"id": f"q{fact_no:02d}-{variant}", "question": question,
                         "relevant_sources": [source], "answerable": True, "expected_answer": expected})
    for index, question in enumerate(UNANSWERABLE, start=1):
        rows.append({"id": f"u{index:02d}", "question": question,
                     "relevant_sources": [], "answerable": False})
    return rows


if __name__ == "__main__":
    output = Path(__file__).with_name("questions.jsonl")
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in build()), encoding="utf-8")
    print(f"Wrote {len(build())} questions to {output}")
