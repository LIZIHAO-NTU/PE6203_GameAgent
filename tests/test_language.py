"""Language-policy prompt wiring, not proof of real-model language compliance."""
import unittest

from agent.prompts import GAME_LANGUAGE_POLICY, PLANNER_SYSTEM, PLAN_AUDIT_SYSTEM, CODER_SYSTEM


class LanguagePromptTests(unittest.TestCase):
    def test_ui_stages_share_one_policy(self):
        for prompt in (PLANNER_SYSTEM, PLAN_AUDIT_SYSTEM, CODER_SYSTEM):
            with self.subTest(stage=prompt[len(GAME_LANGUAGE_POLICY):].splitlines()[0]):
                self.assertTrue(prompt.startswith(GAME_LANGUAGE_POLICY))
                self.assertEqual(prompt.count(GAME_LANGUAGE_POLICY), 1)

    def test_default_does_not_follow_input_language(self):
        self.assertIn("Use English for player-facing text by default", GAME_LANGUAGE_POLICY)
        self.assertIn("Do not infer the UI language from the language of the input", GAME_LANGUAGE_POLICY)

    def test_explicit_language_and_literal_exceptions(self):
        self.assertIn("original specification overrides this default", GAME_LANGUAGE_POLICY)
        self.assertIn("per-element or bilingual", GAME_LANGUAGE_POLICY)
        self.assertIn("Preserve exact required display strings verbatim", GAME_LANGUAGE_POLICY)
        self.assertIn("explicitly requests translating those strings", GAME_LANGUAGE_POLICY)

    def test_identifiers_and_frozen_assertions_are_preserved(self):
        self.assertIn("Do not translate technical identifiers, selectors, state keys or contract enum values", GAME_LANGUAGE_POLICY)
        self.assertIn("Never rewrite frozen tests", GAME_LANGUAGE_POLICY)
        self.assertIn("planner's text assertions must follow this same policy", GAME_LANGUAGE_POLICY)


if __name__ == "__main__":
    unittest.main()
