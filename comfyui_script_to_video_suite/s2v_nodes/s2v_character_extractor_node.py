
import os
import re
import json
from .gemini_relay_client import ask_gemini_via_relay
from . import llm_cache

BIBLE_DIR = os.path.join(os.path.dirname(__file__), "character_bibles")

DEFAULT_EXTRACTION_PROMPT = (
    "You are a character designer's assistant. Read the following script excerpt and list "
    "EVERY character that appears or is mentioned.\n"
    "For each character provide:\n"
    "- name: the most common name used for them\n"
    "- aliases: other names, titles or descriptions the script uses for the same character\n"
    "- appearance: ONE dense line (max ~25 words) of PERMANENT visual traits: species/age "
    "impression, build, hair, eyes, signature outfit and colors. If the script does not "
    "describe them, invent a plausible, consistent design that fits the story.\n\n"
    "Output ONLY this JSON, nothing else:\n"
    '{"characters": [{"name": "...", "aliases": ["..."], "appearance": "..."}]}'
)


def _extract_json(text):
    cleaned = text.replace("```json", "").replace("```", "").strip()
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", cleaned):
        try:
            obj, _ = decoder.raw_decode(cleaned[m.start():])
            if isinstance(obj, dict) and isinstance(obj.get("characters"), list):
                return obj
        except Exception:
            continue
    return None


CURATED_FIELDS = ("canonical_appearance", "lora_trigger", "lora_file", "lora_strength")


def _normalize(char):
    name = str(char.get("name", "")).strip()
    aliases = [str(a).strip() for a in (char.get("aliases") or []) if str(a).strip()]
    appearance = str(char.get("appearance", "")).strip()
    if not name or not appearance:
        return None
    normalized = {"name": name, "aliases": aliases, "appearance": appearance}
    for field in CURATED_FIELDS:
        if char.get(field) not in (None, ""):
            normalized[field] = char[field]
    return normalized


def effective_appearance(char):
    
    return str(char.get("canonical_appearance") or char.get("appearance") or "").strip()


def merge_characters(existing, new):
 
    index = {}
    for c in existing:
        index[c["name"].lower()] = c
        for a in c.get("aliases", []):
            index[a.lower()] = c

    for raw in new:
        nc = _normalize(raw)
        if nc is None:
            continue
        hit = index.get(nc["name"].lower()) or next(
            (index[a.lower()] for a in nc["aliases"] if a.lower() in index), None)
        if hit is not None:
            known = {hit["name"].lower()} | {a.lower() for a in hit.get("aliases", [])}
            for a in [nc["name"]] + nc["aliases"]:
                if a.lower() not in known:
                    hit.setdefault("aliases", []).append(a)
                    index[a.lower()] = hit
        else:
            existing.append(nc)
            index[nc["name"].lower()] = nc
            for a in nc["aliases"]:
                index[a.lower()] = nc
    return existing


def bible_to_lines(characters):
    lines = []
    for c in characters:
        alias_part = f" (aliases: {', '.join(c['aliases'])})" if c.get("aliases") else ""
        lines.append(f"{c['name']}{alias_part}: {effective_appearance(c)}")
    return "\n".join(lines)


def bible_to_lora_map(characters):
   
    lines = []
    for c in characters:
        lora_file = str(c.get("lora_file") or "").strip()
        if not lora_file:
            continue
        alias_part = f" (aliases: {', '.join(c['aliases'])})" if c.get("aliases") else ""
        try:
            strength = float(c.get("lora_strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        line = f"{c['name']}{alias_part}: {lora_file} @ {strength}"
        trigger = str(c.get("lora_trigger") or "").strip()
        if trigger:
            line += f" | trigger: {trigger}"
        lines.append(line)
    return "\n".join(lines)


class CharacterExtractor_S2V:
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "chunks": ("CHUNKS",),
                "bible_file": ("STRING", {
                    "default": "character_bible.json",
                    "tooltip": "JSON file the cast is saved to and reused from. Relative names "
                               "are stored in s2v_nodes/character_bibles/. Existing characters "
                               "keep their saved appearance across episodes.",
                }),
            },
            "optional": {
                "extraction_prompt": ("STRING", {"multiline": True, "default": DEFAULT_EXTRACTION_PROMPT}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("bible_text", "bible_json", "character_count", "lora_map_text")
    FUNCTION = "extract_characters"
    CATEGORY = "Script To Video Suite"

    def _bible_path(self, bible_file):
        bible_file = (bible_file or "character_bible.json").strip()
        if not bible_file.lower().endswith(".json"):
            bible_file += ".json"
        if os.path.isabs(bible_file):
            return bible_file
        os.makedirs(BIBLE_DIR, exist_ok=True)
        return os.path.join(BIBLE_DIR, bible_file)

    def _extract_from_chunks(self, chunks, extraction_prompt):
        
        cached = llm_cache.load("characters", extraction_prompt, *chunks)
        if cached is not None:
            print("♻️ Character extraction loaded from disk cache.")
            return cached

        found = []
        for i, chunk in enumerate(chunks):
            known = ", ".join(c["name"] for c in found)
            known_hint = (f"\n\nKNOWN CHARACTERS SO FAR: {known}. Reuse these exact names for the "
                          "same characters instead of inventing variants.") if known else ""
            print(f"🎭 Character Extractor: scanning chunk {i+1}/{len(chunks)}...", flush=True)

            data = None
            for attempt in range(2):
                correction = "" if attempt == 0 else (
                    "\n\nCRITICAL: Your previous response was not valid JSON. Output ONLY the JSON object.")
                response = ask_gemini_via_relay(
                    f"{extraction_prompt}{known_hint}{correction}\n\n### SCRIPT EXCERPT:\n{chunk}")
                if response.startswith("Error:"):
                    raise RuntimeError(f"RELAY FAILURE on chunk {i+1}: {response}")
                data = _extract_json(response)
                if data is not None:
                    break
            if data is None:
                print(f"Chunk {i+1}: could not parse character JSON, skipping this chunk.")
                continue
            merge_characters(found, data["characters"])

        llm_cache.save("characters", found, extraction_prompt, *chunks)
        return found

    def extract_characters(self, chunks, bible_file, extraction_prompt=DEFAULT_EXTRACTION_PROMPT):
        if not chunks:
            raise ValueError("Input 'chunks' is empty!")

        path = self._bible_path(bible_file)
        existing = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f).get("characters", [])
                print(f"📖 Loaded existing bible with {len(existing)} character(s): {path}")
            except Exception as e:
                print(f"Could not read existing bible ({e}); starting fresh.")

        found = self._extract_from_chunks(chunks, extraction_prompt)
        characters = merge_characters(existing, found)

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"characters": characters}, f, indent=2, ensure_ascii=False)
        print(f"Character bible saved: {len(characters)} character(s) -> {path}")

        return (bible_to_lines(characters),
                json.dumps({"characters": characters}, indent=2, ensure_ascii=False),
                len(characters),
                bible_to_lora_map(characters))
