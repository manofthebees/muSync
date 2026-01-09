# muSync (USB Music Sync)

A small Windows tray application that syncs music from a local folder to a USB drive when the drive with the expected volume name is inserted. The app provides a tray icon, automatic sync prompt, manual "Sync Now" option, settings GUI, and an interactive sync progress window.

**Requirements**
- **Python**: 3.10 or newer (the code uses 3.10+ type syntax)
- **OS**: Windows (uses win32 APIs and winsound)
- **Packages**: Install from `requirements.txt` or via `pip`:

  ```powershell
  python -m pip install -r requirements.txt
  ```

  Typical dependencies include: `pystray`, `Pillow`, `pywin32` (and `tkinter` which is included with standard Windows Python).

**Quick Start (run script)**
- Open a terminal in the project folder and run:

  ```powershell
  python syncSysTray.py
  ```

- On first run a setup window will open. Provide:
  - **USB Drive Letter** (e.g. `E:`)
  - **Expected USB Volume Name** (e.g. `IPOD`) — the application checks the inserted drive's volume label
  - **Remote Folder on USB** (path on the USB where music will be copied)
  - **Local Music Folder** (the folders with your music files on the PC)

- The settings are saved to `config.json` in the same folder as the script.
- After setup, the app runs in the system tray. When the configured USB is inserted (and volume name matches), you'll be prompted to sync.
- You can also right-click the tray icon and choose **Sync Now** or **Settings**.

**Config file**
- `config.json` stores the following keys: `USB_DRIVE`, `REMOTE_FOLDER`, `LOCAL_FOLDER`, `EXPECTED_VOLUME_NAME`.
- Example:

  ```json
  {
    "USB_DRIVE": "E:",
    "REMOTE_FOLDER": "E:/music",
    "LOCAL_FOLDER": "C:/Users/you/Music",
    "EXPECTED_VOLUME_NAME": "IPOD"
  }
  ```

**Making an executable (Windows) using PyInstaller**
- Create and activate a virtual environment (recommended):

  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  python -m pip install pyinstaller
  ```

- Basic single-file build (no console window):

  ```powershell
  pyinstaller --onefile --noconsole syncSysTray.py
  ```

  This will produce `dist\syncSysTray.exe`.

- Include an icon (replace `app.ico` with your icon file):

  ```powershell
  pyinstaller --onefile --noconsole --icon=app.ico syncSysTray.py
  ```

- If you want to include a default `config.json` with the exe, add it as data (Windows path separator uses `;`):

  ```powershell
  pyinstaller --onefile --noconsole --add-data "config.json;." syncSysTray.py
  ```

  Notes about `--add-data` on Windows: the argument format is `SRC;DEST`.

- After building, the executable is located in `dist\`. Double-click to run.

**Troubleshooting & Tips**
- If the tray icon doesn't appear or modules are reported missing, build without `--onefile` first to debug:

  ```powershell
  pyinstaller --noconsole syncSysTray.py
  ```

  Then run the generated folder in `dist\syncSysTray\` to see logs and module issues.

- If PyInstaller misses hidden imports, add `--hidden-import` flags for the reported modules.
- `tkinter` is included with standard Windows Python installers; if missing, install a Python distribution that includes it.
- When testing eject behavior, run the app as Administrator if you have permission issues with device control.

**Files**
- `syncSysTray.py`: Main application script.
- `requirements.txt`: Python dependencies (install with `pip install -r requirements.txt`).
- `config.json`: Generated at first run (you can create a template for packaging).

**License**
See the `LICENSE` file in this repository.

---
