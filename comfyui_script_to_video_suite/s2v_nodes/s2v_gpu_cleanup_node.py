import gc

try:
    import torch
except Exception:
    torch = None

try:
    import comfy.model_management as model_management
except Exception:
    model_management = None

from .s2v_progress_node import any_type


class GPUCleanup_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (any_type,),
                "label": ("STRING", {"default": "GPU cleanup"}),
                "collect_garbage": ("BOOLEAN", {"default": True}),
                "soft_empty_cache": ("BOOLEAN", {"default": True}),
                "torch_empty_cache": ("BOOLEAN", {"default": True}),
                "unload_all_models": ("BOOLEAN", {"default": False}),
                "print_memory": ("BOOLEAN", {"default": True}),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("NaN")

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("value",)
    FUNCTION = "cleanup"
    CATEGORY = "Script To Video Suite/Utility"

    def cleanup(
        self,
        value,
        label="GPU cleanup",
        collect_garbage=True,
        soft_empty_cache=True,
        torch_empty_cache=True,
        unload_all_models=False,
        print_memory=True,
    ):
        before = _memory_summary()

        if collect_garbage:
            gc.collect()

        if model_management is not None:
            if unload_all_models:
                _call_if_available(model_management, "unload_all_models")
            if soft_empty_cache:
                _call_if_available(model_management, "cleanup_models")
                _call_if_available(model_management, "cleanup_models_gc")
                _soft_empty_cache()

        if torch_empty_cache:
            _torch_empty_cache()

        if collect_garbage:
            gc.collect()

        after = _memory_summary()
        if print_memory:
            if before or after:
                print(f"[S2V GPU Cleanup] {label}: {before or 'n/a'} -> {after or 'n/a'}", flush=True)
            else:
                print(f"[S2V GPU Cleanup] {label}: cache cleanup requested", flush=True)

        return (value,)


def _call_if_available(module, name):
    fn = getattr(module, name, None)
    if fn is None:
        return
    try:
        fn()
    except TypeError:
        return


def _soft_empty_cache():
    fn = getattr(model_management, "soft_empty_cache", None)
    if fn is None:
        return
    try:
        fn(force=True)
    except TypeError:
        fn()


def _torch_empty_cache():
    if torch is None:
        return

    try:
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass

    try:
        if hasattr(torch, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def _memory_summary():
    if torch is None:
        return ""

    try:
        if torch.cuda.is_available():
            allocated = _format_bytes(torch.cuda.memory_allocated())
            reserved = _format_bytes(torch.cuda.memory_reserved())
            return f"cuda allocated={allocated}, reserved={reserved}"
    except Exception:
        pass

    try:
        if hasattr(torch, "mps") and torch.backends.mps.is_available():
            current = getattr(torch.mps, "current_allocated_memory", None)
            if current is not None:
                return f"mps allocated={_format_bytes(current())}"
            return "mps"
    except Exception:
        pass

    return ""


def _format_bytes(num_bytes):
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TiB"
