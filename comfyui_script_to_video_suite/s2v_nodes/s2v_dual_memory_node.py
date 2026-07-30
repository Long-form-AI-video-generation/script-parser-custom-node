class DualMemorySelector_S2V:
    

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "context_size": (
                    "INT",
                    {"default": 2, "min": 1, "max": 32, "step": 1},
                ),
                "shot_length": (
                    "INT",
                    {"default": 49, "min": 1, "max": 1024, "step": 1},
                ),
                "shot_anchor_offset": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1023, "step": 1},
                ),
                "shot_memory_size": (
                    "INT",
                    {"default": 2, "min": 0, "max": 32, "step": 1},
                ),
                "temporal_memory_size": (
                    "INT",
                    {"default": 0, "min": 0, "max": 32, "step": 1},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("context_images",)
    FUNCTION = "select"
    CATEGORY = "Script To Video Suite/Execution"

    def select(
        self,
        images,
        context_size=2,
        shot_length=49,
        shot_anchor_offset=0,
        shot_memory_size=2,
        temporal_memory_size=0,
    ):
        if images is None or images.shape[0] == 0:
            raise ValueError("Dual Memory Selector needs at least one image.")

        total = int(images.shape[0])
        context_size = max(1, min(int(context_size), total))
        shot_length = max(1, int(shot_length))
        shot_anchor_offset = max(0, int(shot_anchor_offset))
        shot_memory_size = max(0, int(shot_memory_size))
        temporal_memory_size = max(
            0,
            min(int(temporal_memory_size), context_size, total),
        )

        recent_start = total - temporal_memory_size
        recent_indices = (
            list(range(recent_start, total)) if temporal_memory_size else []
        )
        anchor_slots = context_size - len(recent_indices)
        anchor_budget = min(anchor_slots, shot_memory_size)
        anchor_indices = [
            index
            for index in range(shot_anchor_offset, recent_start, shot_length)
            if 0 <= index < recent_start
        ]

        selected_anchors = []
        if anchor_budget > 0 and anchor_indices:
            selected_anchors.append(anchor_indices[0])
            for index in reversed(anchor_indices[1:]):
                if len(selected_anchors) >= anchor_budget:
                    break
                selected_anchors.append(index)

        selected_indices = sorted(set(selected_anchors + recent_indices))
        if len(selected_indices) < context_size:
            for index in range(total - 1, -1, -1):
                if index not in selected_indices:
                    selected_indices.append(index)
                if len(selected_indices) >= context_size:
                    break
            selected_indices.sort()

        selected_indices = selected_indices[:context_size]
        print(
            "Dual Memory Selector: "
            f"selected frames {selected_indices} from {total} history frames."
        )
        return (images[selected_indices],)
