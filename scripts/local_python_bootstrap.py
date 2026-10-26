"""Recover the existing bundle's Python modules for offline source verification."""
import sys, os, marshal, zlib, _frozen_importlib
root = os.environ['PM_WORKSPACE']
exe = open(os.path.join(root, 'dist', 'PasswordManager', 'PasswordManager.exe'), 'rb').read()
cookie = exe.rfind(b'MEI\014\013\012\013\016')
number = lambda data: int.from_bytes(data, 'big')
start = cookie + 88 - number(exe[cookie+8:cookie+12])
offset = start + number(exe[cookie+12:cookie+16])
end = offset + number(exe[cookie+16:cookie+20])
boot_modules = {}
while offset < end:
    length = number(exe[offset:offset+4])
    name = exe[offset+18:offset+length].rstrip(b'\0')
    if exe[offset+17:offset+18] == b'z':
        pos = start + number(exe[offset+4:offset+8])
        pyz = exe[pos:pos+number(exe[offset+8:offset+12])]
    elif exe[offset+17:offset+18] in (b'm', b'M'):
        pos = start + number(exe[offset+4:offset+8])
        data = exe[pos:pos+number(exe[offset+8:offset+12])]
        boot_modules[name.decode()] = marshal.loads(zlib.decompress(data) if exe[offset+16] else data)
    offset += length
toc = dict(marshal.loads(pyz[number(pyz[8:12]):]))
class BundleFinder:
    def find_spec(self, fullname, path=None, target=None):
        # Prefer the actual edited source and existing environment packages.
        if fullname in boot_modules:
            return _frozen_importlib.ModuleSpec(fullname, self)
        if fullname not in toc or fullname.startswith(('password_manager', 'PySide6', 'shiboken6', 'cryptography', '_argon2')):
            return None
        return _frozen_importlib.ModuleSpec(fullname, self, is_package=toc[fullname][0] == 1)
    def create_module(self, spec): return None
    def exec_module(self, module):
        if module.__name__ in boot_modules:
            exec(boot_modules[module.__name__], module.__dict__)
            return
        kind, offset, length = toc[module.__name__]
        module.__file__ = os.path.join(root, 'build', 'recovered', module.__name__.replace('.', '/') + '.pyc')
        if kind == 1: module.__path__ = [os.path.dirname(module.__file__)]
        exec(marshal.loads(zlib.decompress(pyz[offset:offset+length])), module.__dict__)
sys.meta_path.append(BundleFinder())
import runpy
args = os.environ['PM_PY_ARGS'].split('\n')
sys.argv = args
if args[0] == '-m':
    sys.argv = args[1:]
    runpy.run_module(args[1], run_name='__main__', alter_sys=True)
elif args[0] == '-c':
    sys.argv = ['-c', *args[2:]]
    exec(args[1], {'__name__': '__main__'})
else:
    with open(args[0], encoding='utf-8') as script:
        exec(compile(script.read(), args[0], 'exec'), {'__name__': '__main__', '__file__': os.path.abspath(args[0])})
