import ctypes
import shutil
import sys
import os
import threading
import time
import queue
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import winsound
import pystray
from PIL import Image, ImageDraw
import win32file
import win32con

# ================= CONFIG =================
CONFIG_FILE = "config.json"
POLL_INTERVAL_SECONDS = 1

USB_DRIVE = Path("U:/")
USB_MUSIC = USB_DRIVE / "music"
LOCAL_MUSIC = Path("C:/Users/beeman/Music/testing")
EXPECTED_VOLUME_NAME = "IPOD"

# ---------------- CONFIG ----------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# ---------------- HELPERS ----------------
def get_volume_label(drive: Path) -> str | None:
    try:
        buf = ctypes.create_unicode_buffer(1024)
        success = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(str(drive)),
            buf,
            ctypes.sizeof(buf),
            None,
            None,
            None,
            None,
            0,
        )
        return buf.value if success else None
    except Exception:
        return None

def collect_local_files(base_dir: Path):
    return [p for p in base_dir.rglob("*") if p.is_file()]

def eject_drive_windows(drive_letter: str) -> bool:
    try:
        path = f"\\\\.\\{drive_letter.strip(':')}:"
        handle = win32file.CreateFile(
            path,
            win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            0,
            None
        )
        win32file.DeviceIoControl(handle, 0x2D4808, None, None)
        handle.Close()
        return True
    except:
        return False

def create_image(drive_status: bool) -> Image.Image:
    img = Image.new('RGB', (64, 64), color=(0,0,0,0))
    d = ImageDraw.Draw(img)
    color = (0,200,0) if drive_status else (200,0,0)
    d.ellipse((8,8,56,56), fill=color)
    return img

def center_window(win, width=None, height=None):
    win.update_idletasks()
    if width is None: width = win.winfo_width()
    if height is None: height = win.winfo_height()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

# ---------------- FIRST-TIME SETUP ----------------
def first_launch_setup(root):
    config = {}
    setup_win = tk.Toplevel(root)
    setup_win.title("First-Time Setup")
    setup_win.geometry("500x450")
    setup_win.resizable(False, False)
    setup_win.grab_set()
    center_window(setup_win)

    def on_close():
        messagebox.showinfo("Setup Cancelled","First-time setup must be completed to run the app.", parent=root)
        root.destroy()
        sys.exit(0)
    setup_win.protocol("WM_DELETE_WINDOW", on_close)

    frame = ttk.Frame(setup_win, padding=15)
    frame.pack(fill="both", expand=True)

    # Drive Letter
    ttk.Label(frame, text="USB Drive Letter:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
    drives = [f"{d}:" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    drive_var = tk.StringVar(value=drives[0] if drives else "")
    drive_menu = ttk.OptionMenu(frame, drive_var, drive_var.get(), *drives)
    drive_menu.pack(anchor="w", pady=(0,10))
    ttk.Button(frame, text="Refresh Drive Letters", command=lambda: refresh_drives(drive_var, drive_menu)).pack(anchor="w", pady=(0,15))

    # Volume Name
    ttk.Label(frame, text="Expected USB Volume Name:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
    volume_var = tk.StringVar(value="IPOD")
    ttk.Entry(frame, textvariable=volume_var).pack(anchor="w", fill="x", pady=(0,15))

    # Remote Folder
    ttk.Label(frame, text="Remote Folder on USB:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
    remote_var = tk.StringVar()
    remote_label = ttk.Label(frame, text="", foreground="blue")
    remote_label.pack(anchor="w")
    def choose_remote():
        path = filedialog.askdirectory(title="Select Remote Folder on USB")
        if path:
            remote_var.set(path)
            remote_label.config(text=path)
    ttk.Button(frame, text="Browse...", command=choose_remote).pack(anchor="w", pady=(0,15))

    # Local Folder
    ttk.Label(frame, text="Local Music Folder:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
    local_var = tk.StringVar()
    local_label = ttk.Label(frame, text="", foreground="blue")
    local_label.pack(anchor="w")
    def choose_local():
        path = filedialog.askdirectory(title="Select Local Music Folder")
        if path:
            local_var.set(path)
            local_label.config(text=path)
    ttk.Button(frame, text="Browse...", command=choose_local).pack(anchor="w", pady=(0,15))

    # Save Button
    def save_setup():
        if not drive_var.get() or not remote_var.get() or not local_var.get() or not volume_var.get():
            messagebox.showwarning("Incomplete","Please select all settings.", parent=setup_win)
            return
        config["USB_DRIVE"] = drive_var.get()
        config["REMOTE_FOLDER"] = remote_var.get()
        config["LOCAL_FOLDER"] = local_var.get()
        config["EXPECTED_VOLUME_NAME"] = volume_var.get()
        save_config(config)
        setup_win.destroy()
        messagebox.showinfo("Setup Complete","Settings saved successfully.", parent=root)

    ttk.Button(frame, text="Save Settings", command=save_setup).pack(pady=10)
    root.wait_window(setup_win)
    return config

def refresh_drives(option_var, menu_widget):
    drives = [f"{d}:" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    option_var.set(drives[0] if drives else "")
    menu = menu_widget["menu"]
    menu.delete(0,"end")
    for d in drives:
        menu.add_command(label=d, command=lambda value=d: option_var.set(value))

# ---------------- SYNC APP ----------------
class SyncApp:
    def __init__(self, root):
        self.root = root
        self.progress_queue = queue.Queue()
        self.sync_running = False
        self.synced_this_session = False
        self.drive_present = False
        self.shutdown_requested = False

        style = ttk.Style()
        style.theme_use("clam")

        self.tray_icon = pystray.Icon("music_sync")
        self.tray_icon.icon = create_image(False)
        self.tray_icon.title = "USB Music Sync"
        self.tray_icon.menu = pystray.Menu(
            pystray.MenuItem("Sync Now", self.manual_sync, enabled=lambda item: not self.sync_running),
            pystray.MenuItem("Settings", self.edit_settings),
            pystray.MenuItem("Exit", self.exit_app)
        )

        threading.Thread(target=self.usb_watcher, daemon=True).start()
        threading.Thread(target=self.tray_run, daemon=True).start()

    # ---------------- USB WATCHER ----------------
    def usb_watcher(self):
        while not self.shutdown_requested:
            try:
                drive_exists = USB_DRIVE.exists()
            except OSError:
                drive_exists = False
            label = get_volume_label(USB_DRIVE) if drive_exists else None
            prev = self.drive_present
            self.drive_present = drive_exists and label == EXPECTED_VOLUME_NAME
            self.tray_icon.icon = create_image(self.drive_present)
            self.tray_icon.visible = True
            if self.drive_present and not prev and not self.synced_this_session and not self.sync_running:
                self.root.after(0, self.ask_to_sync)
            elif not self.drive_present:
                self.synced_this_session = False
            time.sleep(POLL_INTERVAL_SECONDS)

    # ---------------- SETTINGS ----------------
    def edit_settings(self, icon=None, item=None):
        config = load_config() or {}
        setup_win = tk.Toplevel(self.root)
        setup_win.title("Edit Settings")
        setup_win.geometry("500x450")
        setup_win.resizable(False, False)
        setup_win.grab_set()
        center_window(setup_win)

        frame = ttk.Frame(setup_win, padding=15)
        frame.pack(fill="both", expand=True)

        # Drive Letter
        ttk.Label(frame, text="USB Drive Letter:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
        drives = [f"{d}:" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        drive_var = tk.StringVar(value=config.get("USB_DRIVE", drives[0] if drives else ""))
        drive_menu = ttk.OptionMenu(frame, drive_var, drive_var.get(), *drives)
        drive_menu.pack(anchor="w", pady=(0,10))
        ttk.Button(frame, text="Refresh Drive Letters", command=lambda: refresh_drives(drive_var, drive_menu)).pack(anchor="w", pady=(0,15))

        # Volume Name
        ttk.Label(frame, text="Expected USB Volume Name:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
        volume_var = tk.StringVar(value=config.get("EXPECTED_VOLUME_NAME","IPOD"))
        ttk.Entry(frame, textvariable=volume_var).pack(anchor="w", fill="x", pady=(0,15))

        # Remote Folder
        ttk.Label(frame, text="Remote Folder on USB:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
        remote_var = tk.StringVar(value=config.get("REMOTE_FOLDER",""))
        remote_label = ttk.Label(frame, text=remote_var.get(), foreground="blue")
        remote_label.pack(anchor="w")
        def choose_remote():
            path = filedialog.askdirectory(title="Select Remote Folder on USB")
            if path:
                remote_var.set(path)
                remote_label.config(text=path)
        ttk.Button(frame, text="Browse...", command=choose_remote).pack(anchor="w", pady=(0,15))

        # Local Folder
        ttk.Label(frame, text="Local Music Folder:", font=("Segoe UI",10,"bold")).pack(pady=(0,5), anchor="w")
        local_var = tk.StringVar(value=config.get("LOCAL_FOLDER",""))
        local_label = ttk.Label(frame, text=local_var.get(), foreground="blue")
        local_label.pack(anchor="w")
        def choose_local():
            path = filedialog.askdirectory(title="Select Local Music Folder")
            if path:
                local_var.set(path)
                local_label.config(text=path)
        ttk.Button(frame, text="Browse...", command=choose_local).pack(anchor="w", pady=(0,15))

        # Save Button
        def save_changes():
            config["USB_DRIVE"] = drive_var.get()
            config["REMOTE_FOLDER"] = remote_var.get()
            config["LOCAL_FOLDER"] = local_var.get()
            config["EXPECTED_VOLUME_NAME"] = volume_var.get()
            save_config(config)
            messagebox.showinfo("Saved","Settings updated successfully.", parent=setup_win)
            setup_win.destroy()

        ttk.Button(frame, text="Save Changes", command=save_changes).pack(pady=10)

    # ---------------- USB POPUP ----------------
    def ask_to_sync(self):
        if self.shutdown_requested:
            return
        self.sync_running = True

        popup = tk.Toplevel(self.root)
        popup.title("USB Detected")
        popup.geometry("400x150")
        popup.resizable(False, False)
        popup.grab_set()
        popup.attributes("-topmost", True)
        center_window(popup,400,150)

        ttk.Label(popup, text="Music USB detected.\nWould you like to sync now?", font=("Segoe UI",11)).pack(pady=20)
        response = tk.BooleanVar()
        def yes(): response.set(True); popup.destroy()
        def no(): response.set(False); popup.destroy()
        frm = ttk.Frame(popup); frm.pack(pady=10)
        ttk.Button(frm,text="Yes", command=yes).pack(side="left", padx=10)
        ttk.Button(frm,text="No", command=no).pack(side="right", padx=10)

        popup.update(); popup.focus_force(); popup.wait_window()
        if response.get(): self.start_sync()
        else: self.sync_running=False

    def manual_sync(self, icon=None, item=None):
        if self.drive_present and not self.sync_running:
            self.start_sync()

    # ---------------- SYNC ----------------
    def start_sync(self):
        if self.shutdown_requested: return
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("Syncing Music")
        w,h = 500,300
        center_window(self.progress_window,w,h)
        self.progress_window.resizable(False, False)

        ttk.Label(self.progress_window,text="Syncing music to USB...", font=("Segoe UI",10)).pack(pady=10)
        self.progress_bar = ttk.Progressbar(self.progress_window, orient="horizontal", length=450, mode="determinate")
        self.progress_bar.pack(pady=10)

        self.verbose_text = scrolledtext.ScrolledText(self.progress_window,width=65,height=10,state='disabled')
        self.verbose_text.pack(pady=5)

        threading.Thread(target=self.sync_worker, daemon=True).start()
        self.root.after(100,self.update_progress_ui)

    def sync_worker(self):
        if self.shutdown_requested: return
        USB_MUSIC.mkdir(parents=True, exist_ok=True)
        local_files = collect_local_files(LOCAL_MUSIC)
        usb_files = {f.relative_to(USB_MUSIC) for f in USB_MUSIC.rglob("*") if f.is_file()}
        total,copied,skipped = len(local_files),0,0
        self.progress_queue.put(("init",total))
        for idx, src in enumerate(local_files,start=1):
            if self.shutdown_requested: break
            rel = src.relative_to(LOCAL_MUSIC)
            dest = USB_MUSIC/rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if rel in usb_files:
                skipped+=1
                msg = f"Skipped: {rel} ({idx}/{total} - {int(idx/total*100)}%)"
            else:
                shutil.copy2(src,dest)
                copied+=1
                msg = f"Copied: {rel} ({idx}/{total} - {int(idx/total*100)}%)"
            self.progress_queue.put(("progress", idx, copied, skipped, msg))
        self.progress_queue.put(("done", copied, skipped))

    def update_progress_ui(self):
        if self.shutdown_requested: self.root.quit(); return
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg[0]=="init": self.progress_bar["maximum"]=msg[1]
                elif msg[0]=="progress":
                    _,cur,copied,skipped,text = msg
                    self.progress_bar["value"]=cur
                    self.verbose_text.config(state='normal')
                    self.verbose_text.insert(tk.END,text+"\n")
                    self.verbose_text.see(tk.END)
                    self.verbose_text.config(state='disabled')
                elif msg[0]=="done":
                    _,copied,skipped = msg
                    self.finish_sync(copied,skipped)
                    return
        except queue.Empty: pass
        self.root.after(100,self.update_progress_ui)

    # ---------------- FINISH ----------------
    def finish_sync(self, copied, skipped):
        if self.shutdown_requested: return
        self.progress_window.destroy()
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        self.synced_this_session=True
        self.sync_running=False

        result = messagebox.askyesno(
            "Sync Complete",
            f"Music sync completed.\nCopied: {copied}\nSkipped: {skipped}\n\nWould you like to safely eject the drive now?",
            parent=self.root
        )

        if result:
            if eject_drive_windows(USB_DRIVE.drive):
                messagebox.showinfo("Safe to Remove","You may now safely remove the USB drive.", parent=self.root)
            else:
                messagebox.showwarning("Eject Failed","Automatic eject failed. Eject manually.", parent=self.root)
        else:
            messagebox.showinfo("Remember","Remember to safely eject your USB drive before removing it.", parent=self.root)

    # ---------------- TRAY ----------------
    def tray_run(self): self.tray_icon.run()
    def exit_app(self,icon=None,item=None):
        self.shutdown_requested=True
        try: self.root.destroy()
        except: pass
        self.tray_icon.stop(); sys.exit(0)

# ---------------- ENTRY ----------------
def main():
    root = tk.Tk()
    root.withdraw()
    config = load_config()
    if config is None: config = first_launch_setup(root)

    global USB_DRIVE, USB_MUSIC, LOCAL_MUSIC, EXPECTED_VOLUME_NAME
    USB_DRIVE = Path(config["USB_DRIVE"]+"/")
    USB_MUSIC = Path(config["REMOTE_FOLDER"])
    LOCAL_MUSIC = Path(config["LOCAL_FOLDER"])
    EXPECTED_VOLUME_NAME = config["EXPECTED_VOLUME_NAME"]

    if not LOCAL_MUSIC.exists():
        messagebox.showerror("Error",f"Local folder not found:\n{LOCAL_MUSIC}", parent=root)
        sys.exit(1)

    app = SyncApp(root)
    threading.Thread(target=app.tray_icon.run, daemon=True).start()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.shutdown_requested=True
        try: root.destroy()
        except: pass
        app.tray_icon.stop()
        sys.exit(130)

if __name__=="__main__":
    main()
