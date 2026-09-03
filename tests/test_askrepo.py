"""Tests for the offline repo-QA core (chunking + lexical retrieval + prompt)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import askrepo  # noqa: E402


def _make_repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix="warden-ask-"))
    (root / "app").mkdir()
    (root / "app" / "auth.py").write_text(
        "def check_token(token):\n    return token == 'secret'\n"
        "def login(user, password):\n    return user == 'admin'\n",
        encoding="utf-8",
    )
    (root / "app" / "payments.py").write_text(
        "def charge(amount):\n    return amount * 1.0\n", encoding="utf-8")
    (root / "README.md").write_text("# demo repo\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return root


class AskRepoTest(unittest.TestCase):
    def setUp(self):
        self.repo = _make_repo()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.repo, ignore_errors=True))

    def test_chunking_skips_git_and_binaries(self):
        chunks = askrepo.iter_chunks(self.repo, window=10, overlap=2)
        paths = {c.path for c in chunks}
        self.assertIn("app/auth.py", paths)
        self.assertNotIn(".git/config", paths)
        self.assertNotIn("assets/icon.png", paths)

    def test_lexical_retrieval_ranks_relevant_file_first(self):
        chunks = askrepo.iter_chunks(self.repo, window=40, overlap=0)
        hits = askrepo.lexical_retrieve("how does token check work", chunks, top_k=2)
        self.assertTrue(hits)
        top = hits[0][1]
        self.assertEqual(top.path, "app/auth.py")

    def test_build_prompt_embeds_citation(self):
        chunks = askrepo.iter_chunks(self.repo, window=40, overlap=0)
        hits = askrepo.lexical_retrieve("login password", chunks, top_k=2)
        prompt = askrepo.build_prompt("how does login work", hits, "demo")
        self.assertIn("app/auth.py:", prompt)
        self.assertIn("how does login work", prompt)

    def test_retrieve_falls_back_to_lexical_when_no_embed_model(self):
        chunks = askrepo.iter_chunks(self.repo, window=40, overlap=0)
        hits = askrepo.retrieve_top("payments charge", chunks, top_k=1, embed=True,
                                    embed_model=None)
        self.assertEqual(hits[0][1].path, "app/payments.py")


if __name__ == "__main__":
    unittest.main()
