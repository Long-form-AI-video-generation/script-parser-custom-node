import re

PANEL_DELIMITER = "--- PANEL BREAK ---"

BIBLE_LINE = re.compile(
    r"^(?P<name>[^:(#][^:(]*?)\s*(?:\(aliases?:\s*(?P<aliases>[^)]*)\))?\s*:\s*(?P<desc>.+)$"
)

DEFAULT_BIBLE = (
    "# One character per line. Examples:\n"
    "# Kira (aliases: Operative 3, the scout): slim female operative, matte-black bodysuit, dark red scarf, silver bob haircut, green eyes\n"
    "# Guard bot: gunmetal canine quadruped robot, single cyan optic bar, reinforced front claws\n"
)

LOCATION_RE = re.compile(r"(?im)^\s*LOCATION\s*:\s*(.+?)\s*$")
TRANSITION_RE = re.compile(r"(?im)^\s*TRANSITION\s*:\s*(.+?)\s*$")
SUBJECT_RE = re.compile(r"(?im)^\s*SUBJECT\s*:\s*(.+?)\s*$")
PRONOUN_RE = re.compile(
    r"\b(he|she|they|him|her|them|his|hers|their|same character|same subject)\b",
    re.IGNORECASE,
)


def _normalized_label(pattern, panel):
    match = pattern.search(panel or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1).strip().lower())


def _panel_needs_character_carry(panel):
    subject = _normalized_label(SUBJECT_RE, panel)
    if subject in {"", "none", "environment", "location", "establishing view"}:
        return False
    return bool(PRONOUN_RE.search(subject) or PRONOUN_RE.search(panel))


def parse_bible(text):
    """Returns a list of (names, description) with names = [name, *aliases]."""
    characters = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = BIBLE_LINE.match(line)
        if not m:
            print(f"⚠️ Character Bible: skipping unparseable line: {line[:60]}")
            continue
        names = [m.group("name").strip()]
        if m.group("aliases"):
            names += [a.strip() for a in m.group("aliases").split(",") if a.strip()]
        characters.append((names, m.group("desc").strip()))
    return characters


class CharacterBibleInjector_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "storyboard_text": ("STRING", {"forceInput": True}),
                "character_bible": ("STRING", {"multiline": True, "default": DEFAULT_BIBLE}),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                
                "bible_text": ("STRING", {"forceInput": True}),
                
                "inject_unmatched": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("enriched_storyboard",)
    FUNCTION = "enrich"
    CATEGORY = "Script To Video Suite"

    def enrich(self, storyboard_text, character_bible=None, enabled=True, bible_text=None,
               inject_unmatched=True, **kwargs):
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ Input 'storyboard_text' is empty!")

        if bible_text is None:
            bible_text = kwargs.get("character_bible_text")
        source = bible_text if (bible_text and bible_text.strip()) else character_bible
        characters = parse_bible(source) if enabled else []
        if not characters:
            if enabled:
                print("Character Bible: no characters defined, passing storyboard through.")
            return (storyboard_text,)

        matchers = [
            (re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.IGNORECASE), names[0], desc)
            for names, desc in characters
        ]

        panels = re.split(r"\s*--- PANEL BREAK ---\s*|(?=\bPANEL\s+\d+)", storyboard_text)
        enriched = []
        hits = 0
        carried = 0
        last_lines = []
        last_location = ""
        header = ("CHARACTER_APPEARANCE (use these exact visual descriptors in the "
                  "image_prompt, and keep this character's canonical name in the video_prompt):")

        for panel in panels:
            panel = panel.strip()
            if not panel:
                continue
            location = _normalized_label(LOCATION_RE, panel)
            transition = _normalized_label(TRANSITION_RE, panel)
            hard_cut = "cut" in transition and "continue" not in transition
            location_changed = bool(location and last_location and location != last_location)
            if hard_cut or location_changed:
                last_lines = []
            lines = []
            for pattern, name, desc in matchers:
                if pattern.search(panel):
                    lines.append(f"- {name}: {desc}")
            if lines:
                hits += 1
                last_lines = lines
            elif inject_unmatched and last_lines and _panel_needs_character_carry(panel):
                
                carried += 1
                lines = last_lines
            if lines:
                panel += f"\n{header}\n" + "\n".join(lines)
            enriched.append(panel)
            if location:
                last_location = location

        print(f"📖 Character Bible: enriched {hits}/{len(enriched)} panels "
              f"({carried} carried forward) with {len(characters)} character(s).")
        return (f"\n\n{PANEL_DELIMITER}\n\n".join(enriched),)
