"""Question preparation is separate from diagnosis and repair instructions."""
from shared.models import MechanicQuestionDraft


DETAILS_TO_NOTE = [
    'Describe what you have already noticed: when it happens, warning messages, sounds or smells. Do not recreate the problem.',
    'Bring any existing photos, service records or details of recent work. Take photos only when safely parked.',
    'Tell the workshop which information you could not confirm and what you want explained.',
]


def general_questions(question):
    summary = question if len(question) <= 600 else question[:597] + '...'
    return MechanicQuestionDraft(concern_summary=summary, questions=[
        {'question': 'Based on the concern I have described, what would you inspect first, and why?',
         'reason': 'Understand how the mechanic will investigate before assuming a cause.'},
        {'question': 'Does this need inspection before I drive again, or should I arrange recovery?',
         'reason': 'Ask a professional about the next safe step for this particular situation.'},
        {'question': 'Which checks or measurements would help confirm the cause?',
         'reason': 'Ask what evidence would support the diagnosis.'},
        {'question': 'Which manufacturer instructions or specifications apply to my exact vehicle?',
         'reason': 'Confirm the correct reference rather than relying on an uncertain value.'},
        {'question': 'What work is necessary, what can wait, and can I have an itemized estimate before work begins?',
         'reason': 'Understand the proposed work and its cost before deciding.'},
    ])


def vehicle_summary(profile):
    if not profile:
        return 'No active vehicle selected. Tell the workshop your vehicle model and year.'
    identity = ' '.join(str(profile.get(field) or '') for field in
                        ('year', 'manufacturer', 'model', 'variant', 'engine')).strip()
    return f"{profile['name']} — {identity or profile['catalogue_name']}; recorded odometer: {profile['mileage_km']} km"
