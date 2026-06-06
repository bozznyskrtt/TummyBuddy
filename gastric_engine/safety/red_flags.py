"""Safety red-flag checks for reported symptoms."""

RED_FLAGS = {
    "blood_in_vomit": "Blood in vomit can indicate bleeding and needs urgent care.",
    "black_stool": "Black stool can indicate gastrointestinal bleeding and needs urgent care.",
    "severe_chest_pain": "Severe chest pain should be assessed urgently.",
}


def safety_flags(symptoms_reported: dict | None) -> list[dict]:
    symptoms_reported = symptoms_reported or {}
    flags = []
    for key, message in RED_FLAGS.items():
        if symptoms_reported.get(key):
            flags.append(
                {
                    "code": key,
                    "urgency": "urgent",
                    "message": message,
                }
            )
    return flags
