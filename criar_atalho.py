import os
import win32com.client

desktop = r"C:\Users\fulvi\Desktop"
shortcut_path = os.path.join(desktop, "Pluggy Open Finance Explorer (Teste).lnk")

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(shortcut_path)
shortcut.Targetpath = r"C:\Users\fulvi\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
shortcut.Arguments = '"c:\\Users\\fulvi\\Desktop\\API-OPEN FINANCE\\app_explorer.py"'
shortcut.WorkingDirectory = r"c:\Users\fulvi\Desktop\API-OPEN FINANCE"
icon_path = r"c:\Users\fulvi\Desktop\API-OPEN FINANCE\app_icon.ico"
if os.path.exists(icon_path):
    shortcut.IconLocation = icon_path + ",0"
shortcut.Description = "Pluggy Open Finance Explorer & Diagnostics (Modo Teste)"
shortcut.save()
print("Desktop shortcut created successfully at:", shortcut_path)

# Also create a .bat file on Desktop for convenience
bat_path = os.path.join(desktop, "Testar Pluggy Explorer.bat")
with open(bat_path, "w", encoding="utf-8") as f:
    f.write('@echo off\n')
    f.write('cd /d "c:\\Users\\fulvi\\Desktop\\API-OPEN FINANCE"\n')
    f.write('start "" "C:\\Users\\fulvi\\AppData\\Local\\Python\\pythoncore-3.14-64\\pythonw.exe" "app_explorer.py"\n')
print("BAT launcher created successfully at:", bat_path)
