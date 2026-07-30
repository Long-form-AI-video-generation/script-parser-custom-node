#!/usr/bin/env python3
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
NODES_DIR = ROOT / "comfyui_script_to_video_suite" / "s2v_nodes"
SOURCE = WORKFLOWS / "app-context-aware-codex-fixed-v11-wan-prompt-compiler.json"
DESTINATION = WORKFLOWS / "app-context-aware-codex-fixed-v12-dual-memory-keyframes.json"
PAINTED_DESTINATION = WORKFLOWS / "app-context-aware-codex-fixed-v13-painted-storybook-anime.json"
CLEAN_VIDEO_DESTINATION = WORKFLOWS / "app-context-aware-codex-fixed-v14-clean-anime-video.json"

PAINTED_ANIME_STYLE = (
    "POLISHED FULL-COLOR HAND-PAINTED JAPANESE FANTASY ANIMATION FRAME, "
    "classic Studio Ghibli-inspired storybook anime aesthetic, rich opaque color coverage, lush gouache and "
    "watercolor backgrounds, soft natural sunlight, atmospheric depth, expressive rounded "
    "character designs, delicate colored contours, soft cel shading with subtle tonal variation, "
    "tactile organic textures, cinematic composition, finished theatrical animation still, "
    "same anime character design"
)
PAINTED_ANIME_MOTION = (
    "Preserve the exact finished full-color painted rendering from the start image with stable "
    "color fills, stable contours, stable lighting, temporally coherent surfaces, the same "
    "character proportions, and the exact outfit design. Advance to the next storyboard beat "
    "with one clear physical action and one camera motion."
)
SKETCH_NEGATIVE = (
    "black and white, black-and-white, monochrome, grayscale, greyscale, rough sketch, "
    "pencil sketch, concept sketch, charcoal drawing, ink drawing, line art only, lineart only, "
    "uncolored, unfinished, storyboard, animatic, manga panel, coloring book, cross-hatching, "
    "white paper background"
)
VIDEO_NOISE_NEGATIVE = (
    "film grain, digital noise, chroma noise, temporal noise, color speckling, crawling texture, "
    "texture boiling, temporal shimmer, flicker, unstable outlines, unstable colors, compression artifacts"
)


with SOURCE.open("r", encoding="utf-8") as handle:
    workflow = json.load(handle)

nodes = workflow["nodes"]
links = workflow["links"]
by_id = {node["id"]: node for node in nodes}
next_node_id = max(by_id) + 1
next_link_id = max(link[0] for link in links) + 1
next_order = max(node.get("order", 0) for node in nodes) + 1


def node(node_id):
    return by_id[node_id]


def disconnect(link_id):
    global links
    match = next(link for link in links if link[0] == link_id)
    _, source_id, source_slot, target_id, target_slot, _ = match
    source_links = node(source_id)["outputs"][source_slot].get("links")
    if source_links:
        node(source_id)["outputs"][source_slot]["links"] = [
            item for item in source_links if item != link_id
        ] or None
    node(target_id)["inputs"][target_slot]["link"] = None
    links = [link for link in links if link[0] != link_id]
    workflow["links"] = links


def connect(source_id, source_slot, target_id, target_slot, data_type):
    global next_link_id
    target_input = node(target_id)["inputs"][target_slot]
    if target_input.get("link") is not None:
        disconnect(target_input["link"])
    link_id = next_link_id
    next_link_id += 1
    links.append([link_id, source_id, source_slot, target_id, target_slot, data_type])
    output = node(source_id)["outputs"][source_slot]
    output.setdefault("links", [])
    if output["links"] is None:
        output["links"] = []
    output["links"].append(link_id)
    target_input["link"] = link_id
    return link_id


def add(new_node):
    global next_node_id, next_order
    new_node["id"] = next_node_id
    next_node_id += 1
    new_node["order"] = next_order
    next_order += 1
    new_node.setdefault("flags", {})
    new_node.setdefault("mode", 0)
    new_node.setdefault("properties", {"Node name for S&R": new_node["type"]})
    nodes.append(new_node)
    by_id[new_node["id"]] = new_node
    return new_node["id"]


def clone(source_id, title, pos):
    cloned = copy.deepcopy(node(source_id))
    cloned.pop("id", None)
    cloned.pop("order", None)
    cloned["title"] = title
    cloned["pos"] = pos
    for input_spec in cloned.get("inputs", []):
        input_spec["link"] = None
    for output_spec in cloned.get("outputs", []):
        output_spec["links"] = None
    return add(cloned)


def set_node(name, data_type, pos):
    template = copy.deepcopy(node(121))
    template.pop("id", None)
    template.pop("order", None)
    template["title"] = f"Set_{name}"
    template["pos"] = pos
    template["inputs"] = [{"name": data_type, "type": data_type, "link": None}]
    template["outputs"] = [{"name": "*", "type": "*", "links": None}]
    template["widgets_values"] = [name]
    return add(template)


def get_node(name, data_type, pos):
    template = copy.deepcopy(node(173))
    template.pop("id", None)
    template.pop("order", None)
    template["title"] = f"Get_{name}"
    template["pos"] = pos
    template["inputs"] = []
    template["outputs"] = [{"name": data_type, "type": data_type, "links": None}]
    template["widgets_values"] = [name]
    return add(template)


def character_lora_node(title, pos):
    return add({
        "type": "CharacterLoraSelect_S2V",
        "title": title,
        "pos": pos,
        "size": [380, 150],
        "inputs": [
            {"name": "prompt", "type": "STRING", "link": None},
            {"name": "prev_lora", "shape": 7, "type": "WANVIDLORA", "link": None},
            {"name": "lora_map_override", "shape": 7, "type": "STRING", "link": None},
        ],
        "outputs": [
            {"name": "lora", "type": "WANVIDLORA", "links": None},
            {"name": "matched_info", "type": "STRING", "links": None},
            {"name": "prompt_with_trigger", "type": "STRING", "links": None},
        ],
        "widgets_values": [
            "# Managed by character_bible.json via lora_map_override.",
            "exact",
        ],
    })


def set_loras_node(title, pos):
    return add({
        "type": "WanVideoSetLoRAs",
        "title": title,
        "pos": pos,
        "size": [260, 80],
        "inputs": [
            {"name": "model", "type": "WANVIDEOMODEL", "link": None},
            {"name": "lora", "shape": 7, "type": "WANVIDLORA", "link": None},
        ],
        "outputs": [{"name": "model", "type": "WANVIDEOMODEL", "links": None}],
        "widgets_values": [],
    })

node(116)["widgets_values"][0] = (NODES_DIR / "storyboard_master_prompt.txt").read_text(encoding="utf-8")
node(116)["widgets_values"][1] = 2
node(117)["widgets_values"][0] = (NODES_DIR / "prompt_generation_meta_prompt.txt").read_text(encoding="utf-8")
node(117)["widgets_values"][1] = 4
node(117)["widgets_values"][2] = 4
node(182)["title"] = "Character/Prop/Location Continuity Bible (full episode)"
node(182)["widgets_values"][0] = "episode1_full_continuity_bible_v2.json"
node(183)["widgets_values"] = [
    "# Exact canonical designs from the full-episode bible.\n",
    True,
    False,
]

node(185)["widgets_values"] = [PAINTED_ANIME_STYLE, PAINTED_ANIME_MOTION]
for text_encoder_id in (55, 66, 167):
    negative = str(node(text_encoder_id)["widgets_values"][0]).rstrip(" ,")
    if "rough sketch" not in negative.lower():
        node(text_encoder_id)["widgets_values"][0] = f"{negative}, {SKETCH_NEGATIVE}"
for text_encoder_id in (66, 167):
    negative = str(node(text_encoder_id)["widgets_values"][0]).rstrip(" ,")
    if "temporal noise" not in negative.lower():
        node(text_encoder_id)["widgets_values"][0] = f"{negative}, {VIDEO_NOISE_NEGATIVE}"

for link_id in (47, 211):
    disconnect(link_id)
node(34)["title"] = "Base Wan T2V - keyframe generator (quality mode)"
node(78)["title"] = "Base Wan I2V - clean 480P animation (RTX 3090 safe)"

disconnect(46)
node(78)["widgets_values"][2] = "fp8_e4m3fn"
node(78)["widgets_values"][4] = "sageattn"

node(102)["widgets_values"] = [
    28, 5.0, 5.0, 0, "fixed", True, "unipc", 0, 1.0, False,
    "comfy", 0, -1, False,
]
node(76)["widgets_values"] = [
    40, 5.0, 3.0, 0, "fixed", True, "unipc", 0, 1.0, False,
    "comfy", 0, -1, False,
]
node(165)["widgets_values"] = [
    40, 5.0, 3.0, 1, "fixed", True, "unipc", 0, 1.0, False,
    "comfy", 0, -1, False,
]
node(171)["widgets_values"][0:3] = [0.0, 1.0, 1.0]
node(171)["title"] = "Loop I2V Encode (exact routed keyframe, zero noise augmentation)"

for video_node_id in (36, 57, 77, 163):
    video_widgets = node(video_node_id).get("widgets_values")
    if isinstance(video_widgets, dict):
        video_widgets["crf"] = 18

disconnect(17)
validator = add({
    "type": "ShotPlanValidator_S2V",
    "title": "4. Shot Plan Quality Gate",
    "pos": [1120, 15],
    "size": [390, 170],
    "inputs": [{"name": "prompt_json", "type": "STRING", "link": None}],
    "outputs": [
        {"name": "validated_prompts", "type": "STRING", "links": None},
        {"name": "quality_report", "type": "STRING", "links": None},
        {"name": "shot_count", "type": "INT", "links": None},
        {"name": "cut_count", "type": "INT", "links": None},
    ],
    "widgets_values": [True, False, 0.82],
})
connect(114, 0, validator, 0, "STRING")
connect(validator, 0, 39, 0, "STRING")
node(39)["title"] = "5. Prompt Unpacker (prompts + shot state)"

# Extend saved node schemas without changing the original output positions.
node(39)["outputs"].extend([
    {"name": "transition_modes", "type": "PROMPTS_LIST", "links": None},
    {"name": "scene_ids", "type": "PROMPTS_LIST", "links": None},
])
node(41)["inputs"].extend([
    {"name": "transition_modes", "shape": 7, "type": "PROMPTS_LIST", "link": None},
    {"name": "scene_ids", "shape": 7, "type": "PROMPTS_LIST", "link": None},
])
node(41)["outputs"].extend([
    {"name": "all_image_prompts", "type": "PROMPTS_LIST", "links": None},
    {"name": "all_transition_modes", "type": "PROMPTS_LIST", "links": None},
    {"name": "all_scene_ids", "type": "PROMPTS_LIST", "links": None},
])
connect(39, 3, 41, 2, "PROMPTS_LIST")
connect(39, 4, 41, 3, "PROMPTS_LIST")
node(41)["title"] = "6. Shot Loop Builder (keyframes, motion, transitions)"

node(185)["inputs"].append(
    {"name": "all_image_prompts", "shape": 7, "type": "PROMPTS_LIST", "link": None}
)
node(185)["outputs"].append(
    {"name": "all_image_prompts", "type": "PROMPTS_LIST", "links": None}
)
connect(41, 5, 185, 3, "PROMPTS_LIST")

set_all_images = set_node("AllImagePrompts", "PROMPTS_LIST", [1780, 45])
set_transitions = set_node("AllTransitions", "PROMPTS_LIST", [1780, 115])
set_scenes = set_node("AllSceneIDs", "PROMPTS_LIST", [1780, 185])
connect(185, 3, set_all_images, 0, "PROMPTS_LIST")
connect(41, 6, set_transitions, 0, "PROMPTS_LIST")
connect(41, 7, set_scenes, 0, "PROMPTS_LIST")

# Index the current keyframe prompt and transition using the same loop index as motion.
get_all_images = get_node("AllImagePrompts", "PROMPTS_LIST", [3550, 1280])
index_image = clone(168, "Loop Keyframe Prompt Indexer", [3790, 1280])
connect(get_all_images, 0, index_image, 0, "PROMPTS_LIST")
connect(162, 0, index_image, 1, "INT")

get_transitions = get_node("AllTransitions", "PROMPTS_LIST", [3550, 1420])
index_transition = clone(168, "Loop Transition Indexer", [3790, 1420])
connect(get_transitions, 0, index_transition, 0, "PROMPTS_LIST")
connect(162, 0, index_transition, 1, "INT")

# Generate a fresh drawable keyframe for every loop shot.
keyframe_lora = character_lora_node("Character LoRA: loop keyframe", [4050, 1280])
connect(index_image, 0, keyframe_lora, 0, "STRING")
connect(182, 3, keyframe_lora, 2, "STRING")
keyframe_model = set_loras_node("Apply Character LoRA: loop keyframe", [4310, 1280])
connect(138, 0, keyframe_model, 0, "WANVIDEOMODEL")
connect(keyframe_lora, 0, keyframe_model, 1, "WANVIDLORA")

keyframe_text = clone(55, "Encode Current Shot Keyframe Prompt", [4310, 1400])
connect(135, 0, keyframe_text, 0, "WANTEXTENCODER")
connect(keyframe_lora, 2, keyframe_text, 2, "STRING")

keyframe_empty = clone(51, "Empty 1-Frame Keyframe Latent", [4310, 1540])
keyframe_empty_node = node(keyframe_empty)
keyframe_empty_node["widgets_values"] = [720, 480, 1]
keyframe_sampler = clone(102, "Generate Fresh Shot Keyframe (base T2V)", [4600, 1280])
node(keyframe_sampler)["widgets_values"] = [
    28, 5.0, 5.0, 0, "fixed", True, "unipc", 0, 1.0, False,
    "comfy", 0, -1, False,
]
connect(keyframe_model, 0, keyframe_sampler, 0, "WANVIDEOMODEL")
connect(keyframe_empty, 0, keyframe_sampler, 1, "WANVIDIMAGE_EMBEDS")
connect(keyframe_text, 0, keyframe_sampler, 2, "WANVIDEOTEXTEMBEDS")

keyframe_cleanup = clone(186, "GPU Cleanup - loop keyframe sampler", [4870, 1280])
node(keyframe_cleanup)["widgets_values"][0] = "After loop keyframe sampler"
connect(keyframe_sampler, 0, keyframe_cleanup, 0, "LATENT")
keyframe_decode = clone(52, "Decode Current Shot Keyframe", [5080, 1280])
connect(136, 0, keyframe_decode, 0, "WANVAE")
connect(keyframe_cleanup, 0, keyframe_decode, 1, "LATENT")
keyframe_first = clone(59, "Use Generated Frame 0 as Shot Start", [5310, 1280])
node(keyframe_first)["widgets_values"] = ["0\n"]
connect(keyframe_decode, 0, keyframe_first, 0, "IMAGE")
keyframe_resize = clone(154, "Resize Fresh Keyframe to Wan I2V", [5520, 1280])
connect(keyframe_first, 0, keyframe_resize, 0, "IMAGE")

# Route CUT to the fresh keyframe and CONTINUE to the actual previous final frame.
disconnect(183)
router = add({
    "type": "ShotStartRouter_S2V",
    "title": "Route CUT vs CONTINUE Shot Start",
    "pos": [5750, 1280],
    "size": [360, 130],
    "inputs": [
        {"name": "generated_keyframe", "type": "IMAGE", "link": None},
        {"name": "previous_frame", "type": "IMAGE", "link": None},
        {"name": "transition_mode", "type": "STRING", "link": None},
    ],
    "outputs": [
        {"name": "start_image", "type": "IMAGE", "links": None},
        {"name": "secondary_reference", "type": "IMAGE", "links": None},
        {"name": "is_hard_cut", "type": "BOOLEAN", "links": None},
        {"name": "transition", "type": "STRING", "links": None},
    ],
    "widgets_values": [True],
})
connect(keyframe_resize, 0, router, 0, "IMAGE")
connect(79, 0, router, 1, "IMAGE")
connect(index_transition, 0, router, 2, "STRING")
connect(router, 0, 171, 2, "IMAGE")

for link_id in (143, 144, 207, 210):
    disconnect(link_id)
node(155).update({
    "type": "DualMemorySelector_S2V",
    "title": "Dual Memory Selector (shot anchors, no composition cage)",
    "size": [372, 168],
    "inputs": [
        {"name": "images", "type": "IMAGE", "link": 142},
        {
            "name": "context_size",
            "type": "INT",
            "widget": {"name": "context_size"},
            "link": None,
        },
    ],
    "outputs": [
        {"name": "context_images", "type": "IMAGE", "links": [149]},
    ],
    "properties": {"Node name for S&R": "DualMemorySelector_S2V"},
    "widgets_values": [2, 49, 0, 2, 0],
})
connect(176, 0, 155, 1, "INT")
disconnect(219)
secondary_batch = clone(170, "Secondary References: routed alternate + shot memory", [6120, 1280])
connect(router, 1, secondary_batch, 0, "IMAGE")
connect(184, 0, secondary_batch, 1, "IMAGE")
connect(router, 0, 156, 1, "IMAGE")
connect(secondary_batch, 0, 156, 2, "IMAGE")
node(156)["title"] = "CLIP Vision: current keyframe 1.0 + weak identity memory 0.12"
node(156)["widgets_values"][0:2] = [1.0, 0.12]

# Optional character LoRAs are now applied to all three generation stages.
seed_lora = character_lora_node("Character LoRA: first keyframe", [2250, -120])
connect(123, 0, seed_lora, 0, "STRING")
connect(182, 3, seed_lora, 2, "STRING")
seed_model = set_loras_node("Apply Character LoRA: first keyframe", [2520, -120])
connect(138, 0, seed_model, 0, "WANVIDEOMODEL")
connect(seed_lora, 0, seed_model, 1, "WANVIDLORA")
connect(seed_model, 0, 102, 0, "WANVIDEOMODEL")
connect(seed_lora, 2, 55, 2, "STRING")

first_video_lora = character_lora_node("Character LoRA: first video section", [2250, 300])
connect(124, 0, first_video_lora, 0, "STRING")
connect(182, 3, first_video_lora, 2, "STRING")
first_video_model = set_loras_node("Apply Character LoRA: first video", [2520, 300])
connect(139, 0, first_video_model, 0, "WANVIDEOMODEL")
connect(first_video_lora, 0, first_video_model, 1, "WANVIDLORA")
connect(first_video_model, 0, 76, 0, "WANVIDEOMODEL")
connect(first_video_lora, 2, 66, 2, "STRING")

loop_lora = character_lora_node("Character LoRA: current loop shot", [4050, 1010])
connect(177, 0, loop_lora, 0, "STRING")
connect(182, 3, loop_lora, 2, "STRING")
loop_model = set_loras_node("Apply Character LoRA: current loop shot", [4310, 1010])
connect(139, 0, loop_model, 0, "WANVIDEOMODEL")
connect(loop_lora, 0, loop_model, 1, "WANVIDLORA")
connect(loop_model, 0, 165, 0, "WANVIDEOMODEL")
connect(loop_lora, 2, 167, 2, "STRING")

# One global anime-style LoRA can be added without hard-failing when absent.
global_style_lora = add({
    "type": "OptionalWanLora_S2V",
    "title": "GLOBAL ANIME STYLE LoRA (set filename for model-level anime lock)",
    "pos": [2050, 610],
    "size": [420, 120],
    "inputs": [
        {"name": "prev_lora", "shape": 7, "type": "WANVIDLORA", "link": None},
    ],
    "outputs": [
        {"name": "lora", "type": "WANVIDLORA", "links": None},
        {"name": "status", "type": "STRING", "links": None},
    ],
    "widgets_values": ["", 0.85],
})
for character_lora in (seed_lora, first_video_lora, keyframe_lora, loop_lora):
    connect(global_style_lora, 0, character_lora, 1, "WANVIDLORA")

workflow["last_node_id"] = max(by_id)
workflow["last_link_id"] = max(link[0] for link in links)
workflow["links"] = links

for destination in (DESTINATION, PAINTED_DESTINATION, CLEAN_VIDEO_DESTINATION):
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(workflow, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(destination)
xT