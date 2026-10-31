"""Windows kernel-enforced worker limits and delete-pending output staging."""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import uuid

kernel = C.WinDLL('kernel32', use_last_error=True)
SIZE = C.c_size_t


class Basic(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64),
        ('flags', W.DWORD), ('min_working', SIZE), ('max_working', SIZE),
        ('active_processes', W.DWORD), ('affinity', SIZE),
        ('priority', W.DWORD), ('scheduling', W.DWORD)]


class IO(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class Extended(C.Structure):
    _fields_ = [('basic', Basic), ('io', IO), ('process_memory', SIZE),
        ('job_memory', SIZE), ('peak_process_memory', SIZE), ('peak_job_memory', SIZE)]


kernel.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]
kernel.CreateJobObjectW.restype = W.HANDLE
kernel.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
kernel.SetInformationJobObject.restype = W.BOOL
kernel.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
kernel.AssignProcessToJobObject.restype = W.BOOL
kernel.CloseHandle.argtypes = [W.HANDLE]
kernel.CloseHandle.restype = W.BOOL
kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
kernel.CreateFileW.restype = W.HANDLE
kernel.SetFileInformationByHandle.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
kernel.SetFileInformationByHandle.restype = W.BOOL
kernel.FlushFileBuffers.argtypes = [W.HANDLE]
kernel.FlushFileBuffers.restype = W.BOOL


def checked(result):
    if not result:
        raise C.WinError(C.get_last_error())
    return result


class WorkerJob:
    def __init__(self, memory_bytes=768 * 1024 * 1024):
        self.handle = checked(kernel.CreateJobObjectW(None, None))
        limits = Extended()
        # One process, committed-memory limit, kill worker when the parent closes/dies.
        limits.basic.flags = 0x8 | 0x100 | 0x2000 | 0x400
        limits.basic.active_processes = 1
        limits.process_memory = memory_bytes
        try:
            checked(kernel.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except Exception:
            self.close()
            raise

    def assign(self, process):
        checked(kernel.AssignProcessToJobObject(self.handle, W.HANDLE(int(process._handle))))

    def close(self):
        if self.handle:
            kernel.CloseHandle(self.handle)
            self.handle = None


class StagedOutput:
    """Windows deletes the staged plaintext when the last handle closes.

    It is delete-pending during parsing, so it cannot be opened by a new path-based
    reader. Only the parent and the explicitly inherited worker handle can use it.
    """
    def __init__(self, directory):
        self.path = Path(directory) / ('.pdfmerger-' + uuid.uuid4().hex + '.tmp')
        self.handle = kernel.CreateFileW(str(self.path), 0x80000000 | 0x40000000 | 0x10000,
            1 | 2 | 4, None, 1, 0x100, None)
        if self.handle == C.c_void_p(-1).value:
            self.handle = None
            raise C.WinError(C.get_last_error())
        self.published = False
        try:
            self.mark_delete(True)
        except Exception:
            self.close()
            self.path.unlink(missing_ok=True)
            raise

    def mark_delete(self, enabled):
        flag = W.BOOLEAN(enabled)
        checked(kernel.SetFileInformationByHandle(self.handle, 4, C.byref(flag), C.sizeof(flag)))

    def publish(self, destination):
        checked(kernel.FlushFileBuffers(self.handle))
        # Stop automatic deletion only for the final atomic publication step.
        self.mark_delete(False)
        try:
            os.replace(self.path, destination)
            self.published = True
        except Exception:
            self.mark_delete(True)
            raise

    def close(self):
        if self.handle:
            kernel.CloseHandle(self.handle)
            self.handle = None
