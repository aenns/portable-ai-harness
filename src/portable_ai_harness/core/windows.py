"""Windows native process jobs and pinned, non-reparse filesystem access.

Imported only by the Windows backend. No shell, administrator requirement or
third-party runtime. Calls fail closed when the OS denies the required boundary.
"""

import ctypes
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes as w
from pathlib import Path


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", w.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", w.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", w.DWORD),
        ("SchedulingClass", w.DWORD),
    ]


class EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BASIC_LIMIT),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class ACCOUNTING(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_longlong)
        for name in (
            "TotalUserTime",
            "TotalKernelTime",
            "ThisPeriodTotalUserTime",
            "ThisPeriodTotalKernelTime",
        )
    ] + [
        (name, w.DWORD)
        for name in (
            "TotalPageFaultCount",
            "TotalProcesses",
            "ActiveProcesses",
            "TotalTerminatedProcesses",
        )
    ]


class FILE_INFO(ctypes.Structure):
    _fields_ = [
        ("attributes", w.DWORD),
        ("creation", w.FILETIME),
        ("access", w.FILETIME),
        ("write", w.FILETIME),
        ("volume", w.DWORD),
        ("size_high", w.DWORD),
        ("size_low", w.DWORD),
        ("links", w.DWORD),
        ("index_high", w.DWORD),
        ("index_low", w.DWORD),
    ]


def api():
    """Explicit ABI declarations prevent 64-bit handle truncation."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    declarations = {
        "CloseHandle": ([w.HANDLE], w.BOOL),
        "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
        "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
        "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
        "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
        "QueryInformationJobObject": (
            [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p],
            w.BOOL,
        ),
        "CreateFileW": (
            [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE],
            w.HANDLE,
        ),
        "GetFileInformationByHandle": ([w.HANDLE, ctypes.POINTER(FILE_INFO)], w.BOOL),
    }
    for name, (args, result) in declarations.items():
        function = getattr(kernel, name)
        function.argtypes = args
        function.restype = result
    return kernel


def checked(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


class Job:
    """Attach a waiting launcher before it may start any reviewed project program."""

    def __init__(self):
        self.kernel = api()
        self.handle = checked(self.kernel.CreateJobObjectW(None, None))
        try:
            limits = EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            checked(
                self.kernel.SetInformationJobObject(
                    self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
                )
            )
        except BaseException:
            self.close()
            raise

    def launch(self, argv, *, cwd, env):
        # -I prevents cwd/PYTHON* injection into the harness's own launcher.
        # EOF or a missing token exits without executing the reviewed command.
        launcher = (
            "import os,subprocess,sys;"
            "token=sys.stdin.buffer.read(1);"
            "sys.stdin.close();"
            "result=subprocess.call(sys.argv[1:],stdin=subprocess.DEVNULL) if token==b'G' else 125;"
            "os._exit(result if result<0x80000000 else result-0x100000000)"
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", launcher, *argv],
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            checked(self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)))
            process.stdin.write(b"G")
            process.stdin.flush()
        except BaseException:
            process.kill()
            process.wait(timeout=2)
            process.stdout.close()
            process.stderr.close()
            raise
        finally:
            process.stdin.close()
        return process

    def stop(self, process):
        try:
            checked(self.kernel.TerminateJobObject(self.handle, 1))
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                state = ACCOUNTING()
                checked(
                    self.kernel.QueryInformationJobObject(
                        self.handle, 1, ctypes.byref(state), ctypes.sizeof(state), None
                    )
                )
                if not state.ActiveProcesses:
                    process.wait(timeout=1)
                    return True
                time.sleep(0.01)
            return False
        except (OSError, subprocess.SubprocessError):
            return False
        finally:
            self.close()

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def open_handle(path, *, directory=False, create=False, write=False):
    kernel = api()
    # A read-access handle without SHARE_DELETE prevents directory replacement.
    # Metadata-only (zero-access) handles did not enforce this boundary on CI.
    # OPEN_REPARSE_POINT opens the link itself so attributes can reject it.
    if create:
        with private_security() as security:
            handle = kernel.CreateFileW(str(path), 0x40000000, 1, security, 1, 0x00200000, None)
    else:
        handle = kernel.CreateFileW(
            str(path),
            0x80000000,  # GENERIC_READ for directories as well as files.
            3 if directory else 1,
            None,
            3,
            0x00200000 | (0x02000000 if directory else 0),
            None,
        )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = FILE_INFO()
        checked(kernel.GetFileInformationByHandle(handle, ctypes.byref(info)))
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise OSError("Reparse points and unexpected file types are denied")
        if not directory and not create and info.links != 1:
            raise OSError("Hard-linked input is denied on Windows")
        return handle
    except BaseException:
        kernel.CloseHandle(handle)
        raise


@contextmanager
def pinned_directory(root: Path, parts=(), *, create=False):
    """Pin every ancestor from the drive root; local NTFS is the supported baseline."""
    root = root.absolute()
    if root.drive.startswith("\\\\"):
        raise OSError("Use a local Windows workspace, not a UNC share")
    handles = []
    kernel = api()
    current = Path(root.anchor)
    try:
        handles.append(open_handle(current, directory=True))
        for part in [*root.parts[1:], *parts]:
            current = current / part
            if create:
                try:
                    kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.c_void_p]
                    kernel.CreateDirectoryW.restype = w.BOOL
                    with private_security() as security:
                        checked(kernel.CreateDirectoryW(str(current), security))
                except FileExistsError:
                    pass
            handles.append(open_handle(current, directory=True))
        yield current
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


def open_stream(path, *, create=False):
    import msvcrt

    handle = open_handle(path, create=create, write=create)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_WRONLY if create else os.O_RDONLY))
    except BaseException:
        api().CloseHandle(handle)
        raise
    return os.fdopen(fd, "wb" if create else "rb")


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", w.DWORD)]


@contextmanager
def private_security():
    """Protected DACL for new objects: current user and LocalSystem only."""
    kernel = api()
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    advapi.OpenProcessToken.restype = w.BOOL
    advapi.GetTokenInformation.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        w.DWORD,
        ctypes.POINTER(w.DWORD),
    ]
    advapi.GetTokenInformation.restype = w.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = w.BOOL
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    token = w.HANDLE()
    sid_text = w.LPWSTR()
    descriptor = ctypes.c_void_p()
    checked(advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)))
    try:
        size = w.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value or size.value > 65536:
            raise OSError("Cannot determine current-user security identity")
        data = ctypes.create_string_buffer(size.value)
        checked(advapi.GetTokenInformation(token, 1, data, size, ctypes.byref(size)))
        sid = ctypes.cast(data, ctypes.POINTER(SID_AND_ATTRIBUTES)).contents.sid
        checked(advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)))
        sddl = f"D:P(A;OICI;FA;;;{sid_text.value})(A;OICI;FA;;;SY)"
        checked(
            advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, 1, ctypes.byref(descriptor), None
            )
        )
        attributes = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
        yield ctypes.byref(attributes)
    finally:
        kernel.CloseHandle(token)
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        if descriptor:
            kernel.LocalFree(descriptor)
