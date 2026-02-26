' Запуск CryptoConsult без видимого окна
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c """ & WshShell.CurrentDirectory & "\Start-CryptoConsult.bat""", 0, False
