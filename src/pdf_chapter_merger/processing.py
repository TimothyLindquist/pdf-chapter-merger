"""Parent-side supervision; never parses PDFs or imports PDF dependencies."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .windows_limits import StagedOutput, WorkerJob

WORKER = Path(__file__).with_name('worker.py')
TIMEOUT_SECONDS = 120


class MergeTask:
    def __init__(self, files, destination, title_pages=True, *, timeout=TIMEOUT_SECONDS,
                 memory_bytes=768 * 1024 * 1024):
        self.process = self.job = self.stage = None
        self.error = None
        self.completed = False
        self.destination = Path(destination).resolve()
        self.paths = [Path(p).resolve() for p in files]
        self.timeout, self.started = timeout, time.monotonic()
        if not self.paths or len(self.paths) > 100:
            raise ValueError('Choose between 1 and 100 PDFs.')
        if self.destination.suffix.lower() != '.pdf':
            raise ValueError('The output filename must end in .pdf.')
        self.check_destination()
        if sum(p.stat().st_size for p in self.paths) > 256 * 1024 * 1024:
            raise ValueError('Input files exceed the combined 256 MiB limit.')
        if any(not p.is_file() or p.suffix.lower() != '.pdf' for p in self.paths):
            raise ValueError('Select PDF files only.')
        request = {'files': [str(p) for p in self.paths], 'titles': bool(title_pages)}
        if len(json.dumps(request).encode('utf-8')) > 120_000:
            raise ValueError('The selected file paths are too long.')
        try:
            self.stage = StagedOutput(self.destination.parent)
            self.job = WorkerJob(memory_bytes)
            request['output_handle'] = int(self.stage.handle)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {'handle_list': [int(self.stage.handle)]}
            os.set_handle_inheritable(self.stage.handle, True)
            try:
                self.process = subprocess.Popen(
                    [sys._base_executable, '-I', '-S', str(WORKER)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    startupinfo=startup, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            finally:
                os.set_handle_inheritable(self.stage.handle, False)
            self.job.assign(self.process)
            # The worker imports no third-party modules and reads no PDF until this gate.
            self.process.stdin.write(json.dumps(request).encode('utf-8') + b'\n')
            self.process.stdin.close()
            self.process.stdin = None
        except Exception:
            self.close()
            raise

    def check_destination(self):
        if self.destination in self.paths or (self.destination.exists() and
                any(os.path.samefile(self.destination, p) for p in self.paths)):
            raise ValueError('Choose an output filename different from your source PDFs.')

    def poll(self):
        if self.process.poll() is not None:
            return True
        if time.monotonic() - self.started > self.timeout:
            self.cancel('Merge exceeded the two-minute time limit.')
            return True
        return False

    def cancel(self, reason='Merge cancelled. No output was replaced.'):
        self.error = reason
        self.close()

    def finish(self):
        if self.completed:
            raise RuntimeError('Merge result already collected.')
        if self.error:
            raise ValueError(self.error)
        if self.process.poll() is None:
            raise RuntimeError('Merge is still running.')
        try:
            result = self.process.stdout.read(8192)
            try:
                result = json.loads(result)
            except (ValueError, UnicodeError):
                raise ValueError('The PDF worker stopped unexpectedly or reached its memory limit.') from None
            if self.process.returncode or result.get('error'):
                raise ValueError(result.get('error', 'PDF processing failed.'))
            if not isinstance(result.get('pages'), int) or not 1 <= result['pages'] <= 2000:
                raise ValueError('Invalid worker result.')
            self.check_destination()
            self.stage.publish(self.destination)
            self.completed = True
            return result['pages']
        finally:
            self.close()

    def close(self):
        if self.job:
            self.job.close()
            self.job = None
        if self.process:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe:
                    pipe.close()
        if self.stage:
            self.stage.close()
