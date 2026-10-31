"""PDF construction, invoked inside the limited worker."""
from pathlib import Path
import textwrap
from urllib.parse import urlsplit
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DictionaryObject, NameObject, NumberObject,
                           FloatObject, TextStringObject, DecodedStreamObject)

MAX_FILES = 100
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_PAGES = 2000
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
DROP_KEYS = {'/AA', '/OpenAction', '/JS', '/JavaScript', '/AF', '/EF',
             '/EmbeddedFiles', '/XFA', '/AcroForm', '/RichMediaContent',
             '/RichMediaSettings', '/PresSteps', '/Collection', '/Launch'}
ACTION_TYPES = {'/JavaScript', '/Launch', '/GoToR', '/GoToE', '/SubmitForm',
                '/ImportData', '/Rendition', '/Movie', '/Sound', '/Named',
                '/SetOCGState', '/Hide', '/ResetForm', '/Trans', '/GoTo3DView', '/Thread'}


def chapter_page(title, number):
    """Use a standard PDF font without external font parsers or startup plugins."""
    writer = PdfWriter()
    page = writer.add_blank_page(595.28, 841.89)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica'),
        NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    def literal(value):
        return b'(' + b''.join(f'\\{byte:03o}'.encode() for byte in value.encode('cp1252', errors='replace')) + b')'
    content = b'0.12 0.23 0.32 rg BT /F1 12 Tf 60 715 Td ' + literal(f'CHAPTER {number}') + b' Tj ET\n'
    lines = textwrap.wrap(title, width=29) or ['Untitled']
    # Helvetica glyphs fit within roughly one em; leave a little extra margin.
    size = min(26, 470 / (1.05 * max(map(len, lines))), 470 / max(1, len(lines)))
    for index, line in enumerate(lines):
        content += f'BT /F1 {size:.2f} Tf 60 {660-index*(size+9):.2f} Td '.encode() + literal(line) + b' Tj ET\n'
    if title.encode('cp1252', errors='replace').decode('cp1252') != title:
        content += b'BT /F1 10 Tf 60 90 Td (Full Unicode title is available in the bookmark.) Tj ET\n'
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject('/Contents')] = writer._add_object(stream)
    return page


def safe_uri(value):
    if not isinstance(value, str) or len(value) > 4096 or '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme.lower() in ('http', 'https') and bool(parsed.hostname)
                and not parsed.username and not parsed.password) or (parsed.scheme.lower() == 'mailto'
                and '@' in parsed.path and not parsed.query and not parsed.fragment
                and '%' not in parsed.path and ':' not in parsed.path and '/' not in parsed.path)
    except ValueError:
        return False


def strip_active_objects(writer):
    """Visit all cloned objects, including unused objects still in the writer."""
    seen, pending = set(), list(writer._objects)
    visits = 0
    while pending:
        item = pending.pop()
        item = item.get_object() if hasattr(item, 'get_object') else item
        if id(item) in seen:
            continue
        seen.add(id(item))
        visits += 1
        if visits > 500_000:
            raise ValueError('PDF object limit exceeded.')
        if isinstance(item, DictionaryObject):
            if str(item.get('/S', '')) in ACTION_TYPES or str(item.get('/Type', '')) in ('/EmbeddedFile', '/Filespec'):
                item.clear()
                continue
            if '/S' in item:
                item.pop('/Next', None)  # Action chains; bookmark /Next links are structural.
            for key in list(item):
                if str(key) in DROP_KEYS or str(key) == '/A':
                    del item[key]
            pending.extend(item.values())
        elif isinstance(item, ArrayObject):
            pending.extend(item)


def collect_links(reader, offset):
    """Rebuild links from an allowlist; never clone annotation objects."""
    ids = {p.indirect_reference.idnum: index for index, p in enumerate(reader.pages)}
    links = []
    for index, page in enumerate(reader.pages):
        annotations = page.get('/Annots', [])
        annotations = annotations.get_object() if hasattr(annotations, 'get_object') else annotations
        if len(annotations) > 1000:
            raise ValueError('Page annotation limit (1,000) exceeded.')
        for reference in annotations:
            annotation = reference.get_object()
            if not isinstance(annotation, DictionaryObject) or annotation.get('/Subtype') != '/Link':
                continue
            rect = annotation.get('/Rect', [])
            if len(rect) != 4 or not all(isinstance(x, (NumberObject, FloatObject)) and abs(float(x)) <= 1e6 for x in rect):
                continue
            action = annotation.get('/A', {})
            action = action.get_object() if hasattr(action, 'get_object') else action
            uri = action.get('/URI') if isinstance(action, dict) and action.get('/S') == '/URI' else None
            dest = annotation.get('/Dest')
            if dest is None and isinstance(action, dict) and action.get('/S') == '/GoTo':
                dest = action.get('/D')
            if isinstance(dest, str):
                named = reader.named_destinations.get(dest)
                target = reader.get_destination_page_number(named) if named else None
            elif isinstance(dest, ArrayObject) and dest:
                target = ids.get(getattr(dest[0], 'idnum', None))
            else:
                target = None
            if safe_uri(uri):
                links.append((offset + index, [float(x) for x in rect], str(uri), None))
            elif target is not None and 0 <= target < len(reader.pages):
                links.append((offset + index, [float(x) for x in rect], None, offset + target))
    return links


class LimitedOutput:
    def __init__(self, stream):
        self.stream = stream
    def write(self, value):
        if self.stream.tell() + len(value) > MAX_OUTPUT_BYTES:
            raise ValueError('Merged output exceeds the 256 MiB limit.')
        return self.stream.write(value)
    def __getattr__(self, name):
        return getattr(self.stream, name)


def build_pdf(files, output, title_pages=True):
    if not files or len(files) > MAX_FILES:
        raise ValueError('Choose between 1 and 100 PDFs.')
    paths = [Path(p).resolve() for p in files]
    if sum(p.stat().st_size for p in paths) > MAX_INPUT_BYTES:
        raise ValueError('Input files exceed the combined 256 MiB limit.')
    writer, links, total = PdfWriter(), [], 0
    try:
        for number, path in enumerate(paths, 1):
            try:
                with path.open('rb') as source:
                    data = source.read(MAX_INPUT_BYTES + 1)
                total += len(data)
                if total > MAX_INPUT_BYTES:
                    raise ValueError('Input files exceed the combined 256 MiB limit.')
                reader = PdfReader(BytesIO(data))
                if reader.is_encrypted:
                    raise ValueError('Encrypted PDFs are not accepted, including files with an empty password. Export an unencrypted copy deliberately before merging.')
                count = len(reader.pages)
                if not count or len(writer.pages) + count + int(title_pages) > MAX_PAGES:
                    raise ValueError('Empty PDF or combined page limit (2,000) exceeded.')
                start = len(writer.pages)
                if title_pages:
                    writer.add_page(chapter_page(path.stem, number))
                links.extend(collect_links(reader, len(writer.pages)))
                for page in reader.pages:
                    writer.add_page(page, excluded_keys=['/Annots', '/AA', '/B', '/AF', '/PresSteps', '/Metadata'])
                parent = writer.add_outline_item(path.stem, start)
                def copy_outline(items, ancestor, depth=0):
                    if depth > 30:
                        raise ValueError('Source bookmark nesting exceeds 30 levels.')
                    previous = ancestor
                    for item in items:
                        if isinstance(item, list):
                            copy_outline(item, previous, depth + 1)
                        else:
                            target = reader.get_destination_page_number(item)
                            if target is not None and 0 <= target < count:
                                previous = writer.add_outline_item(item.title, start + int(title_pages) + target, parent=ancestor)
                copy_outline(reader.outline, parent)
            except Exception as exc:
                raise ValueError(f'{path.name}: {exc}') from exc
        strip_active_objects(writer)
        for page, rect, uri, target in links:
            annotation = DictionaryObject({NameObject('/Type'): NameObject('/Annot'),
                NameObject('/Subtype'): NameObject('/Link'), NameObject('/Rect'): ArrayObject([FloatObject(n) for n in rect]),
                NameObject('/Border'): ArrayObject([NumberObject(0)] * 3)})
            if uri:
                annotation[NameObject('/A')] = DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject(uri)})
            else:
                annotation[NameObject('/Dest')] = ArrayObject([writer.pages[target].indirect_reference, NameObject('/Fit')])
            writer.add_annotation(page, annotation)
        writer.page_mode = '/UseOutlines'
        writer.add_metadata({'/Title': 'Merged chapters', '/Creator': 'PDF Chapter Merger'})
        writer.write(LimitedOutput(output))
        output.flush()
        return len(writer.pages)
    finally:
        writer.close()


def merge_pdfs(files, destination, title_pages=True):
    """Synchronous API with the same resource limits as the UI."""
    import time
    from .processing import MergeTask
    task = MergeTask(files, destination, title_pages)
    try:
        while not task.poll():
            time.sleep(.02)
        return task.finish()
    finally:
        task.close()
