
import datetime


class AnyType(str):
    """Wildcard socket type: compares equal to every other type."""
    def __ne__(self, _other):
        return False


any_type = AnyType("*")


class ProgressMessage_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (any_type,),
                "message": ("STRING", {"default": "Processing stage"}),
                "index_offset": ("INT", {"default": 0, "min": -100, "max": 100}),
            },
            "optional": {
                "index": ("INT", {"forceInput": True}),
                "total": ("INT", {"forceInput": True}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("value",)
    FUNCTION = "announce"
    CATEGORY = "Script To Video Suite"

    def announce(self, value, message, index_offset=0, index=None, total=None, unique_id=None):
        text = message
        if index is not None:
            shown = index + index_offset
            text = f"{message} {shown}/{total}" if total is not None else f"{message} {shown}"

        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"📢 [{stamp}] {text}"
        print("\n" + "=" * len(line), flush=True)
        print(line, flush=True)
        print("=" * len(line) + "\n", flush=True)

        announce_to_ui(text, unique_id)
        return (value,)


def announce_to_ui(text, unique_id=None):
    """Best-effort UI announcements: a toast event (works in app mode via
    web/s2v_progress.js) and node progress text (graph view)."""
    try:
        from server import PromptServer
        PromptServer.instance.send_sync("s2v.progress", {"text": text, "node": unique_id})
    except Exception:
        pass
    try:
        from server import PromptServer
        if unique_id is not None:
            PromptServer.instance.send_progress_text(text, unique_id)
    except Exception:
        pass
