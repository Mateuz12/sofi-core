Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
SCRIPT_DIR = fso.GetParentFolderName(WScript.ScriptFullName)

' Executa run_monitors.py sem janela visivel
WshShell.Run "py -3.14 """ & SCRIPT_DIR & "\run_monitors.py""", 0, False
