import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import knowledge as k  # noqa: E402


class InstantAnswers(unittest.TestCase):
    def test_definitions_answer_instantly(self):
        for q in ("what is a replica set", "What is sharding?", "define write concern", "explain journaling", "what is RAG"):
            self.assertIsNotNone(k.answer(q), q)

    def test_every_lab_has_an_answer(self):
        for n in range(7, 19):
            self.assertIn(f"Lab {n}", k.answer(f"explain lab {n}"))

    def test_actions_and_detail_requests_fall_through_to_the_model(self):
        for q in ("run lab 8", "lab 8 status", "explain lab 9 in detail", "why does my replica set fail",
                  "how do I fix this error", "show output of lab 9", "hello there", "x " * 12):
            self.assertIsNone(k.answer(q), q)

    def test_empty_input(self):
        self.assertIsNone(k.answer(""))
        self.assertIsNone(k.answer(None))


if __name__ == "__main__":
    unittest.main()
