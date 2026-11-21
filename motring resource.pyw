import tkinter as tk
from tkinter import colorchooser, ttk
import psutil
import time
import subprocess
import threading
import re
import sys

DEBUG = "--debug" in sys.argv  # python script.py --debug  -> prints raw Bluetooth scan rows

BT_DEV_ID = re.compile(r"^BTH(ENUM|LE)\\DEV_", re.I)
BT_NAME_OK = re.compile(r"AirPods|Headphones|Earbuds|Buds|Mouse|Keyboard|Watch|Band|Controller|iPhone", re.I)
BT_NAME_BAD = re.compile(r"Microsoft|Intel|Realtek|High Definition|Display Audio|Enumerator|Service|Protocol|Transport|GATT", re.I)


# # ResourceMonitorPro
class ResourceMonitorPro:

    # # __init__
    def __init__(self, root):
        self.root = root

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)

        self.bg_color = "#0F0F0F"
        self.fg_color = "#33FF33"
        self.warn_color = "#FFFF33"
        self.crit_color = "#FF3333"
        self.font_style = ("Consolas", 10, "bold")
        self.mode = tk.StringVar(value="Free Drag")

        self.root.configure(bg=self.bg_color)
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()

        # {name: {"bat": "85" or "--", "connected": True/False}}
        self.all_bt_devices = {}
        # empty = show every connected device automatically
        self.selected_bt_devices = []
        self.bluetooth_devices = "🛜 No BT Connected"
        self._bt_lines = 1
        self.bt_error = ""
        self.gpu_text = "🎮 GPU Searching..."

        self.show_cpu = tk.BooleanVar(value=True)
        self.show_ram = tk.BooleanVar(value=True)
        self.show_gpu = tk.BooleanVar(value=True)
        self.show_net = tk.BooleanVar(value=True)
        self.show_pwr = tk.BooleanVar(value=True)
        self.show_bt = tk.BooleanVar(value=True)

        self.labels = {
            "cpu": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color),
            "ram": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color),
            "gpu": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color),
            "net": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color),
            "pwr": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color),
            "bt": tk.Label(root, font=self.font_style, bg=self.bg_color, fg=self.fg_color, justify="left"),
        }

        self.refresh_layout()

        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.root.bind("<Button-3>", self.open_control_panel)

        threading.Thread(target=self.fetch_bluetooth, daemon=True).start()
        threading.Thread(target=self.fetch_gpu, daemon=True).start()

        self.update_stats()

    # # run_ps
    def run_ps(self, ps_script, timeout=6):
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=timeout,
        )

    # # open_control_panel
    def open_control_panel(self, event=None):
        cp = tk.Toplevel(self.root)
        cp.title("⚙️ Monitor Control Panel")
        cp.geometry("300x500")
        cp.configure(bg="#222222")
        cp.attributes("-topmost", True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCheckbutton", background="#222222", foreground="white")
        style.configure("TRadiobutton", background="#222222", foreground="white")

        tk.Label(cp, text="Modules to Display:", fg="white", bg="#222222", font=("Arial", 10, "bold")).pack(pady=5)
        ttk.Checkbutton(cp, text="💻 CPU Usage", variable=self.show_cpu, command=self.refresh_layout).pack(anchor="w", padx=20)
        ttk.Checkbutton(cp, text="🧠 RAM Usage", variable=self.show_ram, command=self.refresh_layout).pack(anchor="w", padx=20)
        ttk.Checkbutton(cp, text="🎮 GPU", variable=self.show_gpu, command=self.refresh_layout).pack(anchor="w", padx=20)
        ttk.Checkbutton(cp, text="⬇️ Network Speed", variable=self.show_net, command=self.refresh_layout).pack(anchor="w", padx=20)
        ttk.Checkbutton(cp, text="🔋 System Battery", variable=self.show_pwr, command=self.refresh_layout).pack(anchor="w", padx=20)
        ttk.Checkbutton(cp, text="🛜 Bluetooth Devices", variable=self.show_bt, command=self.refresh_layout).pack(anchor="w", padx=20)

        tk.Button(
            cp,
            text="🔍 Select Bluetooth Devices",
            command=self.open_bt_manager,
            bg="#0066cc",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(pady=10, fill="x", padx=40)

        tk.Label(cp, text="Placement Mode:", fg="white", bg="#222222", font=("Arial", 10, "bold")).pack(pady=10)
        ttk.Radiobutton(cp, text="Free Drag (Move anywhere)", variable=self.mode, value="Free Drag", command=self.apply_placement).pack(anchor="w", padx=20)
        ttk.Radiobutton(cp, text="Taskbar (Snap to bottom-right)", variable=self.mode, value="Taskbar", command=self.apply_placement).pack(anchor="w", padx=20)
        ttk.Radiobutton(cp, text="Floating (Snap to top-right)", variable=self.mode, value="Floating", command=self.apply_placement).pack(anchor="w", padx=20)

        tk.Label(cp, text="Design & Colors:", fg="white", bg="#222222", font=("Arial", 10, "bold")).pack(pady=10)
        tk.Button(cp, text="🎨 Pick Main Color", command=self.pick_color, bg="#444", fg="white").pack(pady=5)
        tk.Button(cp, text="❌ Close Monitor", command=self.root.quit, bg="#ff4444", fg="white").pack(side="bottom", pady=15, fill="x", padx=20)

    # # open_bt_manager
    def open_bt_manager(self):
        bt_win = tk.Toplevel(self.root)
        bt_win.title("Bluetooth Scanner")
        bt_win.geometry("280x360")
        bt_win.configure(bg="#222222")
        bt_win.attributes("-topmost", True)

        tk.Label(bt_win, text="Select Devices to Monitor:", bg="#222222", fg="white", font=("Arial", 10, "bold")).pack(pady=8)
        tk.Label(bt_win, text="(Select none = show all connected)", bg="#222222", fg="#aaa", font=("Arial", 8)).pack()

        listbox = tk.Listbox(bt_win, selectmode=tk.MULTIPLE, bg="#333333", fg="white", highlightthickness=0)
        listbox.pack(fill="both", expand=True, padx=15, pady=8)

        listed = []  # device names in the same order as the listbox rows

        # # populate_list
        def populate_list():
            listed.clear()
            listbox.delete(0, tk.END)
            devices = dict(self.all_bt_devices)
            if not devices:
                listbox.insert(tk.END, "No devices found yet...")
                return
            for idx, (dev, info) in enumerate(devices.items()):
                listed.append(dev)
                state = "connected" if info["connected"] else "off"
                listbox.insert(tk.END, f"{dev}  ({state})")
                if dev in self.selected_bt_devices:
                    listbox.select_set(idx)

        populate_list()

        # # trigger_refresh
        def trigger_refresh():
            refresh_btn.config(state="disabled", text="Scanning...")
            worker = threading.Thread(target=self.scan_bluetooth_once, daemon=True)
            worker.start()

            # # wait_scan
            def wait_scan():
                if worker.is_alive():
                    bt_win.after(300, wait_scan)
                else:
                    populate_list()
                    refresh_btn.config(state="normal", text="🔄 Refresh Scan")

            wait_scan()

        # # save_selection
        def save_selection():
            if listed:
                self.selected_bt_devices = [listed[i] for i in listbox.curselection() if i < len(listed)]
                self.update_bluetooth_display()
                self.refresh_layout()
            bt_win.destroy()

        refresh_btn = tk.Button(bt_win, text="🔄 Refresh Scan", command=trigger_refresh, bg="#444444", fg="white", font=("Arial", 9, "bold"))
        refresh_btn.pack(pady=(0, 6), fill="x", padx=15)
        tk.Button(bt_win, text="💾 Save & Track", command=save_selection, bg="#0066cc", fg="white", font=("Arial", 9, "bold")).pack(pady=(0, 10), fill="x", padx=15)

    # # pick_color
    def pick_color(self):
        color_code = colorchooser.askcolor(title="Choose Main Color")[1]
        if color_code:
            self.fg_color = color_code
            for label in self.labels.values():
                label.config(fg=self.fg_color)

    # # apply_placement
    def apply_placement(self):
        mode = self.mode.get()
        width = 195

        active_mods = sum([self.show_cpu.get(), self.show_ram.get(), self.show_gpu.get(), self.show_net.get(), self.show_pwr.get()])
        height = active_mods * 25
        if self.show_bt.get():
            bt_lines = max(1, self.bluetooth_devices.count("\n") + 1)
            height += (bt_lines * 20) + 15

        if mode == "Taskbar":
            self.root.geometry(f"{width}x{height}+{self.screen_w - width - 10}+{self.screen_h - height - 50}")
        elif mode == "Floating":
            self.root.geometry(f"{width}x{height}+{self.screen_w - width - 10}+30")
        else:
            current_pos = self.root.geometry().split("+")
            if len(current_pos) == 3:
                self.root.geometry(f"{width}x{height}+{current_pos[1]}+{current_pos[2]}")

    # # refresh_layout
    def refresh_layout(self):
        for label in self.labels.values():
            label.pack_forget()

        if self.show_cpu.get():
            self.labels["cpu"].pack(pady=1, anchor="w", padx=8)
        if self.show_ram.get():
            self.labels["ram"].pack(pady=1, anchor="w", padx=8)
        if self.show_gpu.get():
            self.labels["gpu"].pack(pady=1, anchor="w", padx=8)
        if self.show_net.get():
            self.labels["net"].pack(pady=1, anchor="w", padx=8)
        if self.show_pwr.get():
            self.labels["pwr"].pack(pady=1, anchor="w", padx=8)
        if self.show_bt.get():
            self.labels["bt"].pack(pady=5, anchor="w", padx=8)
        self.apply_placement()

    # # start_move
    def start_move(self, event):
        if self.mode.get() == "Free Drag":
            self.x = event.x
            self.y = event.y

    # # do_move
    def do_move(self, event):
        if self.mode.get() == "Free Drag":
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    # # fetch_gpu
    def fetch_gpu(self):
        while True:
            try:
                res = self.run_ps("(Get-CimInstance Win32_VideoController)[0].Name", timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    name = res.stdout.strip().replace("Graphics", "").replace("Family", "").strip()[:14]
                    self.gpu_text = f"🎮 {name}"
                else:
                    wmic_res = subprocess.run(
                        ["wmic", "path", "win32_VideoController", "get", "name"],
                        shell=False,
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=4,
                    )
                    if wmic_res.returncode == 0:
                        lines = [ln.strip() for ln in wmic_res.stdout.strip().split("\n") if ln.strip()]
                        if len(lines) > 1:
                            name = lines[1].replace("Graphics", "").replace("Family", "").strip()[:14]
                            self.gpu_text = f"🎮 {name}"
                        else:
                            self.gpu_text = "🎮 GPU N/A"
                    else:
                        self.gpu_text = "🎮 GPU N/A"
            except Exception:
                self.gpu_text = "🎮 GPU Error"
            time.sleep(10)

    # # get_bt_icon
    def get_bt_icon(self, dev_name):
        name = dev_name.lower()
        if any(x in name for x in ["airpods", "head", "ear", "bud"]):
            return "🎧"
        if "mouse" in name:
            return "🖱️"
        if "key" in name:
            return "⌨️"
        if "watch" in name or "band" in name:
            return "⌚"
        if "xbox" in name or "controller" in name:
            return "🎮"
        return "📱"

    # # normalize_device_name
    def normalize_device_name(self, raw_name):
        name = raw_name.strip()
        if "airpods pro" in name.lower():
            return "AirPods Pro"
        if "airpods" in name.lower():
            return "AirPods"
        if "iphone" in name.lower():
            return "iPhone"
        return name

    # # update_bluetooth_display
    def update_bluetooth_display(self):
        if self.bt_error:
            self.bluetooth_devices = f"🛜 {self.bt_error}"
            return

        devices = self.all_bt_devices

        if self.selected_bt_devices:
            names = list(self.selected_bt_devices)
        else:
            names = [n for n, d in devices.items() if d["connected"]]

        lines = []
        for dev in names:
            info = devices.get(dev)
            icon = self.get_bt_icon(dev)
            if not info or not info["connected"]:
                lines.append(f"{icon} {dev[:12]} | OFF")
            else:
                bat = info["bat"]
                value = f"{bat}%" if str(bat).isdigit() else "N/A"
                lines.append(f"{icon} {dev[:12]} | {value}")

        self.bluetooth_devices = "\n".join(lines) if lines else "🛜 No BT Connected"

    # # scan_bluetooth_once
    def scan_bluetooth_once(self):
        # Reads every Bluetooth-related node, with its container id (one container = one physical device).
        # The battery value is often stored on a sibling node (HID / hands-free), not on the main device node.
        ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$batKey = '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2'
$conKey = '{83DA6326-97A6-4088-9453-A1923F573B29} 15'
$ctrKey = '{8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C} 2'
Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.Name -and $_.PNPDeviceID -match 'BTH|00805F9B34FB'
} | ForEach-Object {
    $id = $_.PNPDeviceID
    $bat = (Get-PnpDeviceProperty -InstanceId $id -KeyName $batKey).Data
    $con = (Get-PnpDeviceProperty -InstanceId $id -KeyName $conKey).Data
    $ctr = (Get-PnpDeviceProperty -InstanceId $id -KeyName $ctrKey).Data
    "$ctr|$id|$($_.Name)|$bat|$con|$($_.ConfigManagerErrorCode)"
}
"""
        try:
            res = self.run_ps(ps_script, timeout=45)
            self.bt_error = "" if res.returncode == 0 else "BT scan error"
            if DEBUG:
                print("---- BT scan ----")
                print("container | instance id | name | battery | connected | code")
                print(res.stdout)

            rows = []
            for line in res.stdout.strip().splitlines():
                parts = [x.strip() for x in line.split("|")]
                if len(parts) < 6:
                    continue
                rows.append(
                    {"ctr": parts[0], "id": parts[1], "name": parts[2], "bat": parts[3], "con": parts[4].lower(), "code": parts[5]}
                )

            # battery per physical device: take it from ANY node in the same container
            bat_by_ctr = {}
            for r in rows:
                if r["bat"].isdigit() and r["ctr"] and not r["ctr"].lower().startswith("{00000000-0000-0000-ffff"):
                    bat_by_ctr.setdefault(r["ctr"], r["bat"])

            scanned = {}
            for r in rows:
                if BT_NAME_BAD.search(r["name"]) or r["code"] != "0":
                    continue
                is_main = bool(BT_DEV_ID.match(r["id"])) or (BT_NAME_OK.search(r["name"]) and "BTH" in r["id"].upper())
                if not is_main:
                    continue

                name = self.normalize_device_name(r["name"])
                if not name:
                    continue

                if r["con"] in ("true", "false"):
                    connected = r["con"] == "true"
                else:
                    connected = True

                bat = r["bat"] if r["bat"].isdigit() else bat_by_ctr.get(r["ctr"], "--")

                entry = scanned.setdefault(name, {"bat": "--", "connected": False})
                if connected:
                    entry["connected"] = True
                    if str(bat).isdigit():
                        entry["bat"] = bat

            self.all_bt_devices = scanned
        except Exception:
            self.all_bt_devices = {}
            self.bt_error = "BT scan timeout"

        self.update_bluetooth_display()

    # # fetch_bluetooth
    def fetch_bluetooth(self):
        while True:
            self.scan_bluetooth_once()
            time.sleep(3)

    # # update_stats
    def update_stats(self):
        if self.show_cpu.get():
            cpu = psutil.cpu_percent(interval=None)
            self.labels["cpu"].config(
                text=f"💻 {cpu:04.1f}%",
                fg=self.crit_color if cpu > 80 else (self.warn_color if cpu > 50 else self.fg_color),
            )

        if self.show_ram.get():
            ram = psutil.virtual_memory().percent
            self.labels["ram"].config(
                text=f"🧠 {ram:04.1f}%",
                fg=self.crit_color if ram > 85 else (self.warn_color if ram > 65 else self.fg_color),
            )

        if self.show_gpu.get():
            self.labels["gpu"].config(text=self.gpu_text, fg=self.fg_color)

        if self.show_net.get():
            curr_io = psutil.net_io_counters()
            now = time.time()
            diff = now - self.last_time
            if diff > 0:
                bps = (curr_io.bytes_recv - self.last_net_io.bytes_recv) / diff
                spd = f"{bps / 1024:04.1f} KB/s" if bps < 1048576 else f"{bps / 1048576:04.1f} MB/s"
                self.labels["net"].config(text=f"⬇️ {spd}")
            self.last_net_io = curr_io
            self.last_time = now

        if self.show_pwr.get():
            bat = psutil.sensors_battery()
            if bat:
                stat = "AC" if bat.power_plugged else "BAT"
                col = self.crit_color if (bat.percent < 20 and not bat.power_plugged) else self.fg_color
                self.labels["pwr"].config(text=f"🔋 {bat.percent}% {stat}", fg=col)

        if self.show_bt.get():
            self.labels["bt"].config(text=self.bluetooth_devices)
            # resize the window when devices connect or disconnect
            lines = self.bluetooth_devices.count("\n") + 1
            if lines != self._bt_lines:
                self._bt_lines = lines
                self.apply_placement()

        self.root.after(1000, self.update_stats)


# # main
if __name__ == "__main__":
    root = tk.Tk()
    app = ResourceMonitorPro(root)
    root.mainloop()