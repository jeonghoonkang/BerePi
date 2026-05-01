from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from pipeline_common import SUPPORTED_MODEL_OPTIONS, build_user_message, model_supports_tools
from rag_webdav import format_retrieved_contexts, read_local_markdown_files, retrieve_markdown_chunks


class RagPipelineTests(unittest.TestCase):
    def test_supported_models_all_receive_shared_markdown_context(self) -> None:
        contexts = [
            "[Markdown Source] notes/runbook.md\n[Chunk] 0\n[Score] 1.000\nBackup steps are listed here."
        ]

        for model in SUPPORTED_MODEL_OPTIONS:
            prompt = build_user_message(
                prompt="How do I restore the backup?",
                excel_contexts=[],
                markdown_contexts=contexts,
                allow_tools=model_supports_tools(model),
                workspace_root=Path("/tmp/workspace"),
            )
            self.assertIn("[Markdown Source] notes/runbook.md", prompt)

    def test_qwen_coder_models_keep_tool_mode_while_gemma_does_not(self) -> None:
        self.assertTrue(model_supports_tools("qwen2.5-coder:7b"))
        self.assertTrue(model_supports_tools("qwen3-coder:30b"))
        self.assertFalse(model_supports_tools("gemma3:4b"))

    def test_markdown_retrieval_uses_cached_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "notes"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "backup.md").write_text(
                "# Backup\nUse rsync for backup.\nRestore requires manifest validation.\n",
                encoding="utf-8",
            )
            (docs_dir / "other.md").write_text(
                "# Other\nThis note covers unrelated camera settings.\n",
                encoding="utf-8",
            )

            documents = read_local_markdown_files(root)
            chunks = retrieve_markdown_chunks("restore backup manifest", documents, max_chunks=2)
            contexts = format_retrieved_contexts(chunks)

            self.assertTrue(contexts)
            self.assertIn("backup.md", contexts[0])
            self.assertIn("Restore requires manifest validation", contexts[0])


if __name__ == "__main__":
    unittest.main()
