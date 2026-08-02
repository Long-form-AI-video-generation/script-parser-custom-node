import json
import re


TRANSITION_ALIASES = {
    "continue": "continue",
    "continuation": "continue",
    "continuous": "continue",
    "same shot": "continue",
    "same scene": "continue",
    "cut": "cut",
    "hard cut": "cut",
    "scene cut": "cut",
    "new scene": "cut",
    "match cut": "match_cut",
    "match_cut": "match_cut",
}

STYLE_NOISE = {
    "strict", "japanese", "anime", "keyframe", "hand", "drawn", "cel",
    "animation", "clean", "black", "ink", "lineart", "flat", "shaded",
    "colors", "stylized", "faces", "simplified", "skin", "tones",
    "painterly", "background", "cinematic", "composition", "same",
    "character", "design", "single", "coherent", "shot",
    "polished", "full", "color", "painted", "fantasy", "warm", "whimsical",
    "classic", "studio", "ghibli", "inspired",
    "storybook", "rich", "opaque", "gouache", "watercolor", "natural",
    "sunlight", "atmospheric", "depth", "rounded", "delicate", "colored",
    "contours", "soft", "tonal", "variation", "tactile", "organic",
    "textures", "finished", "theatrical", "still",
}

REALISM_RE = re.compile(
    r"\b(photoreal(?:istic|ism)?|live[- ]action|photograph(?:y|ic)?|dslr|"
    r"real(?:istic)? (?:person|human|skin|face)|cosplay|cgi|3d render|"
    r"documentary|film still)\b",
    re.IGNORECASE,
)


def normalize_transition(value, default="cut"):
    raw = re.sub(r"[_-]+", " ", str(value or "").strip().lower())
    if not raw:
        return default
    if raw in TRANSITION_ALIASES:
        return TRANSITION_ALIASES[raw]
    if "match" in raw and "cut" in raw:
        return "match_cut"
    if "continu" in raw or "same scene" in raw:
        return "continue"
    return "cut"


def _prompt_tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) > 2 and token not in STYLE_NOISE
    }


def _jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


class ShotPlanValidator_S2V:
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_json": ("STRING", {"multiline": True, "forceInput": True}),
                "auto_repair": ("BOOLEAN", {"default": True}),
                "strict": ("BOOLEAN", {"default": False}),
                "duplicate_threshold": (
                    "FLOAT",
                    {"default": 0.82, "min": 0.5, "max": 1.0, "step": 0.01},
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("validated_prompts", "quality_report", "shot_count", "cut_count")
    FUNCTION = "validate"
    CATEGORY = "Script To Video Suite/Planning"

    def validate(self, prompt_json, auto_repair=True, strict=False, duplicate_threshold=0.82):
        cleaned = str(prompt_json or "").replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Shot Plan Validator: invalid JSON: {exc}") from exc

        panels = data.get("panels")
        if not isinstance(panels, list) or not panels:
            raise ValueError("Shot Plan Validator: 'panels' must be a non-empty array.")

        warnings = []
        repaired = []
        previous_scene = ""
        previous_image_tokens = set()
        previous_video_tokens = set()
        cut_count = 0

        for index, raw_panel in enumerate(panels):
            if not isinstance(raw_panel, dict):
                raise ValueError(f"Shot Plan Validator: panel {index + 1} is not an object.")

            panel = dict(raw_panel)
            image_prompt = str(panel.get("image_prompt") or "").strip()
            video_prompt = str(panel.get("video_prompt") or "").strip()
            if not image_prompt or not video_prompt:
                raise ValueError(
                    f"Shot Plan Validator: panel {index + 1} needs image_prompt and video_prompt."
                )

            transition = normalize_transition(
                panel.get("transition_type", panel.get("transition")),
                default="cut",
            )
            scene_id = re.sub(
                r"[^A-Za-z0-9_.-]+",
                "_",
                str(panel.get("scene_id") or "").strip(),
            ).strip("_")

            if index == 0:
                transition = "cut"
                scene_id = scene_id or "scene_001"
            elif transition == "continue":
                scene_id = scene_id or previous_scene
                if previous_scene and scene_id != previous_scene:
                    warnings.append(
                        f"shot {index + 1}: CONTINUE changed scene_id; repaired to CUT"
                    )
                    transition = "cut"
            else:
                scene_id = scene_id or f"scene_{index + 1:03d}"

            if transition != "continue":
                cut_count += 1

            if REALISM_RE.search(image_prompt) or REALISM_RE.search(video_prompt):
                warnings.append(f"shot {index + 1}: realism language remains in a positive prompt")

            image_tokens = _prompt_tokens(image_prompt)
            video_tokens = _prompt_tokens(video_prompt)
            if index > 0:
                image_similarity = _jaccard(previous_image_tokens, image_tokens)
                video_similarity = _jaccard(previous_video_tokens, video_tokens)
                if image_similarity >= duplicate_threshold and video_similarity >= duplicate_threshold:
                    warnings.append(
                        f"shot {index + 1}: adjacent prompts look duplicated "
                        f"(image={image_similarity:.2f}, motion={video_similarity:.2f})"
                    )

            if auto_repair:
                panel["panel_number"] = index + 1
                panel["scene_id"] = scene_id
                panel["transition_type"] = transition
                panel["image_prompt"] = image_prompt
                panel["video_prompt"] = video_prompt

            repaired.append(panel)
            previous_scene = scene_id
            previous_image_tokens = image_tokens
            previous_video_tokens = video_tokens

        report_lines = [
            f"Shot plan: {len(repaired)} shots, {cut_count} cuts, "
            f"{len(repaired) - cut_count} continuations."
        ]
        if warnings:
            report_lines.extend(f"WARNING: {message}" for message in warnings)
        else:
            report_lines.append("No structural, realism, or adjacent-duplicate warnings.")

        if strict and warnings:
            raise ValueError("Shot Plan Validator strict mode failed:\n" + "\n".join(report_lines))

        data["panels"] = repaired
        result = json.dumps(data, indent=2, ensure_ascii=False) if auto_repair else cleaned
        report = "\n".join(report_lines)
        print(f"Shot Plan Validator: {report_lines[0]}")
        for warning in warnings:
            print(f"Shot Plan Validator WARNING: {warning}")
        return (result, report, len(repaired), cut_count)


class ShotStartRouter_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "generated_keyframe": ("IMAGE",),
                "previous_frame": ("IMAGE",),
                "transition_mode": ("STRING", {"forceInput": True}),
                "allow_continuations": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "BOOLEAN", "STRING")
    RETURN_NAMES = ("start_image", "secondary_reference", "is_hard_cut", "transition")
    FUNCTION = "route"
    CATEGORY = "Script To Video Suite/Execution"

    def route(self, generated_keyframe, previous_frame, transition_mode, allow_continuations=True):
        transition = normalize_transition(transition_mode, default="cut")
        use_previous = allow_continuations and transition == "continue"
        if use_previous:
            start_image = previous_frame
            secondary_reference = generated_keyframe
            is_hard_cut = False
        else:
            start_image = generated_keyframe
            secondary_reference = previous_frame
            is_hard_cut = True
            if transition == "continue":
                transition = "cut"

        print(
            f"Shot Start Router: {transition}; "
            f"start={'previous final frame' if use_previous else 'fresh generated keyframe'}."
        )
        return (start_image, secondary_reference, is_hard_cut, transition)
