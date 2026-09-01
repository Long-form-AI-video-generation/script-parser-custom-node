#!/usr/bin/env python3
"""Build the low-memory August 10 workflow from the known-good v14 graph."""

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / "Downloads" / "app-context-aware-codex-fixed-v14-clean-anime-video.json"
DESTINATION = ROOT / "workflows" / "aug_10_v14_working_loaders_t2v_context_controlled.json"


with SOURCE.open("r", encoding="utf-8") as handle:
    workflow = json.load(handle)

nodes = workflow["nodes"]
links = workflow["links"]
by_id = {item["id"]: item for item in nodes}
next_node_id = max(by_id) + 1
next_link_id = max(item[0] for item in links) + 1
next_order = max(item.get("order", 0) for item in nodes) + 1


def node(node_id):
    return by_id[node_id]


def disconnect(link_id):
    global links
    links = [item for item in links if item[0] != link_id]


def disconnect_input(node_id, input_slot):
    link_id = node(node_id)["inputs"][input_slot].get("link")
    if link_id is not None:
        disconnect(link_id)


def remove_node(node_id):
    global nodes, links
    links = [item for item in links if item[1] != node_id and item[3] != node_id]
    nodes = [item for item in nodes if item["id"] != node_id]
    workflow["nodes"] = nodes
    del by_id[node_id]


def connect(source_id, source_slot, target_id, target_slot, data_type):
    global next_link_id
    disconnect_input(target_id, target_slot)
    link_id = next_link_id
    next_link_id += 1
    links.append([link_id, source_id, source_slot, target_id, target_slot, data_type])
    return link_id


def add(item):
    global next_node_id, next_order
    item["id"] = next_node_id
    next_node_id += 1
    item["order"] = next_order
    next_order += 1
    item.setdefault("flags", {})
    item.setdefault("mode", 0)
    item.setdefault("properties", {"Node name for S&R": item["type"]})
    nodes.append(item)
    by_id[item["id"]] = item
    return item["id"]


def clone(source_id, title, pos, *, color=None, bgcolor=None):
    item = copy.deepcopy(node(source_id))
    item.pop("id", None)
    item.pop("order", None)
    item["title"] = title
    item["pos"] = pos
    if color:
        item["color"] = color
    if bgcolor:
        item["bgcolor"] = bgcolor
    for input_spec in item.get("inputs", []):
        input_spec["link"] = None
    for output_spec in item.get("outputs", []):
        output_spec["links"] = None
    return add(item)


def get_node(name, data_type, pos, color="#243447", bgcolor="#36516b"):
    return add({
        "type": "GetNode",
        "title": f"Get_{name}",
        "pos": pos,
        "size": [225, 58],
        "flags": {"collapsed": True},
        "inputs": [],
        "outputs": [{"name": data_type, "type": data_type, "links": None}],
        "properties": {
            "Node name for S&R": "GetNode",
            "aux_id": "kijai/ComfyUI-KJNodes",
            "widget_ue_connectable": {},
        },
        "widgets_values": [name],
        "color": color,
        "bgcolor": bgcolor,
    })


def set_node(name, data_type, pos, color="#1b4669", bgcolor="#29699c"):
    return add({
        "type": "SetNode",
        "title": f"Set_{name}",
        "pos": pos,
        "size": [245, 58],
        "flags": {"collapsed": True},
        "inputs": [{"name": data_type, "type": data_type, "link": None}],
        "outputs": [{"name": "*", "type": "*", "links": None}],
        "properties": {
            "Node name for S&R": "SetNode",
            "aux_id": "kijai/ComfyUI-KJNodes",
            "previousName": "",
            "widget_ue_connectable": {},
        },
        "widgets_values": [name],
        "color": color,
        "bgcolor": bgcolor,
    })


def prompt_status(title, stage, pos, color, bgcolor):
    return add({
        "type": "PromptExecutionStatus_S2V",
        "title": title,
        "pos": pos,
        "size": [500, 230],
        "inputs": [
            {"name": "value", "type": "*", "link": None},
            {"name": "prompt", "type": "STRING", "link": None},
            {"name": "index", "type": "INT", "link": None},
            {"name": "total", "type": "INT", "link": None},
        ],
        "outputs": [
            {"name": "value", "type": "*", "links": None},
            {"name": "current_prompt", "type": "STRING", "links": None},
            {"name": "status", "type": "STRING", "links": None},
        ],
        "properties": {
            "Node name for S&R": "PromptExecutionStatus_S2V",
            "aux_id": "Long-form-AI-video-generation/script-parser-custom-node",
            "widget_ue_connectable": {},
        },
        "widgets_values": [stage, "Waiting for execution"],
        "color": color,
        "bgcolor": bgcolor,
    })


def auto_lora(title, pos, color, bgcolor):
    return add({
        "type": "AutoLoraLoader_S2V",
        "title": title,
        "pos": pos,
        "size": [330, 126],
        "inputs": [{"name": "image_prompt", "type": "STRING", "link": None}],
        "outputs": [{"name": "lora_stack", "type": "LORA_STACK", "links": None}],
        "properties": {
            "Node name for S&R": "AutoLoraLoader_S2V",
            "widget_ue_connectable": {},
        },
        "widgets_values": [1.0],
        "color": color,
        "bgcolor": bgcolor,
    })


def multi_lora(title, pos, color, bgcolor):
    return add({
        "type": "MultiLoraLoader_S2V",
        "title": title,
        "pos": pos,
        "size": [300, 90],
        "inputs": [{"name": "lora_stack", "type": "LORA_STACK", "link": None}],
        "outputs": [{"name": "loras_list", "type": "WANVIDLORA", "links": None}],
        "properties": {
            "Node name for S&R": "MultiLoraLoader_S2V",
            "widget_ue_connectable": {},
        },
        "widgets_values": [],
        "color": color,
        "bgcolor": bgcolor,
    })


def merge_loras(title, pos, color, bgcolor):
    return add({
        "type": "MergeWanVideoLoras_S2V",
        "title": title,
        "pos": pos,
        "size": [300, 120],
        "inputs": [
            {"name": "lora_a", "type": "WANVIDLORA", "link": None},
            {"name": "lora_b", "type": "WANVIDLORA", "link": None},
            {"name": "lora_c", "type": "WANVIDLORA", "link": None},
        ],
        "outputs": [{"name": "loras", "type": "WANVIDLORA", "links": None}],
        "properties": {
            "Node name for S&R": "MergeWanVideoLoras_S2V",
            "widget_ue_connectable": {},
        },
        "widgets_values": [],
        "color": color,
        "bgcolor": bgcolor,
    })


def fight_detector(title, pos, color, bgcolor):
    return add({
        "type": "FightingSceneDetector_S2V",
        "title": title,
        "pos": pos,
        "size": [330, 90],
        "inputs": [{"name": "input", "type": "STRING", "link": None}],
        "outputs": [{"name": "condition", "type": "BOOLEAN", "links": None}],
        "properties": {
            "Node name for S&R": "FightingSceneDetector_S2V",
            "widget_ue_connectable": {},
        },
        "widgets_values": [],
        "color": color,
        "bgcolor": bgcolor,
    })


def conditional_fight_lora(title, pos, color, bgcolor):
    return add({
        "type": "DragonBallLoRAConditional_S2V",
        "title": title,
        "pos": pos,
        "size": [340, 126],
        "inputs": [{"name": "condition", "type": "BOOLEAN", "link": None}],
        "outputs": [{"name": "lora", "type": "WANVIDLORA", "links": None}],
        "properties": {
            "Node name for S&R": "DragonBallLoRAConditional_S2V",
            "widget_ue_connectable": {},
        },
        "widgets_values": ["dbz_fight_style_lora_epoch60.safetensors", 1.0],
        "color": color,
        "bgcolor": bgcolor,
    })


def generation_folder(pos):
    return add({
        "type": "GenerationFolder_S2V",
        "title": "SET GENERATION FOLDER HERE (one place)",
        "pos": pos,
        "size": [430, 250],
        "inputs": [],
        "outputs": [
            {"name": "root_folder", "type": "STRING", "links": None},
            {"name": "seed_prefix", "type": "STRING", "links": None},
            {"name": "first_section_prefix", "type": "STRING", "links": None},
            {"name": "loop_section_prefix", "type": "STRING", "links": None},
            {"name": "final_video_prefix", "type": "STRING", "links": None},
        ],
        "properties": {
            "Node name for S&R": "GenerationFolder_S2V",
            "aux_id": "Long-form-AI-video-generation/script-parser-custom-node",
            "widget_ue_connectable": {},
        },
        "widgets_values": ["aug_10"],
        "color": "#24464a",
        "bgcolor": "#35686d",
    })


def context_selector(pos):
    return add({
        "type": "WanVideoContextSelector",
        "title": "Semantic Context Selector - choose 4 frames from 8 candidates",
        "pos": pos,
        "size": [430, 384],
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": None},
            {"name": "clip_vision", "shape": 7, "type": "CLIP_VISION", "link": None},
            {"name": "text_encoder", "shape": 7, "type": "WANTEXTENCODER", "link": None},
            {
                "name": "context_size",
                "type": "INT",
                "widget": {"name": "context_size"},
                "link": None,
            },
            {
                "name": "current_prompt",
                "shape": 7,
                "type": "STRING",
                "widget": {"name": "current_prompt"},
                "link": None,
            },
        ],
        "outputs": [{"name": "context_images", "type": "IMAGE", "links": None}],
        "properties": {
            "Node name for S&R": "WanVideoContextSelector",
            "aux_id": "jajos12/Comfyui-WanVideo-Context",
            "widget_ue_connectable": {},
        },
        "widgets_values": ["contiguous", 4, 0, 16, 0, 16, 0],
        "color": "#5a3d18",
        "bgcolor": "#806028",
    })


# Keep the two model loaders exactly as they are in the known-good v14 graph.
# Distillation and conditional LoRAs are attached downstream with SetLoRAs, so
# neither FP8 loader has to merge LoRA weights while loading its base model.
remove_node(61)
node(180)["title"] = "T2V Distillation LoRA Config - unmerged downstream patch"
node(180)["pos"] = [-280, 810]
node(180)["widgets_values"] = [
    "wan2.1_t2v_14b_lora_rank64_lightx2v_4step.safetensors",
    1.0,
    False,
    False,
]
node(99)["title"] = "I2V Distillation LoRA Config - unmerged downstream patch"
node(99)["pos"] = [-280, 1020]
node(99)["widgets_values"] = [
    "wan2.1_i2v_lora_rank64_lightx2v_4step.safetensors",
    1.0,
    False,
    False,
]
node(34)["title"] = "Base Wan T2V - keyframe generator (working v14 settings)"
node(78)["title"] = "Base Wan I2V - clean 480P animation (working v14 settings)"
node(62)["title"] = "I2V 20-Block Swap (working v14 wiring)"
node(63)["title"] = "Torch Compile Settings (disconnected for stability)"

distilled_sampler = [
    4, 1.0, 5.0, 0, "fixed", True, "euler", 0, 1.0, False,
    "comfy", 0, -1, False,
]
for sampler_id in (102, 76, 165, 205):
    node(sampler_id)["widgets_values"] = copy.deepcopy(distilled_sampler)
node(102)["title"] = "T2V Seed Keyframe - 4-step distilled"
node(76)["title"] = "First I2V Section - 4-step distilled"
node(205)["title"] = "Fresh Loop Keyframe T2V - 4-step distilled"
node(165)["title"] = "Context-Aware Loop I2V - 4-step distilled"

# Remove T2V character LoRAs from both I2V stages. Reuse the existing SetLoRAs
# nodes for I2V-compatible, conditional fight LoRAs only.
remove_node(214)
remove_node(216)
node(215)["title"] = "Apply Conditional I2V Fight LoRA - first section"
node(215)["pos"] = [5280, -650]
node(217)["title"] = "Apply Conditional I2V Fight LoRA - loop"
node(217)["pos"] = [4580, 1320]

# Prompt status for the first prompt.
first_total = get_node("TotalPanels_FirstStage", "INT", [2160, -380])
node(first_total)["widgets_values"] = ["TotalPanels"]
first_zero = clone(118, "First Prompt Index (zero based)", [2160, -300])
node(first_zero)["widgets_values"] = [0]
first_status = prompt_status(
    "CURRENT PROMPT - first section",
    "Generating first section",
    [2160, -650],
    "#26324d",
    "#3a4c73",
)
connect(123, 0, first_status, 0, "STRING")
connect(124, 0, first_status, 1, "STRING")
connect(first_zero, 0, first_status, 2, "INT")
connect(first_total, 0, first_status, 3, "INT")

# First T2V keyframe: auto file-name matching + curated bible matching. These
# dynamic LoRAs remain unmerged and are applied to a cloned patcher.
node(212)["pos"] = [3410, -650]
node(212)["title"] = "Curated T2V Character LoRAs - first keyframe"
first_auto = auto_lora(
    "Auto T2V Character LoRAs - first keyframe",
    [2700, -650],
    "#26324d",
    "#3a4c73",
)
first_multi = multi_lora(
    "Build Auto T2V Character LoRAs",
    [3050, -650],
    "#26324d",
    "#3a4c73",
)
first_merge = merge_loras(
    "Merge Auto + Curated Character + T2V Distillation LoRAs",
    [3830, -650],
    "#26324d",
    "#3a4c73",
)
node(213)["pos"] = [4170, -650]
node(213)["title"] = "Apply Per-Prompt T2V Character LoRAs - first keyframe"
connect(first_status, 0, first_auto, 0, "STRING")
connect(first_auto, 0, first_multi, 0, "LORA_STACK")
connect(first_status, 0, 212, 0, "STRING")
connect(first_multi, 0, first_merge, 0, "WANVIDLORA")
connect(212, 0, first_merge, 1, "WANVIDLORA")
connect(180, 0, first_merge, 2, "WANVIDLORA")
connect(first_merge, 0, 213, 1, "WANVIDLORA")
connect(212, 2, 55, 2, "STRING")

# First I2V stage uses no T2V character LoRA. Identity comes from the generated
# keyframe; only the I2V-trained fight LoRA may be added.
first_fight = fight_detector(
    "Fight Detector - first video prompt",
    [4540, -650],
    "#26324d",
    "#3a4c73",
)
first_fight_lora = conditional_fight_lora(
    "Conditional I2V Fight LoRA - first section",
    [4900, -650],
    "#26324d",
    "#3a4c73",
)
first_i2v_merge = merge_loras(
    "Merge I2V Distillation + Conditional Fight LoRA",
    [5250, -650],
    "#26324d",
    "#3a4c73",
)
node(215)["pos"] = [5580, -650]
connect(first_status, 1, first_fight, 0, "STRING")
connect(first_fight, 0, first_fight_lora, 0, "BOOLEAN")
connect(139, 0, 215, 0, "WANVIDEOMODEL")
connect(99, 0, first_i2v_merge, 0, "WANVIDLORA")
connect(first_fight_lora, 0, first_i2v_merge, 1, "WANVIDLORA")
connect(first_i2v_merge, 0, 215, 1, "WANVIDLORA")
connect(215, 0, 76, 0, "WANVIDEOMODEL")
connect(first_status, 1, 66, 2, "STRING")

# Prompt status and per-prompt T2V character LoRAs for every remaining shot.
remove_node(177)
loop_status = prompt_status(
    "CURRENT PROMPT - context-aware loop",
    "Generating context-aware section",
    [3360, 580],
    "#4a3424",
    "#6b4b33",
)
connect(198, 0, loop_status, 0, "STRING")
connect(168, 0, loop_status, 1, "STRING")
connect(162, 0, loop_status, 2, "INT")
connect(174, 0, loop_status, 3, "INT")

node(201)["pos"] = [3380, 1510]
node(201)["title"] = "Curated T2V Character LoRAs - current keyframe"
loop_auto = auto_lora(
    "Auto T2V Character LoRAs - current keyframe",
    [2660, 1510],
    "#4a3424",
    "#6b4b33",
)
loop_multi = multi_lora(
    "Build Current Auto T2V Character LoRAs",
    [3020, 1510],
    "#4a3424",
    "#6b4b33",
)
loop_merge = merge_loras(
    "Merge Current Character + T2V Distillation LoRAs",
    [3790, 1510],
    "#4a3424",
    "#6b4b33",
)
node(202)["pos"] = [4120, 1510]
node(202)["title"] = "Apply Per-Prompt T2V Character LoRAs - current keyframe"
connect(loop_status, 0, loop_auto, 0, "STRING")
connect(loop_auto, 0, loop_multi, 0, "LORA_STACK")
connect(loop_status, 0, 201, 0, "STRING")
connect(loop_multi, 0, loop_merge, 0, "WANVIDLORA")
connect(201, 0, loop_merge, 1, "WANVIDLORA")
connect(180, 0, loop_merge, 2, "WANVIDLORA")
connect(loop_merge, 0, 202, 1, "WANVIDLORA")
connect(201, 2, 203, 2, "STRING")

loop_fight = fight_detector(
    "Fight Detector - current loop prompt",
    [3820, 1180],
    "#4a3424",
    "#6b4b33",
)
loop_fight_lora = conditional_fight_lora(
    "Conditional I2V Fight LoRA - current loop",
    [4180, 1180],
    "#4a3424",
    "#6b4b33",
)
loop_i2v_merge = merge_loras(
    "Merge Loop I2V Distillation + Conditional Fight LoRA",
    [4540, 1180],
    "#4a3424",
    "#6b4b33",
)
node(217)["pos"] = [4870, 1180]
connect(loop_status, 1, loop_fight, 0, "STRING")
connect(loop_fight, 0, loop_fight_lora, 0, "BOOLEAN")
connect(139, 0, 217, 0, "WANVIDEOMODEL")
connect(99, 0, loop_i2v_merge, 0, "WANVIDLORA")
connect(loop_fight_lora, 0, loop_i2v_merge, 1, "WANVIDLORA")
connect(loop_i2v_merge, 0, 217, 1, "WANVIDLORA")
connect(217, 0, 165, 0, "WANVIDEOMODEL")
connect(loop_status, 1, 167, 2, "STRING")

# Optional T2V anime LoRA remains available, but it never enters I2V.
node(218)["title"] = "Optional GLOBAL T2V Anime Style LoRA (blank is disabled)"
node(218)["pos"] = [1490, 1150]
node(218)["color"] = "#223"
node(218)["bgcolor"] = "#335"
for target in (212, 201):
    connect(218, 0, target, 1, "WANVIDLORA")

# Two-stage context memory: first choose anchor/recent candidates, then let the
# Wan context selector select four prompt-relevant contiguous frames.
remove_node(184)
node(118)["widgets_values"] = [4]
node(118)["title"] = "Final Context Size - 4 selected frames"
disconnect_input(155, 1)
node(155)["widgets_values"] = [8, 49, 0, 4, 4]
node(155)["title"] = "Anime Anchor Memory - 8 candidates (4 anchors + 4 recent)"
node(155)["pos"] = [2700, 1120]
semantic_context = context_selector([3100, 1060])
connect(155, 0, semantic_context, 0, "IMAGE")
connect(137, 0, semantic_context, 1, "CLIP_VISION")
connect(135, 0, semantic_context, 2, "WANTEXTENCODER")
connect(176, 0, semantic_context, 3, "INT")
connect(loop_status, 1, semantic_context, 4, "STRING")
connect(semantic_context, 0, 211, 1, "IMAGE")
node(211)["title"] = "Secondary References - routed alternate + selected context"
node(156)["title"] = "CLIP Identity - fresh start + weak selected context"
node(156)["pos"] = [6310, 1510]
node(189)["pos"] = [2100, 1450]
node(183)["pos"] = [3500, -1165]
node(185)["pos"] = [1550, 300]
node(185)["flags"] = {"collapsed": True}
node(185)["size"] = [350, 58]
node(144)["pos"] = [5200, 330]
node(144)["flags"] = {"collapsed": True}
node(144)["size"] = [280, 58]
node(178)["pos"] = [6500, 620]
node(86)["pos"] = [5920, -970]
for cleanup_id in (186, 187, 188, 189, 190, 191, 192, 206):
    node(cleanup_id)["flags"] = {"collapsed": True}
    node(cleanup_id)["size"] = [300, 58]
node(191)["pos"] = [5200, 1100]

# One folder widget controls every saver through named Set/Get boundaries.
folder = generation_folder([5520, -1510])
prefix_specs = [
    ("SeedVideoPrefix", 1, 57, [5980, -1480]),
    ("FirstSectionPrefix", 2, 77, [5980, -1400]),
    ("LoopSectionPrefix", 3, 163, [5980, -1320]),
    ("FinalVideoPrefix", 4, 36, [5980, -1240]),
]
for index, (name, output_slot, saver_id, get_pos) in enumerate(prefix_specs):
    setter = set_node(name, "STRING", [5520, -1190 + index * 70])
    getter = get_node(name, "STRING", get_pos, "#24464a", "#35686d")
    connect(folder, output_slot, setter, 0, "STRING")
    saver = node(saver_id)
    saver["inputs"].append({
        "name": "filename_prefix",
        "type": "STRING",
        "widget": {"name": "filename_prefix"},
        "link": None,
    })
    saver["properties"].setdefault("widget_ue_connectable", {})[
        "filename_prefix"
    ] = True
    connect(getter, 0, saver_id, len(saver["inputs"]) - 1, "STRING")

for saver_id in (36, 57, 77, 163):
    widgets = node(saver_id)["widgets_values"]
    widgets["frame_rate"] = 16
    widgets["filename_prefix"] = "aug_10/final/video" if saver_id == 36 else "aug_10/checkpoint"
    widgets["format"] = "video/h265-mp4"
    widgets["pix_fmt"] = "yuv420p10le"
    widgets["crf"] = 18
    widgets.pop("videopreview", None)

node(36)["title"] = "ACTIVE - Save Final Stitched 16 FPS MP4"
node(36)["pos"] = [6250, -1510]
node(36)["mode"] = 0
for saver_id, title, pos in (
    (57, "MUTED - Optional Seed Checkpoint", [6670, -920]),
    (77, "MUTED - Optional First Section Checkpoint", [6960, -920]),
    (163, "MUTED - Optional Loop Checkpoint", [7250, -920]),
):
    node(saver_id)["title"] = title
    node(saver_id)["pos"] = pos
    node(saver_id)["mode"] = 2
    node(saver_id)["flags"] = {"collapsed": True}
    node(saver_id)["size"] = [280, 58]
    node(saver_id)["color"] = "#4a4a4a"
    node(saver_id)["bgcolor"] = "#2f2f2f"

# Keep section boundaries clear and include all newly added control nodes.
workflow["groups"] = [
    {
        "id": 1,
        "title": "1. Script Parser: PDF to Prompt Lists",
        "bounding": [-90, 0, 2095, 670],
        "color": "#3f789e",
        "flags": {},
    },
    {
        "id": 2,
        "title": "2. Working v14 Models, Distillation LoRA Configs and Constants",
        "bounding": [-340, 680, 2380, 650],
        "color": "#6f8f3f",
        "flags": {},
    },
    {
        "id": 3,
        "title": "3. First Character T2V Keyframe and First I2V Section",
        "bounding": [2100, -720, 3850, 1230],
        "color": "#a1309b",
        "flags": {},
    },
    {
        "id": 4,
        "title": "4. Context Loop: Character T2V Keyframe for Every Prompt -> I2V",
        "bounding": [2040, 520, 4800, 1280],
        "color": "#b58b2a",
        "flags": {},
    },
    {
        "id": 5,
        "title": "5. Output Control and Final Stitched Video",
        "bounding": [5440, -1580, 1150, 760],
        "color": "#4f8a8b",
        "flags": {},
    },
    {
        "id": 6,
        "title": "6. Muted Optional Checkpoints",
        "bounding": [6600, -1010, 1020, 260],
        "color": "#606060",
        "flags": {},
    },
    {
        "id": 7,
        "title": "Input: PDF, Character Bible and Storyboard Generation",
        "bounding": [2930, -1580, 1120, 680],
        "color": "#7b5a2c",
        "flags": {},
    },
    {
        "id": 8,
        "title": "Visual Previews",
        "bounding": [4080, -1580, 1230, 790],
        "color": "#a1309b",
        "flags": {},
    },
]


def rebuild_connections():
    valid_ids = set(by_id)
    valid_links = []
    for item in links:
        _, source_id, source_slot, target_id, target_slot, _ = item
        if source_id not in valid_ids or target_id not in valid_ids:
            continue
        if source_slot >= len(node(source_id).get("outputs", [])):
            raise ValueError(f"Invalid source slot in link {item}")
        if target_slot >= len(node(target_id).get("inputs", [])):
            raise ValueError(f"Invalid target slot in link {item}")
        valid_links.append(item)

    for item in nodes:
        for input_spec in item.get("inputs", []):
            input_spec["link"] = None
        for output_spec in item.get("outputs", []):
            output_spec["links"] = None

    for link_id, source_id, source_slot, target_id, target_slot, _ in valid_links:
        target = node(target_id)["inputs"][target_slot]
        if target["link"] is not None:
            raise ValueError(
                f"Input {target_id}:{target_slot} has duplicate links "
                f"{target['link']} and {link_id}"
            )
        target["link"] = link_id
        source = node(source_id)["outputs"][source_slot]
        if source["links"] is None:
            source["links"] = []
        source["links"].append(link_id)
    return valid_links


links = rebuild_connections()
workflow["nodes"] = nodes
workflow["links"] = links
workflow["last_node_id"] = max(by_id)
workflow["last_link_id"] = max(item[0] for item in links)


def validate_workflow():
    adjacency = {item["id"]: set() for item in nodes}
    for _, source_id, _, target_id, _, _ in links:
        adjacency[source_id].add(target_id)

    def has_path(source_id, target_id):
        pending = [source_id]
        visited = set()
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency[current] - visited)
        return False

    model_loaders = [item for item in nodes if item["type"] == "WanVideoModelLoader"]
    assert len(model_loaders) == 2, "The low-memory graph must have exactly two Wan model loaders."
    assert not any(
        "upscale" in item["type"].lower() or "tensorrt" in item["type"].lower()
        for item in nodes
    ), "Upscaler nodes must remain detached from this workflow."

    for sampler_id in (102, 76, 165, 205):
        sampler_values = node(sampler_id)["widgets_values"]
        assert sampler_values[0] == 4
        assert sampler_values[1] == 1.0
        assert sampler_values[6] == "euler"
        assert sampler_values[10] == "comfy"

    working_t2v_settings = [
        "wan2.1_t2v_14B_fp8_e4m3fn.safetensors",
        "bf16",
        "fp8_e4m3fn",
        "offload_device",
        "sdpa",
        "default",
    ]
    working_i2v_settings = [
        "wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors",
        "bf16",
        "fp8_e4m3fn",
        "offload_device",
        "sageattn",
        "default",
    ]
    assert node(34)["widgets_values"] == working_t2v_settings
    assert node(78)["widgets_values"] == working_i2v_settings
    assert node(34)["inputs"][1]["link"] is None
    assert node(34)["inputs"][2]["link"] is None
    assert node(78)["inputs"][1]["link"] is None
    assert node(78)["inputs"][2]["link"] is None
    assert node(180)["widgets_values"][2:] == [False, False]
    assert node(99)["widgets_values"][2:] == [False, False]
    assert has_path(first_status, 102) and has_path(first_status, 76)
    assert has_path(loop_status, 205) and has_path(loop_status, 165)
    first_i2v_lora_link = node(215)["inputs"][1]["link"]
    loop_i2v_lora_link = node(217)["inputs"][1]["link"]
    first_i2v_lora_source = next(item[1] for item in links if item[0] == first_i2v_lora_link)
    loop_i2v_lora_source = next(item[1] for item in links if item[0] == loop_i2v_lora_link)
    assert first_i2v_lora_source == first_i2v_merge
    assert loop_i2v_lora_source == loop_i2v_merge

    per_prompt_t2v_chain = [
        loop_status,
        loop_auto,
        loop_multi,
        loop_merge,
        202,
        205,
        206,
        207,
        208,
        209,
        210,
        171,
        165,
    ]
    assert all(
        has_path(source_id, target_id)
        for source_id, target_id in zip(
            per_prompt_t2v_chain,
            per_prompt_t2v_chain[1:],
        )
    ), "Every loop prompt must pass through a character-aware T2V keyframe."

    context_chain = [20, 155, semantic_context, 211, 156, 171, 165]
    assert all(
        has_path(source_id, target_id)
        for source_id, target_id in zip(context_chain, context_chain[1:])
    ), "The semantic context chain is incomplete."

    savers = [item for item in nodes if item["type"] == "VHS_VideoCombine"]
    assert [item["id"] for item in savers if item.get("mode", 0) == 0] == [36]
    for saver in savers:
        prefix_input = next(
            item for item in saver["inputs"] if item["name"] == "filename_prefix"
        )
        assert prefix_input["link"] is not None
        assert saver["widgets_values"]["frame_rate"] == 16
        assert saver["widgets_values"]["format"] == "video/h265-mp4"

    for index, first_group in enumerate(workflow["groups"]):
        ax, ay, aw, ah = first_group["bounding"]
        for second_group in workflow["groups"][index + 1:]:
            bx, by, bw, bh = second_group["bounding"]
            overlaps = ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by
            assert not overlaps, (
                f"Workflow groups overlap: {first_group['title']} and "
                f"{second_group['title']}"
            )


validate_workflow()

with DESTINATION.open("w", encoding="utf-8") as handle:
    json.dump(workflow, handle, indent=2, ensure_ascii=False)
    handle.write("\n")

print(DESTINATION)
