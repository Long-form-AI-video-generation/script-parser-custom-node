import pytest

from comfyui_script_to_video_suite.s2v_nodes.s2v_generation_control_node import GenerationFolder_S2V
from comfyui_script_to_video_suite.s2v_nodes.s2v_progress_node import PromptExecutionStatus_S2V


def test_generation_folder_builds_all_prefixes():
    result = GenerationFolder_S2V().build("aug_10/run_01")

    assert result == (
        "aug_10/run_01",
        "aug_10/run_01/seed/seed",
        "aug_10/run_01/sections/first",
        "aug_10/run_01/sections/loop",
        "aug_10/run_01/final/video",
    )


@pytest.mark.parametrize("folder", ["", "/absolute", "../escape", "C:\\absolute"])
def test_generation_folder_rejects_unsafe_paths(folder):
    with pytest.raises(ValueError):
        GenerationFolder_S2V().build(folder)


def test_prompt_status_reports_one_based_progress():
    result = PromptExecutionStatus_S2V().show(
        value="image prompt",
        prompt="  camera   pans to Isaac  ",
        index=1,
        total=6,
        stage="Generating section",
    )

    assert result["ui"]["text"] == [
        "Generating section: prompt 2/6",
        "camera pans to Isaac",
    ]
    assert result["result"] == (
        "image prompt",
        "camera pans to Isaac",
        "Generating section: prompt 2/6",
    )
