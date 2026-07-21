import re


ANIME_IMAGE_PREFIX = (
    "STRICT 2D ANIME KEYFRAME, Japanese TV anime screenshot, hand-drawn cel animation, "
    "clean black ink lineart, flat cel-shaded colors, simplified anime skin, stylized anime faces, "
    "large expressive anime eyes when faces are visible, painterly anime background, animation production still, "
    "same anime character design"
)

ANIME_VIDEO_PREFIX = (
    "Continue as strict 2D Japanese TV anime cel animation with the same hand-drawn character designs, "
    "same flat colors, same ink outlines, same anime character proportions, same outfit design."
)

REALISM_TERMS = (
    "photorealistic", "photorealism", "photo realistic", "hyperrealistic", "realistic", "realism",
    "live action", "live-action", "film still", "camera photo look", "camera photo", "photo look",
    "photographic look", "film look", "realistic look", "photograph",
    "photography", "DSLR", "real person", "real people", "real human", "human actor", "cosplay",
    "cinematic realism", "realistic face", "realistic skin", "skin pores",
    "natural skin texture", "documentary", "news footage", "3d render", "3D render",
    "3d", "3D", "CGI", "game cinematic", "semi-realistic", "uncanny valley",
)


def _clean_prompt(text):
    text = str(text or "")
    for term in sorted(REALISM_TERMS, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(term)}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcinematic still\b", "anime keyframe", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*,+", ", ", text)
    text = re.sub(r"\b(?:no|not|never)\s+(?:a\s+|an\s+)?(?=,|\.|$)", "", text, flags=re.IGNORECASE)
    text = ", ".join(
        part.strip()
        for part in text.split(",")
        if part.strip() and not re.fullmatch(r"(?i)(?:no|not|never|a|an|the|\s)+", part.strip())
    )
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    return text


def _guard_image_prompt(prompt, style_prefix):
    prompt = _clean_prompt(prompt)
    if prompt.lower().startswith("strict 2d anime keyframe"):
        return prompt
    if not prompt:
        return style_prefix
    return f"STRICT 2D ANIME FRAME OF THIS STORY BEAT: {prompt}. STYLE LOCK: {style_prefix}"


def _guard_video_prompt(prompt, style_prefix, video_prefix):
    prompt = _clean_prompt(prompt)
    if prompt:
        guarded = f"NEXT STORY BEAT IN STRICT 2D ANIME: {prompt}. STYLE LOCK: {style_prefix}. Motion style: {video_prefix}"
    else:
        guarded = f"NEXT STORY BEAT IN STRICT 2D ANIME. STYLE LOCK: {style_prefix}. Motion style: {video_prefix}"
    return guarded


class AnimePromptGuard_S2V:
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "first_image_prompt": ("STRING", {"forceInput": True}),
                "first_video_prompt": ("STRING", {"forceInput": True}),
                "all_video_prompts": ("PROMPTS_LIST",),
                "style_prefix": ("STRING", {"multiline": True, "default": ANIME_IMAGE_PREFIX}),
                "video_prefix": ("STRING", {"multiline": True, "default": ANIME_VIDEO_PREFIX}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "PROMPTS_LIST")
    RETURN_NAMES = ("first_image_prompt", "first_video_prompt", "all_video_prompts")
    FUNCTION = "guard_prompts"
    CATEGORY = "Script To Video Suite/Execution"

    def guard_prompts(self, first_image_prompt, first_video_prompt, all_video_prompts,
                      style_prefix=ANIME_IMAGE_PREFIX, video_prefix=ANIME_VIDEO_PREFIX):
        style_prefix = _clean_prompt(style_prefix) or ANIME_IMAGE_PREFIX
        video_prefix = _clean_prompt(video_prefix) or ANIME_VIDEO_PREFIX

        guarded_first_image = _guard_image_prompt(first_image_prompt, style_prefix)
        guarded_first_video = _guard_video_prompt(first_video_prompt, style_prefix, video_prefix)
        guarded_all_video = [
            _guard_video_prompt(prompt, style_prefix, video_prefix)
            for prompt in (all_video_prompts or [])
        ]

        print(f"🎨 Anime Prompt Guard: locked {len(guarded_all_video)} video prompts to 2D anime.")
        return (guarded_first_image, guarded_first_video, guarded_all_video)
