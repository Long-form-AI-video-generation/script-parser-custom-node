import unittest

from comfyui_script_to_video_suite.s2v_nodes.s2v_prompt_gen_node import PromptGenerator


class PromptGeneratorJsonExtractionTests(unittest.TestCase):
    def setUp(self):
        self.generator = PromptGenerator()

    def test_valid_json_with_apostrophe_inside_string(self):
        response = """
        {
          "meta_summary": "A tense moment aboard the scout ship 'Stargazer'.",
          "panels": [
            {
              "panel_number": "1",
              "image_prompt": "cockpit of the scout ship 'Stargazer', compact and functional",
              "video_prompt": "Wide shot of the cockpit."
            }
          ]
        }
        """

        data = self.generator._extract_json_robustly(response)

        self.assertIsNotNone(data)
        self.assertTrue(self.generator._panels_are_valid(data["panels"]))
        self.assertIn("'Stargazer'", data["panels"][0]["image_prompt"])

    def test_markdown_wrapped_json(self):
        response = """
        ```json
        {
          "meta_summary": "A clean response.",
          "panels": [
            {
              "panel_number": "1",
              "image_prompt": "image",
              "video_prompt": "motion"
            }
          ]
        }
        ```
        """

        data = self.generator._extract_json_robustly(response)

        self.assertIsNotNone(data)
        self.assertEqual(data["panels"][0]["video_prompt"], "motion")


if __name__ == "__main__":
    unittest.main()
