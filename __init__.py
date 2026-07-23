
from .comfyui_script_to_video_suite.s2v_nodes.s2v_chunker_node import PDFChunker, PDFUploadChunker
from .comfyui_script_to_video_suite.s2v_nodes.s2v_storyboard_node import StoryboardGenerator
from .comfyui_script_to_video_suite.s2v_nodes.s2v_prompt_gen_node import PromptGenerator
from .comfyui_script_to_video_suite.s2v_nodes.s2v_executor_nodes import PromptUnpacker, SmartSequencer_S2V, PromptLoopBuilder_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_utility_nodes import StringSwitch_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_auto_lora_node import AutoLoraLoader_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_multi_lora_loader_node import MultiLoraLoader_S2V, MergeWanVideoLoras_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_fighting_detector_node import FightingSceneDetector_S2V, DragonBallLoRAConditional_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_video_merger_node import VideoMergerNode


from .comfyui_script_to_video_suite.s2v_nodes.s2v_rag_node import RagConsistencyNode_S2V
from .comfyui_script_to_video_suite.s2v_nodes.s2v_progress_node import ProgressMessage_S2V
NODE_CLASS_MAPPINGS = {
    "PDFChunker_S2V": PDFChunker,
    "PDFUploadChunker_S2V": PDFUploadChunker,
    "StoryboardGenerator_S2V": StoryboardGenerator,
    "PromptGenerator_S2V": PromptGenerator,
    "PromptUnpacker_S2V": PromptUnpacker,
    "PromptLoopBuilder_S2V": PromptLoopBuilder_S2V,
    "StringSwitch_S2V": StringSwitch_S2V,
    "AutoLoraLoader_S2V": AutoLoraLoader_S2V,
    "RagConsistencyNode_S2V": RagConsistencyNode_S2V,
    "SmartSequencer_S2V": SmartSequencer_S2V,
    "MultiLoraLoader_S2V": MultiLoraLoader_S2V,
    "MergeWanVideoLoras_S2V": MergeWanVideoLoras_S2V,
    "FightingSceneDetector_S2V": FightingSceneDetector_S2V,
    "DragonBallLoRAConditional_S2V": DragonBallLoRAConditional_S2V,
    "VideoMerger_S2V": VideoMergerNode,
    "ProgressMessage_S2V": ProgressMessage_S2V
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PDFChunker_S2V": "1. PDF Chunker (S2V)",
    "PDFUploadChunker_S2V": "1a. PDF Upload Chunker (S2V)",
    "StoryboardGenerator_S2V": "2. Storyboard Generator (S2V)",
    "PromptGenerator_S2V": "3. Prompt Generator (S2V)",
    "PromptUnpacker_S2V": "4. Prompt Unpacker (S2V)",
    "PromptLoopBuilder_S2V": "5. Prompt Loop Builder (S2V)",
    "StringSwitch_S2V": "Debug String Switch (S2V)",
    "AutoLoraLoader_S2V": "6. Gemini Auto LoRA Loader (S2V)",
    "RagConsistencyNode_S2V": "RAG Consistency Engine (S2V)",
    "SmartSequencer_S2V": "5b. Smart Sequencer (Auto-Loop)",
    "MultiLoraLoader_S2V": "7. Multi LoRA Loader (S2V)",
    "MergeWanVideoLoras_S2V": "Merge WanVideo LoRAs (S2V)",
    "FightingSceneDetector_S2V": "Fighting Scene Detector (S2V)",
    "DragonBallLoRAConditional_S2V": "Dragon Ball LoRA Conditional (S2V)",
    "VideoMerger_S2V": "Video Merger (S2V)",
    "ProgressMessage_S2V": "Progress Message (S2V)"
}

WEB_DIRECTORY = "./web"

# --- A confirmation message that your package was loaded ---
print('✅ Loaded Custom Nodes: Script-to-Video Suite')
