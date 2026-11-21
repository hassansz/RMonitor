import tkinter as tk
import psutil
import time

# Try to load GPU tools safely
try:
    import GPUtil
    has_gpu = True
except ImportError:
    has_gpu = False

class ResourceMonitor:
    def __init__(self, root):
        self.root = root
        
        # Make the window frameless, always-on-top, and slightly transparent
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='#0F0F0F')
        
        # Increased window height to 125px to fit the 3 new labels
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f'155x125+{screen_width - 175}+30')

        self.font_style = ("Consolas", 10, "bold")
        self.bg_color = "#0F0F0F"

        # Initialize network speed trackers
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()

        # Create Labels
        self.cpu_label = tk.Label(root, text="CPU: --%", font=self.font_style, bg=self.bg_color)
        self.cpu_label.pack(pady=(8, 0), anchor="w", padx=15)
        
        self.ram_label = tk.Label(root, text="RAM: --%", font=self.font_style, bg=self.bg_color)
        self.ram_label.pack(pady=0, anchor="w", padx=15)
        
        self.gpu_label = tk.Label(root, text="GPU: N/A", font=self.font_style, bg=self.bg_color)
        self.gpu_label.pack(pady=0, anchor="w", padx=15)
        
        self.net_label = tk.Label(root, text="NET: -- KB/s", font=self.font_style, bg=self.bg_color)
        self.net_label.pack(pady=0, anchor="w", padx=15)
        
        self.bat_label = tk.Label(root, text="PWR: --%", font=self.font_style, bg=self.bg_color)
        self.bat_label.pack(pady=0, anchor="w", padx=15)

        psutil.cpu_percent(interval=0.1)

        # Mouse Bindings
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.root.bind("<Button-3>", lambda e: self.root.quit()) 

        self.update_stats()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        new_x = self.root.winfo_x() + deltax
        new_y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{new_x}+{new_y}")

    def format_speed(self, bytes_per_sec):
        # Dynamically converts bytes to KB/s or MB/s
        if bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:04.1f} KB/s"
        else:
            return f"{bytes_per_sec / (1024 * 1024):04.1f} MB/s"

    def update_stats(self):
        # 1. CPU & RAM
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        self.cpu_label.config(text=f"CPU: {cpu:04.1f}%", fg="#FF3333" if cpu > 80 else ("#FFFF33" if cpu > 50 else "#33FF33"))
        self.ram_label.config(text=f"RAM: {ram:04.1f}%", fg="#FF3333" if ram > 85 else ("#FFFF33" if ram > 65 else "#33FF33"))
        
        # 2. GPU (NVIDIA only via GPUtil)
        if has_gpu:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_load = gpus[0].load * 100
                    self.gpu_label.config(text=f"GPU: {gpu_load:04.1f}%", fg="#FF3333" if gpu_load > 80 else ("#FFFF33" if gpu_load > 50 else "#33FF33"))
            except Exception:
                pass

        # 3. Network (Calculates Download Speed)
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        time_diff = current_time - self.last_time
        
        if time_diff > 0:
            bytes_recv = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_diff
            self.net_label.config(text=f"DL : {self.format_speed(bytes_recv)}", fg="#33FF33")
            
        self.last_net_io = current_net_io
        self.last_time = current_time
        
        # 4. Power / Battery
        battery = psutil.sensors_battery()
        if battery:
            # Check if AC adapter is plugged in
            plug_status = "AC" if battery.power_plugged else "BAT"
            
            # Turn text red if battery is under 20% and NOT charging
            bat_color = "#FF3333" if (battery.percent < 20 and not battery.power_plugged) else "#33FF33"
            self.bat_label.config(text=f"PWR: {battery.percent}% {plug_status}", fg=bat_color)
        
        # Loop every 1000ms
        self.root.after(1000, self.update_stats)

if __name__ == "__main__":
    root = tk.Tk()
    app = ResourceMonitor(root)
    root.mainloop()