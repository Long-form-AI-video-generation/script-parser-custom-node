
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
            raise ValueError(" Input 'storyboard_text' is empty!")

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
        header = ("CHARACTER_APPEARANCE (use these exact visual descriptors in the "
                  "image_prompt, and keep this character's canonical name in the video_prompt):")

        for panel in panels:
            panel = panel.strip()
            if not panel:
                continue
            lines = []
            for pattern, name, desc in matchers:
                if pattern.search(panel):
                    lines.append(f"- {name}: {desc}")
            if lines:
                hits += 1
                last_lines = lines
            elif inject_unmatched and last_lines:
                
                carried += 1
                lines = last_lines
            if lines:
                panel += f"\n{header}\n" + "\n".join(lines)
            enriched.append(panel)

        print(f"📖 Character Bible: enriched {hits}/{len(enriched)} panels "
              f"({carried} carried forward) with {len(characters)} character(s).")
        return (f"\n\n{PANEL_DELIMITER}\n\n".join(enriched),)
