"""User-bound Windows DPAPI, fail closed on other platforms."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import uuid

from .crypto import canonical, parse
from .errors import VaultError
from .storage import read_bounded, write_fsynced


class Blob(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data, decrypt=False):
    if os.name != "nt":
        raise VaultError("Защищённое подключение Google доступно только в Windows.")
    if not data or len(data) > 256 * 1024:
        raise VaultError("Некорректные данные подключения.")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes, kernel32.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
    if decrypt:
        function = crypt32.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    else:
        function = crypt32.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise VaultError("Windows не смогла защитить или открыть данные подключения.")
    try:
        return ctypes.string_at(output.data, output.length)
    finally:
        ctypes.memset(output.data, 0, output.length)
        kernel32.LocalFree(output.data)


class ProtectedConnection:
    def __init__(self, root):
        self.path = Path(root) / "google-connection.dpapi"

    @property
    def exists(self): return self.path.exists()

    def load(self):
        return parse(_dpapi(read_bounded(self.path, 256 * 1024), decrypt=True))

    def save(self, value):
        ciphertext = _dpapi(canonical(value))
        temporary = self.path.with_name(f"connection-{uuid.uuid4()}.tmp")
        try:
            write_fsynced(temporary, ciphertext)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def disconnect(self):
        self.path.unlink(missing_ok=True)
