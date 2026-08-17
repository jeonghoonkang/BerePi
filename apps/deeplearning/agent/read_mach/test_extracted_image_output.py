from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from extracted_image_output import output_extracted_images


class ExtractedImageOutputTests(unittest.TestCase):
    def test_writes_images_below_output_extract_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "slides.pptx"
            result = output_extracted_images(
                [("ppt/media/image.png", b"first"), ("other/image.png", b"second")],
                source_path=source,
                output_dir=root / "result",
            )

            self.assertEqual(
                result.directory,
                (root / "result" / "extract_image" / "slides_pptx").resolve(),
            )
            self.assertEqual([path.name for path in result.files], [
                "0001_image.png", "0002_image.png",
            ])
            self.assertEqual([path.read_bytes() for path in result.files], [b"first", b"second"])
            self.assertFalse(result.removed)

    def test_remove_image_deletes_only_the_current_document_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "result"
            source = root / "slides.pptx"
            saved = output_extracted_images(
                [("ppt/media/image.png", b"image")],
                source_path=source,
                output_dir=output_dir,
            )
            other_directory = output_dir / "extract_image" / "other_docx"
            other_directory.mkdir(parents=True)
            other_file = other_directory / "0001_other.png"
            other_file.write_bytes(b"keep")

            removed = output_extracted_images(
                [("ppt/media/image.png", b"image")],
                source_path=source,
                output_dir=output_dir,
                rm_image=True,
            )

            self.assertFalse(saved.directory.exists())
            self.assertTrue(other_file.exists())
            self.assertEqual(removed.files, ())
            self.assertTrue(removed.removed)


if __name__ == "__main__":
    unittest.main()
