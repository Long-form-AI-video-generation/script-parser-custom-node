import os
import re
import difflib

try:
    import folder_paths
except ImportError:
    folder_paths = None

MAP_LINE = re.compile(
    r"^(?P<name>[^:(#][^:(]*?)\s*(?:\(aliases?:\s*(?P<aliases>[^)]*)\))?\s*:\s*"
    r"(?P<file>[^@]+?)\s*(?:@\s*(?P<strength>[\d.]+))?$"
)

DEFAULT_MAP = (
    "# One character per line. Examples:\n"
    "# Kira (aliases: Operative 3): kira_character_v2.safetensors @ 0.8\n"
    "# Isaac: isaac_15.safetensors\n"
    "# Isaac: isaac_15.safetensors @ 1.0 | trigger: tr1gger_token\n"
)


def parse_lora_map(text):
    """Returns a list of (names, lora_file, strength, trigger); trigger may be None."""
    entries = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        head, _, tail = line.partition("|")
        m = MAP_LINE.match(head.strip())
        if not m:
            print(f"⚠️ Character LoRA: skipping unparseable line: {line[:60]}")
            continue
        trigger = None
        if tail.strip():
            t = re.match(r"\s*trigger\s*:\s*(.+)", tail, re.IGNORECASE)
            if t:
                trigger = t.group(1).strip()
            else:
                print(f"⚠️ Character LoRA: ignoring unrecognized suffix after '|': {tail.strip()[:40]}")
        names = [m.group("name").strip()]
        if m.group("aliases"):
            names += [a.strip() for a in m.group("aliases").split(",") if a.strip()]
        strength = float(m.group("strength")) if m.group("strength") else 1.0
        entries.append((names, m.group("file").strip(), strength, trigger))
    return entries


def inject_triggers(prompt, triggers):
    """Prepends each trigger to the prompt unless it's already present (case-insensitive)."""
    prompt = prompt or ""
    lowered = prompt.lower()
    new = []
    for trigger in triggers:
        if trigger and trigger.lower() not in lowered and trigger.lower() not in (t.lower() for t in new):
            new.append(trigger)
    if not new:
        return prompt
    return ", ".join(new) + ", " + prompt if prompt else ", ".join(new)


def resolve_lora_path(lora_file):
    if folder_paths is not None:
        try:
            return folder_paths.get_full_path_or_raise("loras", lora_file)
        except Exception:
            pass
    return lora_file


def _safetensors_header_error(path):
    try:
        size = os.path.getsize(path)
        if size < 8:
            return f"file is only {size} bytes; safetensors files must contain an 8-byte header prefix"

        with open(path, "rb") as f:
            header_size = int.from_bytes(f.read(8), "little")
        if header_size <= 0:
            return "safetensors header length is empty"
        if header_size > size - 8:
            return f"safetensors header claims {header_size} bytes, but file is only {size} bytes"
    except Exception as e:
        return f"could not inspect file ({e})"
    return None


def _normalize_name(text):
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def _matched_name(names, prompt, match_mode="fuzzy"):
    prompt = prompt or ""
    for name in names:
        pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
        if pattern.search(prompt):
            return name

    prompt_words = {
        _normalize_name(word): word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", prompt)
    }
    for name in names:
        normalized = _normalize_name(name)
        if not normalized:
            continue
        if normalized in prompt_words:
            return name
        if match_mode == "fuzzy" and len(normalized) >= 4:
            matches = difflib.get_close_matches(normalized, prompt_words.keys(), n=1, cutoff=0.8)
            if matches:
                return f"{name}~{prompt_words[matches[0]]}"
    return None


class CharacterLoraSelect_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "lora_map": ("STRING", {"multiline": True, "default": DEFAULT_MAP}),
            },
            "optional": {
                "prev_lora": ("WANVIDLORA",),
                # "exact" disables fuzzy (difflib) matching — recommended, avoids
                # near-miss tokens pulling in the wrong character LoRA.
                "match_mode": (["fuzzy", "exact"], {"default": "fuzzy"}),
                # When connected and non-empty, overrides the lora_map widget.
                # Wire the Character Extractor's lora_map_text here so the map
                # lives in one place (character_bible.json).
                "lora_map_override": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("WANVIDLORA", "STRING", "STRING")
    RETURN_NAMES = ("lora", "matched_info", "prompt_with_trigger")
    FUNCTION = "select"
    CATEGORY = "Script To Video Suite"

    def select(self, prompt, lora_map, prev_lora=None, match_mode="fuzzy", lora_map_override=None):
        loras = list(prev_lora) if prev_lora else []
        matched = []
        triggers = []
        if lora_map_override and lora_map_override.strip():
            lora_map = lora_map_override
        entries = parse_lora_map(lora_map)

        for names, lora_file, strength, trigger in entries:
            hit = _matched_name(names, prompt, match_mode)
            if not hit:
                continue
            path = resolve_lora_path(lora_file)
            if not os.path.isfile(path):
                print(f"Character LoRA: '{names[0]}' matched but file not found: {lora_file}")
                continue
            header_error = _safetensors_header_error(path)
            if header_error:
                print(f"Character LoRA: '{names[0]}' matched but invalid safetensors file '{lora_file}': {header_error}")
                continue
            if any(l.get("path") == path for l in loras):
                continue
            loras.append({
                "path": path,
                "strength": strength,
                "name": os.path.splitext(os.path.basename(lora_file))[0],
                "blocks": {},
                "layer_filter": "",
                "low_mem_load": False,
                # Required by WanVideoSetLoRAs: runtime application, no merging.
                "merge_loras": False,
            })
            if trigger:
                triggers.append(trigger)
            matched.append(f"{names[0]} -> {lora_file} @ {strength} (matched {hit})")

        if matched:
            info = ", ".join(matched)
        elif entries:
            excerpt = " ".join(str(prompt or "").split())[:180]
            info = f"no character LoRA for this shot; prompt='{excerpt}'"
        else:
            info = "no character LoRA for this shot; LoRA map is empty or commented out"
        print(f"🎭 Character LoRA: {info}")
        prompt_with_trigger = inject_triggers(prompt, triggers)
        return (loras, info, prompt_with_trigger)
