// Per-user offline installer. No administrator access, network or vault migration.
using System;
using System.IO;
using System.IO.Compression;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;
using System.Runtime.InteropServices;
using Microsoft.Win32;

static class Setup {
 [DllImport("shell32.dll", CharSet=CharSet.Unicode, ExactSpelling=true)]
 static extern void SHChangeNotify(uint eventId, uint flags, string path, IntPtr secondItem);
 const string AppName = "Password Manager";
 static string Version { get { return ((AssemblyInformationalVersionAttribute)Attribute.GetCustomAttribute(Assembly.GetExecutingAssembly(), typeof(AssemblyInformationalVersionAttribute))).InformationalVersion; } }
 const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\PersonalPasswordManager";
 static string Target = DefaultTarget();
 static string DefaultTarget() {
  using (var key = Registry.CurrentUser.OpenSubKey(UninstallKey)) {
   var saved = key == null ? null : key.GetValue("InstallLocation") as string;
   if (!String.IsNullOrWhiteSpace(saved) && Path.IsPathRooted(saved)) return Path.GetFullPath(saved);
  }
  return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "PersonalPasswordManager");
 }
 static bool ChooseTarget() {
  using (var form = new Form()) {
   form.Text = "Установка Password Manager " + Version;
   form.ClientSize = new System.Drawing.Size(610, 220);
   form.FormBorderStyle = FormBorderStyle.FixedDialog; form.MaximizeBox = false; form.MinimizeBox = false;
   form.StartPosition = FormStartPosition.CenterScreen;
   var label = new Label { Left=20, Top=18, Width=570, Height=38, Text="Выберите папку установки менеджера паролей:" };
   var path = new TextBox { Left=20, Top=59, Width=465, Text=Target };
   var browse = new Button { Left=495, Top=57, Width=95, Text="Обзор…" };
   browse.Click += delegate {
    using (var picker = new FolderBrowserDialog()) {
     picker.Description="Папка установки Password Manager"; picker.SelectedPath=path.Text;
     if (picker.ShowDialog(form) == DialogResult.OK) path.Text=picker.SelectedPath;
    }
   };
   var hint = new Label { Left=20, Top=98, Width=570, Height=48, Text="Будет создан ярлык в меню «Пуск». Пароли сохраняются отдельно в AppData.\nВыберите папку, в которую у вашей учётной записи есть право записи." };
   var install = new Button { Left=355, Top=166, Width=115, Text="Установить" };
   install.Click += delegate {
    try {
     if (String.IsNullOrWhiteSpace(path.Text) || !Path.IsPathRooted(path.Text.Trim())) throw new IOException("Укажите полный путь к папке.");
     string selected=Path.GetFullPath(path.Text.Trim()).TrimEnd(Path.DirectorySeparatorChar);
     if (String.Equals(selected, Path.GetPathRoot(selected).TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase)) throw new IOException("Выберите отдельную папку для приложения.");
     CheckPath(Path.Combine(selected,"probe"), selected);
     if (Directory.Exists(selected) && Directory.GetFileSystemEntries(selected).Length != 0 && !File.Exists(Path.Combine(selected,"installed-files.txt"))) throw new IOException("Папка занята. Выберите пустую папку или папку установленного Password Manager.");
     Target=selected; form.DialogResult=DialogResult.OK;
    } catch (Exception error) { MessageBox.Show(form,error.Message,AppName,MessageBoxButtons.OK,MessageBoxIcon.Warning); }
   };
   var cancel = new Button { Left=480, Top=166, Width=110, Text="Отмена", DialogResult=DialogResult.Cancel };
   form.Controls.AddRange(new Control[] {label,path,browse,hint,install,cancel});
   form.AcceptButton=install; form.CancelButton=cancel;
   return form.ShowDialog() == DialogResult.OK;
  }
 }
 static readonly string Shortcut = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Password Manager.lnk");
 static readonly string[] AllowedArgs = new string[] { "--uninstall", "--remove", "--verify" };
 static void CheckPath(string path, string root) {
  string absolute = Path.GetFullPath(path), prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
  if (!absolute.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new IOException("Путь вне папки программы.");
  for (string parent = Path.GetDirectoryName(absolute); parent != null; parent = Path.GetDirectoryName(parent)) {
   if (Directory.Exists(parent) && (File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0) throw new IOException("Папка содержит перенаправление. Выберите обычную папку.");
  }
  if ((File.Exists(absolute) || Directory.Exists(absolute)) && (File.GetAttributes(absolute) & FileAttributes.ReparsePoint) != 0) throw new IOException("Файл содержит перенаправление.");
 }
 static string Hash(string file) { using (var sha = SHA256.Create()) using (var stream = File.OpenRead(file)) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
 static string ResourceText(string name) {
  using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name)) {
   if (stream == null) throw new IOException("В поставке отсутствует " + name);
   using (var reader = new StreamReader(stream, Encoding.UTF8)) return reader.ReadToEnd();
  }
 }
 static string[] Lines(string text) { return text.Split(new char[] {'\r','\n'}, StringSplitOptions.RemoveEmptyEntries); }
 static void Extract(string destination) {
  if (Directory.Exists(destination)) throw new IOException("Папка проверки уже существует.");
  CheckPath(Path.Combine(destination, "probe"), destination);
  Directory.CreateDirectory(destination);
  using (var payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
   if (payload == null) throw new IOException("Нет файлов программы.");
   using (var archive = new ZipArchive(payload, ZipArchiveMode.Read)) foreach (var entry in archive.Entries) {
    var path = Path.Combine(destination, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
    CheckPath(path, destination);
    Directory.CreateDirectory(Path.GetDirectoryName(path));
    entry.ExtractToFile(path);
   }
  }
  var lines = Lines(ResourceText("payload.sha256"));
  if (Directory.GetFiles(destination, "*", SearchOption.AllDirectories).Length != lines.Length) throw new IOException("Неполная поставка.");
  foreach (var line in lines) {
   var path = Path.Combine(destination, line.Substring(66)); CheckPath(path, destination);
   if (Hash(path) != line.Substring(0,64)) throw new IOException("Проверка файлов не пройдена.");
  }
 }
 static void EnsureClosed() {
  foreach (var process in Process.GetProcessesByName("PasswordManager")) {
   using (process) {
    // Do not force-close a vault or discard unsaved user edits.
    throw new IOException("Закройте Password Manager перед установкой или удалением.");
   }
  }
 }
 static void CreateShortcut() {
  Type shellType = Type.GetTypeFromProgID("WScript.Shell");
  object shell = Activator.CreateInstance(shellType);
  object link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] {Shortcut});
  Type type = link.GetType();
  type.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] {Path.Combine(Target,"PasswordManager.exe")});
  type.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] {Target});
  type.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] {Path.Combine(Target,"PasswordManager.exe") + ",0"});
  type.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] {"Менеджер паролей"});
  type.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
  SHChangeNotify(0x2000, 0x0005, Shortcut, IntPtr.Zero);
  SHChangeNotify(0x2000, 0x0005, Path.Combine(Target,"PasswordManager.exe"), IntPtr.Zero);
 }
 static void Install() {
  EnsureClosed();
  CheckPath(Path.Combine(Target,"probe"), Target);
  if (Directory.Exists(Target) && Directory.GetFileSystemEntries(Target).Length != 0 && !File.Exists(Path.Combine(Target,"installed-files.txt"))) throw new IOException("Папка установки уже занята. Выберите пустую папку.");
  string stage = Target + ".staging-" + Guid.NewGuid().ToString("N");
  Extract(stage);
  string manifest = ResourceText("payload.sha256");
  Directory.CreateDirectory(Target);
  foreach (string line in Lines(manifest)) {
   string relative = line.Substring(66), path = Path.Combine(Target,relative);
   CheckPath(path, Target);
   Directory.CreateDirectory(Path.GetDirectoryName(path));
   File.Copy(Path.Combine(stage,relative), path, true);
   if (Hash(path) != line.Substring(0,64)) throw new IOException("Не удалось проверить установленный файл.");
  }
  string uninstaller = Path.Combine(Target,"Uninstall.exe");
  CheckPath(uninstaller,Target);
  using (var source = Assembly.GetExecutingAssembly().GetManifestResourceStream("uninstall.exe")) using (var file = File.Create(uninstaller)) source.CopyTo(file);
  File.WriteAllText(Path.Combine(Target,"installed-files.txt"), manifest, Encoding.UTF8);
  CreateShortcut();
  using (var key = Registry.CurrentUser.CreateSubKey(UninstallKey)) {
   key.SetValue("DisplayName", AppName); key.SetValue("DisplayVersion", Version);
   key.SetValue("Publisher", "Personal Password Manager"); key.SetValue("InstallLocation", Target);
   key.SetValue("DisplayIcon", Path.Combine(Target,"PasswordManager.exe"));
   key.SetValue("UninstallString", "\"" + uninstaller + "\" --uninstall");
   key.SetValue("NoModify", 1, RegistryValueKind.DWord); key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
  }
  // Only remove the staging files whose exact paths came from this payload.
  foreach (string line in Lines(manifest)) { string path = Path.Combine(stage,line.Substring(66)); CheckPath(path,stage); File.Delete(path); }
  RemoveEmptyDirectories(stage);
  MessageBox.Show("Готово. Найдите Password Manager через поиск Windows.\nПароли сохраняются в %LOCALAPPDATA%\\PersonalPasswordManager.", AppName);
 }
 static void RemoveEmptyDirectories(string root) {
  foreach (string dir in Directory.GetDirectories(root)) { CheckPath(dir,root); RemoveEmptyDirectories(dir); }
  if (Directory.GetFileSystemEntries(root).Length == 0) Directory.Delete(root);
 }
 static void Uninstall(bool removing) {
  EnsureClosed();
  if (!removing) {
   if (MessageBox.Show("Удалить приложение? Хранилище паролей в AppData сохранится.",AppName,MessageBoxButtons.YesNo) != DialogResult.Yes) return;
   string temporary = Path.Combine(Path.GetTempPath(), "PasswordManager-Uninstall-" + Guid.NewGuid().ToString("N") + ".exe");
   File.Copy(Assembly.GetExecutingAssembly().Location, temporary);
   Process.Start(new ProcessStartInfo(temporary, "--remove \"" + Target + "\"") { UseShellExecute = false, CreateNoWindow = true });
   return;
  }
  string manifestPath = Path.Combine(Target,"installed-files.txt");
  CheckPath(manifestPath,Target);
  var lines = Lines(File.ReadAllText(manifestPath,Encoding.UTF8));
  // Validate the complete manifest and all targets before deleting anything.
  foreach (string line in lines) { if (line.Length < 67) throw new IOException("Повреждён список установки."); CheckPath(Path.Combine(Target,line.Substring(66)),Target); }
  CheckPath(Path.Combine(Target,"Uninstall.exe"),Target);
  foreach (string line in lines) File.Delete(Path.Combine(Target,line.Substring(66)));
  File.Delete(Path.Combine(Target,"Uninstall.exe")); File.Delete(manifestPath);
  using (var key = Registry.CurrentUser.OpenSubKey(UninstallKey)) {
   if (key != null && String.Equals(key.GetValue("InstallLocation") as string, Target, StringComparison.OrdinalIgnoreCase)) {
    if (File.Exists(Shortcut)) File.Delete(Shortcut);
    Registry.CurrentUser.DeleteSubKeyTree(UninstallKey,false);
   }
  }
  RemoveEmptyDirectories(Target);
  MessageBox.Show("Приложение удалено. Хранилище паролей в AppData сохранено.",AppName);
 }
 [STAThread] static int Main(string[] args) {
  Application.EnableVisualStyles();
  try {
   if (args.Length == 2 && args[0] == "--wait-pid") {
    int pid;
    if (!Int32.TryParse(args[1],out pid) || pid <= 0 || pid == Process.GetCurrentProcess().Id) throw new IOException("Неверный процесс обновления.");
    try { using (var previous=Process.GetProcessById(pid)) if (!previous.WaitForExit(30000)) throw new IOException("Закройте приложение перед обновлением."); }
    catch (ArgumentException) { }
    args = new string[0];
   }
   if (args.Length == 2 && args[0] == "--verify") { Extract(Path.GetFullPath(args[1])); return 0; }
   if (args.Length == 2 && args[0] == "--remove") { Target=Path.GetFullPath(args[1]); Uninstall(true); return 0; }
   if (args.Length == 0 || (args.Length == 1 && args[0] == "--uninstall")) {
#if UNINSTALLER
    Target=Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
#endif
   }
   if (args.Length == 1 && (args[0] == "--uninstall" || args[0] == "--remove")) { Uninstall(args[0] == "--remove"); return 0; }
#if UNINSTALLER
   Uninstall(false); return 0;
#else
   if (args.Length != 0) throw new IOException("Неизвестный параметр.");
   if (!ChooseTarget()) return 0;
   Install(); return 0;
#endif
  } catch (Exception error) { MessageBox.Show("Операция не завершена.\n" + error.Message,AppName,MessageBoxButtons.OK,MessageBoxIcon.Error); return 1; }
 }
}
