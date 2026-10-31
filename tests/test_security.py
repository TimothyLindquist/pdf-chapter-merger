import _support
import ctypes
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject
from pdf_chapter_merger import merge
from pdf_chapter_merger.merge import chapter_page, merge_pdfs
from pdf_chapter_merger.processing import MergeTask
from pdf_chapter_merger.windows_limits import WorkerJob, StagedOutput

ROOT = Path(__file__).resolve().parents[1]


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.pdf'
        self.output = self.folder / 'merged.pdf'
        writer = PdfWriter()
        writer.add_page(chapter_page('Source', 1))
        writer.write(self.source)
        writer.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_actions_attachments_forms_removed_and_safe_links_preserved(self):
        writer = PdfWriter()
        page = writer.add_page(chapter_page('Source', 1))
        script = DictionaryObject({NameObject('/S'): NameObject('/JavaScript'), NameObject('/JS'): TextStringObject('inert marker')})
        page[NameObject('/AA')] = DictionaryObject({NameObject('/O'): script})
        writer.add_js('/* inert document marker */')
        writer.add_attachment('secret.txt', b'attachment marker')
        page['/Resources'][NameObject('/Audit')] = DictionaryObject({NameObject('/AA'): script, NameObject('/EF'): script})
        def annotation(action=None, subtype='/Link'):
            result = DictionaryObject({NameObject('/Subtype'): NameObject(subtype),
                NameObject('/Rect'): ArrayObject([NumberObject(n) for n in (0, 0, 40, 40)])})
            if action:
                result[NameObject('/A')] = action
            return result
        safe = DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject('https://example.com'), NameObject('/Next'): script})
        writer.add_annotation(0, annotation(safe))
        for kind in ('/Launch', '/GoToR', '/SubmitForm', '/JavaScript'):
            writer.add_annotation(0, annotation(DictionaryObject({NameObject('/S'): NameObject(kind), NameObject('/JS'): TextStringObject('marker')})))
        for uri in ('file:///C:/Windows/win.ini', 'javascript:alert(1)', 'mailto:a@example.com?attach=C:/secret'):
            writer.add_annotation(0, annotation(DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject(uri)})))
        writer.add_annotation(0, annotation(subtype='/Widget'))
        writer.add_annotation(0, annotation(subtype='/FileAttachment'))
        internal = annotation()
        internal[NameObject('/Dest')] = ArrayObject([page.indirect_reference, NameObject('/Fit')])
        writer.add_annotation(0, internal)
        writer.write(self.source)
        writer.close()
        merge_pdfs([self.source], self.output, False)
        reader = PdfReader(self.output)
        annotations = [x.get_object() for x in reader.pages[0]['/Annots']]
        self.assertEqual(len(annotations), 2)
        self.assertEqual(annotations[0]['/A']['/URI'], 'https://example.com')
        self.assertEqual(annotations[1]['/Dest'][0].idnum, reader.pages[0].indirect_reference.idnum)
        self.assertNotIn('/Names', reader.trailer['/Root'])
        self.assertNotIn('/AcroForm', reader.trailer['/Root'])
        # Inspect every written indirect object, including unused cloned objects.
        from pypdf.generic import IndirectObject
        for generation, entries in reader.xref.items():
            for number in entries:
                if number:
                    item = reader.get_object(IndirectObject(number, generation, reader))
                    self.check_object(item, set())

    def check_object(self, item, seen):
        if id(item) in seen:
            return
        seen.add(id(item))
        if isinstance(item, dict):
            self.assertFalse(set(item) & merge.DROP_KEYS)
            self.assertNotIn(str(item.get('/S', '')), merge.ACTION_TYPES)
            if '/S' in item:
                self.assertNotIn('/Next', item)
            self.assertNotIn(str(item.get('/Type', '')), ('/Filespec', '/EmbeddedFile'))
            for value in item.values():
                self.check_object(value, seen)
        elif isinstance(item, list):
            for value in item:
                self.check_object(value, seen)

    def test_all_encryption_rejected_without_output_change(self):
        self.output.write_bytes(b'existing output')
        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        writer.encrypt('', 'owner-secret')
        writer.write(self.source)
        writer.close()
        with self.assertRaisesRegex(ValueError, 'Encrypted PDFs are not accepted'):
            merge_pdfs([self.source], self.output)
        self.assertEqual(self.output.read_bytes(), b'existing output')
        self.assertFalse(list(self.folder.glob('.pdfmerger-*')))

    def test_cancel_and_timeout_preserve_existing_output_and_cleanup(self):
        self.output.write_bytes(b'existing')
        task = MergeTask([self.source], self.output)
        stage = task.stage.path
        task.cancel()
        self.assertIsNotNone(task.process.poll())
        self.assertFalse(stage.exists())
        self.assertEqual(self.output.read_bytes(), b'existing')
        task = MergeTask([self.source], self.output, timeout=-1)
        task.poll()
        with self.assertRaisesRegex(ValueError, 'time limit'):
            task.finish()
        self.assertFalse(task.stage.path.exists())
        self.assertEqual(self.output.read_bytes(), b'existing')

    def test_file_page_and_output_limits(self):
        with self.assertRaisesRegex(ValueError, '100 PDFs'):
            MergeTask([self.source] * 101, self.output)
        with patch.object(merge, 'MAX_PAGES', 1):
            with self.assertRaisesRegex(ValueError, 'page limit'):
                merge.build_pdf([self.source], BytesIO(), True)
        with patch.object(merge, 'MAX_OUTPUT_BYTES', 3):
            with self.assertRaisesRegex(ValueError, 'output exceeds'):
                merge.LimitedOutput(BytesIO()).write(b'1234')
        with self.assertRaisesRegex(ValueError, 'end in .pdf'):
            MergeTask([self.source], self.folder / 'output.bat')

    def test_kernel_memory_and_child_process_limits(self):
        code = "import sys; sys.stdin.readline();\ntry:\n x=bytearray(256*1024*1024)\n print('unexpected allocation')\nexcept MemoryError:\n print('memory limited')\nimport subprocess\ntry:\n subprocess.run([sys.executable,'-I','-S','-c','pass'],check=True)\n print('unexpected child')\nexcept OSError:\n print('child limited')"
        process = subprocess.Popen([sys._base_executable, '-I', '-S', '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        job = WorkerJob(64 * 1024 * 1024)
        try:
            job.assign(process)
            stdout, stderr = process.communicate(b'go\n', timeout=10)
            self.assertEqual(process.returncode, 0, stderr.decode(errors='replace'))
            self.assertIn(b'memory limited', stdout)
            self.assertIn(b'child limited', stdout)
        finally:
            job.close()
            process.wait(timeout=5)

    def test_delete_pending_stage_and_abrupt_exit_cleanup(self):
        stage = StagedOutput(self.folder)
        try:
            with self.assertRaises(OSError):
                stage.path.read_bytes()
        finally:
            stage.close()
        self.assertFalse(stage.path.exists())
        code = "import sys,os; from pathlib import Path; sys.path.insert(0,str(Path(sys.argv[1])/'src')); from pdf_chapter_merger.windows_limits import StagedOutput; s=StagedOutput(Path(sys.argv[2])); print(s.path,flush=True); os._exit(0)"
        result = subprocess.run([sys._base_executable, '-I', '-S', '-c', code, str(ROOT), str(self.folder)],
                                capture_output=True, text=True, check=True, timeout=10)
        self.assertFalse(Path(result.stdout.strip()).exists())


if __name__ == '__main__':
    unittest.main()
