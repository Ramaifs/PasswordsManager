using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
class LocalPython {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern bool SetDllDirectory(string path);
 [DllImport("python314.dll", CallingConvention=CallingConvention.Cdecl)] static extern void Py_Initialize();
 [DllImport("python314.dll", CallingConvention=CallingConvention.Cdecl)] static extern int PyRun_SimpleString(byte[] code);
 [DllImport("python314.dll", CallingConvention=CallingConvention.Cdecl)] static extern int Py_FinalizeEx();
 static int Main(string[] args) {
  string root = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, ".."));
  string runtime = Path.Combine(root, "dist", "PasswordManager", "_internal");
  SetDllDirectory(runtime);
  Environment.SetEnvironmentVariable("PYTHONHOME", runtime);
  Environment.SetEnvironmentVariable("PYTHONPATH", runtime + Path.PathSeparator + Path.Combine(runtime,"base_library.zip") + Path.PathSeparator + Path.Combine(root,".venv","Lib","site-packages") + Path.PathSeparator + Path.Combine(root,"src"));
  Environment.SetEnvironmentVariable("PM_WORKSPACE", root);
  Environment.SetEnvironmentVariable("PM_PY_ARGS", string.Join("\n", args));
  Py_Initialize();
  int result = PyRun_SimpleString(Encoding.UTF8.GetBytes(File.ReadAllText(Path.Combine(root,"scripts","local_python_bootstrap.py")) + "\0"));
  int finish = Py_FinalizeEx();
  return result == 0 && finish == 0 ? 0 : 1;
 }
}
