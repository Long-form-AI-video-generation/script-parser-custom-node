

# 1. Import all your node classes
from .s2v_nodes.s2v_chunker_node import PDFChunker
from .s2v_nodes.s2v_storyboard_node import StoryboardGenerator
from .s2v_nodes.s2v_prompt_gen_node import PromptGenerator

# 2. Add them to the mappings
NODE_CLASS_MAPPINGS = {
    "PDFChunker_S2V": PDFChunker,
    "StoryboardGenerator_S2V": StoryboardGenerator,
    "PromptGenerator_S2V": PromptGenerator,
}

# 3. Create user-friendly display names
NODE_DISPLAY_NAME_MAPPINGS = {
    "PDFChunker_S2V": "1. PDF Chunker (S2V)",
    "StoryboardGenerator_S2V": "2. Storyboard Generator (S2V)",
    "PromptGenerator_S2V": "3. Prompt Generator (S2V)",
}

print('✅ Loaded Custom Nodes: Script-to-Video Suite')