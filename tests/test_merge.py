import _support
import hashlib
from pathlib import Path
import tempfile
import unittest
from pypdf import PdfReader, PdfWriter
from pdf_chapter_merger.merge import merge_pdfs, chapter_page


class MergeTests(unittest.TestCase):
    def test_seven_chapters(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            folder = Path(directory)
            files = []
            for number in range(1, 8):
                path = folder / f'Chapter {number}.pdf'
                writer = PdfWriter()
                writer.add_page(chapter_page(f'Source content {number}', number))
                writer.add_outline_item('Original bookmark', 0)
                writer.write(path)
                writer.close()
                files.append(path)
            original = [hashlib.sha256(p.read_bytes()).digest() for p in files]
            output = folder / 'merged.pdf'
            for titles in (True, False):
                self.assertEqual(merge_pdfs(files, output, titles), 14 if titles else 7)
                reader = PdfReader(output)
                chapters = [item for item in reader.outline if not isinstance(item, list)]
                self.assertEqual([item.title for item in chapters], [p.stem for p in files])
                for index, chapter in enumerate(chapters):
                    start = index * (2 if titles else 1)
                    self.assertEqual(reader.get_destination_page_number(chapter), start)
                    self.assertIn(f'Source content {index + 1}', reader.pages[start + int(titles)].extract_text())
                    nested = reader.outline[index * 2 + 1][0]
                    self.assertEqual(reader.get_destination_page_number(nested), start + int(titles))
            with self.assertRaises(ValueError):
                merge_pdfs(files, files[0])
            broken = folder / 'broken.pdf'
            broken.write_text('not a pdf')
            before = output.read_bytes()
            with self.assertRaises(ValueError):
                merge_pdfs([files[0], broken], output)
            self.assertEqual(output.read_bytes(), before)
            locked = folder / 'locked.pdf'
            writer = PdfWriter()
            writer.add_blank_page(100, 100)
            writer.encrypt('secret')
            writer.write(locked)
            writer.close()
            with self.assertRaises(ValueError):
                merge_pdfs([locked], output)
            self.assertEqual(original, [hashlib.sha256(p.read_bytes()).digest() for p in files])


if __name__ == '__main__':
    unittest.main()
