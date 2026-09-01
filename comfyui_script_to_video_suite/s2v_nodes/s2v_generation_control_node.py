import re


class GenerationFolder_S2V:
    """Build every video filename prefix from one relative output folder."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_name": (
                    "STRING",
                    {
                        "default": "generation",
                        "multiline": False,
                        "tooltip": "Relative folder under ComfyUI/output. Example: aug_10_run_01",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "root_folder",
        "seed_prefix",
        "first_section_prefix",
        "loop_section_prefix",
        "final_video_prefix",
    )
    FUNCTION = "build"
    CATEGORY = "Script To Video Suite"

    @staticmethod
    def _clean_folder(folder_name):
        value = str(folder_name or "").strip().replace("\\", "/")
        if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
            raise ValueError("Generation folder must be a non-empty relative path.")

        parts = []
        for raw_part in value.split("/"):
            part = raw_part.strip()
            if not part or part == ".":
                continue
            if part == "..":
                raise ValueError("Generation folder cannot contain '..'.")
            part = re.sub(r"[^A-Za-z0-9._ -]+", "_", part).strip(" .")
            if not part:
                raise ValueError("Generation folder contains an invalid path component.")
            parts.append(part)

        if not parts:
            raise ValueError("Generation folder must contain at least one valid name.")
        return "/".join(parts)

    def build(self, folder_name):
        root = self._clean_folder(folder_name)
        print(f"Generation output folder: output/{root}/", flush=True)
        return (
            root,
            f"{root}/seed/seed",
            f"{root}/sections/first",
            f"{root}/sections/loop",
            f"{root}/final/video",
        )
