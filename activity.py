"""Intent badges, not proof that a provider/tool has run or an action succeeded."""
import re

# Order favors the requested operation over objects mentioned in its body.
RULES = (
    ('email', r'\b(gmail|e-?mails?|inbox)\b'),
    ('calendar', r'\b(calendar|appointments?|meetings?|schedule|agenda)\b'),
    ('reminder', r'\b(remind(?:er|ers)?|timesheet|to-?do)\b'),
    ('home', r'\b(lights?|home assistant|garage|thermostat|kitchen|hallway|bedroom|smart home)\b'),
    ('printing', r'\b(3d|print(?:er|ing)?|bambu|orcaslicer|stl|cad|enclosure)\b'),
    ('coding', r'\b(code|coding|debug|bug|fix|gitlab|github|pull request|deploy|firmware|build|refactor)\b'),
    ('thecam', r'\b(thecam|bookings?|creators?|support tickets?|signups?)\b'),
    ('markets', r'\b(markets?|stocks?|bitcoin|crypto|portfolio|nasdaq|s&p)\b'),
    ('weather', r'\b(weather|forecast|rain|temperature)\b'),
    ('research', r'\b(search|research|find|look up|compare|news|farms?|buy|nearby|youtube)\b'),
)

def classify_activity(text):
    text = (text or '').lower()
    return next((name for name, pattern in RULES if re.search(pattern, text)), 'general')
