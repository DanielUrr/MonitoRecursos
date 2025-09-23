import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import psutil
import platform
import time

# Intentar usar GPUtil (opcional)
try:
    import GPUtil
    GPUtil_available = True
except Exception:
    GPUtil_available = False

import matplotlib.style as style
style.use('dark_background')  # Tema oscuro

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class EdgeWidget:
    def __init__(self, width=405, height=260, y=60, step=18, delay=10, hide_gap=8):
        # Tamaño compacto (por defecto)
        self.compact_width = width
        self.compact_height = height
        

        # Tamaño expandido (Task Manager style)
        self.expanded_width = 820
        self.expanded_height = 520

        self.y = y
        self.step = step
        self.delay = delay
        self.hide_gap = hide_gap

        # Ventana
        self.root = ttk.Window(themename="darkly")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.root.update_idletasks()
        self.screen_w = self.root.winfo_screenwidth()
        self.open_x = self.screen_w - self.compact_width
        self.closed_x = self.screen_w - self.hide_gap
        self.cur_x = self.closed_x

        # Iniciar en modo compacto (no expandido)
        self.expanded = False

        # Flags y prev counters
        self.is_open = False
        self.animating = False
        self.leave_after = None
        self.pinned = False

        self.prev_net = psutil.net_io_counters()
        self.prev_disk = psutil.disk_io_counters()
        self.prev_time = time.time()
        psutil.cpu_percent(None)

        # paneles y datos
        self.panels = {}
        self.current_panel = "cpu"

        self.build_ui()
        

        # Eventos
        self.root.bind("<Enter>", self.on_enter)
        self.root.bind("<Leave>", self.on_leave)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.update_stats()

        

    # ---------------- Construcción UI ----------------
    def build_ui(self):
        # contenedor principal
        self.container = ttk.Frame(self.root, padding=8)
        self.container.pack(fill="both", expand=True)

        # Top bar (compacta) - horizontal buttons
        self.top = ttk.Frame(self.container)
        self.top.pack(fill="x", pady=(0, 6))

        self.btn_cpu = ttk.Button(self.top, text="CPU", bootstyle=PRIMARY, command=lambda: self.show_panel("cpu"))
        self.btn_cpu.pack(side="left", padx=2)
        self.btn_ram = ttk.Button(self.top, text="RAM", bootstyle=INFO, command=lambda: self.show_panel("ram"))
        self.btn_ram.pack(side="left", padx=2)
        self.btn_disk = ttk.Button(self.top, text="DISCO", bootstyle=WARNING, command=lambda: self.show_panel("disk"))
        self.btn_disk.pack(side="left", padx=2)
        self.btn_net = ttk.Button(self.top, text="RED", bootstyle=SUCCESS, command=lambda: self.show_panel("net"))
        self.btn_net.pack(side="left", padx=2)
        self.btn_gpu = ttk.Button(self.top, text="GPU", bootstyle=SECONDARY, command=lambda: self.show_panel("gpu"))
        self.btn_gpu.pack(side="left", padx=2)
        self.btn_sys = ttk.Button(self.top, text="SISTEMA", bootstyle=DANGER, command=lambda: self.show_panel("sys"))
        self.btn_sys.pack(side="left", padx=2)

        # Sidebar (expandida) - construido pero no empaquetado hasta expandir
        self.sidebar = ttk.Frame(self.container, width=150, padding=(4, 4))
        # botones verticales (se reutilizan en compact/expanded via pack_forget/pack)
        self.sb_btn_cpu = ttk.Button(self.sidebar, text="CPU", bootstyle=PRIMARY, command=lambda: self.show_panel("cpu"))
        self.sb_btn_ram = ttk.Button(self.sidebar, text="Memoria", bootstyle=INFO, command=lambda: self.show_panel("ram"))
        self.sb_btn_disk = ttk.Button(self.sidebar, text="Disco", bootstyle=WARNING, command=lambda: self.show_panel("disk"))
        self.sb_btn_net = ttk.Button(self.sidebar, text="Red", bootstyle=SUCCESS, command=lambda: self.show_panel("net"))
        self.sb_btn_gpu = ttk.Button(self.sidebar, text="GPU", bootstyle=SECONDARY, command=lambda: self.show_panel("gpu"))
        self.sb_btn_sys = ttk.Button(self.sidebar, text="Sistema", bootstyle=DANGER, command=lambda: self.show_panel("sys"))

        for btn in (self.sb_btn_cpu, self.sb_btn_ram, self.sb_btn_disk, self.sb_btn_net, self.sb_btn_gpu, self.sb_btn_sys):
            btn.pack(fill="x", pady=6)

        # footer botones en sidebar
        sb_footer = ttk.Frame(self.sidebar)
        sb_footer.pack(side="bottom", fill="x", pady=(6, 0))
        self.sb_expand_btn = ttk.Button(sb_footer, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand(self.current_panel))
        self.sb_expand_btn.pack(side="left", padx=6)
        self.sb_pin_btn = ttk.Button(sb_footer, text="📌", bootstyle=SECONDARY, command=self.toggle_pin)
        self.sb_pin_btn.pack(side="right", padx=6)

        # panel principal (donde van las tarjetas)
        self.panel_container = ttk.Frame(self.container)
        self.panel_container.pack(fill="both", expand=True)

        # crear los panels (cada uno ya incluye botón de expandir)
        self.create_cpu_panel()
        self.create_ram_panel()
        self.create_disk_panel()
        self.create_net_panel()
        self.create_gpu_panel()
        self.create_sys_panel()

        # hint
        hint = ttk.Label(self.container, text="Pasa el mouse por la pestaña →", bootstyle=INFO)
        hint.pack(side="bottom", anchor="e")

        # fijar tamaño inicial compacto
        self.root.geometry(f"{self.compact_width}x{self.compact_height}+{self.screen_w - self.compact_width}+{self.y}")

    # ---------------- Mostrar panel ----------------
    def show_panel(self, name):
        # ocultar todos y mostrar el seleccionado
        for p in self.panels.values():
            p.pack_forget()
        self.panels[name].pack(fill="both", expand=True)
        self.current_panel = name
        # actualizar detalles (si estamos en modo expandido se mostrarán)
        self.show_detailed_info(name)

    # ---------------- Mostrar info detallada (se muestra solo en expandido) ----------------
    def show_detailed_info(self, name):
        # cada panel tiene labels de detalle creados en create_*_panel; aquí actualizamos textos
        if name == "cpu":
            cores = psutil.cpu_count(logical=False)
            threads = psutil.cpu_count(logical=True)
            freqs = psutil.cpu_freq()
            ftext = f"{freqs.current:.0f} MHz" if freqs else "N/D"
            txt = f"Cores: {cores}   Threads: {threads}\nFreq: {ftext}"
            self.cpu_details.config(text=txt)
            # mostrar u ocultar según modo
            if self.expanded:
                self.cpu_details.pack(anchor="w", pady=(6, 4))
            else:
                self.cpu_details.pack_forget()

        elif name == "ram":
            vm = psutil.virtual_memory()
            tot = vm.total / 1024**3
            used = vm.used / 1024**3
            avail = vm.available / 1024**3
            txt = f"Total: {tot:.2f} GB  Usada: {used:.2f} GB  Libre: {avail:.2f} GB"
            self.ram_details.config(text=txt)
            if self.expanded:
                self.ram_details.pack(anchor="w", pady=(6, 4))
            else:
                self.ram_details.pack_forget()

        elif name == "disk":
            try:
                du = psutil.disk_usage("C:\\")
            except Exception:
                du = psutil.disk_usage("/")
            tot = du.total / 1024**3
            used = du.used / 1024**3
            free = du.free / 1024**3
            txt = f"Total: {tot:.2f} GB  Usado: {used:.2f} GB  Libre: {free:.2f} GB"
            self.disk_details.config(text=txt)
            if self.expanded:
                self.disk_details.pack(anchor="w", pady=(6, 4))
            else:
                self.disk_details.pack_forget()

        elif name == "net":
            net = psutil.net_io_counters()
            sent = net.bytes_sent / 1024**2
            recv = net.bytes_recv / 1024**2
            txt = f"Total enviado: {sent:.2f} MB   Total recibido: {recv:.2f} MB"
            self.net_details.config(text=txt)
            if self.expanded:
                self.net_details.pack(anchor="w", pady=(6, 4))
            else:
                self.net_details.pack_forget()

        elif name == "gpu":
            if GPUtil_available:
                gpus = GPUtil.getGPUs()
                if gpus:
                    g = gpus[0]
                    txt = f"{g.name}  Carga: {g.load*100:.0f}%  Mem: {g.memoryUsed}/{g.memoryTotal} MB"
                else:
                    txt = "No se detectó GPU"
            else:
                txt = "GPUtil no instalado"
            self.gpu_details.config(text=txt)
            if self.expanded:
                self.gpu_details.pack(anchor="w", pady=(6, 4))
            else:
                self.gpu_details.pack_forget()

        elif name == "sys":
            txt = f"{platform.system()} {platform.release()}  Host: {platform.node()}"
            self.sys_details.config(text=txt)
            if self.expanded:
                self.sys_details.pack(anchor="w", pady=(6, 4))
            else:
                self.sys_details.pack_forget()

    # ---------------- Expand / Collapse (cambia layout) ----------------
    def toggle_expand(self, name):
        # alterna expanded flag y reorganiza layout en la misma ventana
        self.expanded = not self.expanded

        if self.expanded:
            # Poner tamaño expandido
            self.root.geometry(f"{self.expanded_width}x{self.expanded_height}+{self.screen_w - self.expanded_width}+{self.y}")

            # ocultar top (horizontal) y mostrar sidebar (vertical)
            self.top.pack_forget()
            # colocar sidebar a la izquierda y panel_container a la derecha
            self.sidebar.pack(side="left", fill="y", padx=(0, 8), pady=8)
            self.panel_container.pack_forget()
            self.panel_container.pack(side="left", fill="both", expand=True)

            # actualizar botones del sidebar para coincidir con top
            # (ya están creados y con comando, se usan tal cual)
            # mostrar información detallada del panel actual
            self.show_panel(name)

        else:
            # volver al compacto
            self.root.geometry(f"{self.compact_width}x{self.compact_height}+{self.screen_w - self.compact_width}+{self.y}")

            # ocultar sidebar y volver a poner top
            self.sidebar.pack_forget()
            self.top.pack(fill="x", pady=(0, 6))

            # agrandar/encoger panel container a full width del container
            self.panel_container.pack_forget()
            self.panel_container.pack(fill="both", expand=True)

            # ocultar labels detalladas (show_detailed_info las ocultará)
            self.show_panel(name)

    # ---------------- CREACIÓN DE PANELES ----------------
    def create_cpu_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="CPU", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")

        # resumen compacto
        self.cpu_usage = ttk.Label(f, text="-- %", font=("Consolas", 11))
        self.cpu_usage.pack(anchor="w", pady=(4, 0))
        self.cpu_freq = ttk.Label(f, text="Freq: -- MHz", font=("Consolas", 10))
        self.cpu_freq.pack(anchor="w")
        self.cpu_cores = ttk.Label(f, text="Cores: -- (L: --)", font=("Consolas", 10))
        self.cpu_cores.pack(anchor="w")

        # mini-gráfica
        self.cpu_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.cpu_ax = self.cpu_fig.add_subplot(111)
        self.cpu_ax.set_xticks([])
        self.cpu_ax.set_yticks([])
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_fig, master=f)
        self.cpu_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.cpu_data = []

        # detalle (no empaquetado por defecto; se mostrará sólo en expanded)
        self.cpu_details = ttk.Label(f, text="", font=("Consolas", 10))
        # botones
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("cpu")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["cpu"] = f

    def create_ram_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="Memoria", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")
        self.ram_usage = ttk.Label(f, text="-- %", font=("Consolas", 11))
        self.ram_usage.pack(anchor="w", pady=(4, 0))
        self.ram_detail = ttk.Label(f, text="Usada: -- / -- GB", font=("Consolas", 10))
        self.ram_detail.pack(anchor="w")

        self.ram_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.ram_ax = self.ram_fig.add_subplot(111)
        self.ram_ax.set_xticks([])
        self.ram_ax.set_yticks([])
        self.ram_canvas = FigureCanvasTkAgg(self.ram_fig, master=f)
        self.ram_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.ram_data = []

        self.ram_details = ttk.Label(f, text="", font=("Consolas", 10))
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("ram")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["ram"] = f

    def create_disk_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="Disco (C:)", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")
        self.disk_usage = ttk.Label(f, text="-- %", font=("Consolas", 11))
        self.disk_usage.pack(anchor="w", pady=(4, 0))
        self.disk_rw = ttk.Label(f, text="R/W: -- / -- MB/s", font=("Consolas", 10))
        self.disk_rw.pack(anchor="w")
        self.disk_free = ttk.Label(f, text="Libre: -- GB", font=("Consolas", 10))
        self.disk_free.pack(anchor="w")

        self.disk_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.disk_ax = self.disk_fig.add_subplot(111)
        self.disk_ax.set_xticks([])
        self.disk_ax.set_yticks([])
        self.disk_canvas = FigureCanvasTkAgg(self.disk_fig, master=f)
        self.disk_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.disk_data = []
        self.disk_max_points = 60

        self.disk_details = ttk.Label(f, text="", font=("Consolas", 10))
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("disk")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["disk"] = f

    def create_net_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="Red (total)", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")
        self.net_speed = ttk.Label(f, text="↑ -- MB/s  ↓ -- MB/s", font=("Consolas", 11))
        self.net_speed.pack(anchor="w", pady=(4, 0))
        self.net_total = ttk.Label(f, text="Total: -- / -- MB", font=("Consolas", 10))
        self.net_total.pack(anchor="w")

        self.net_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.net_ax = self.net_fig.add_subplot(111)
        self.net_ax.set_xticks([])
        self.net_ax.set_yticks([])
        self.net_canvas = FigureCanvasTkAgg(self.net_fig, master=f)
        self.net_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.net_data = []

        self.net_details = ttk.Label(f, text="", font=("Consolas", 10))
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("net")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["net"] = f

    def create_gpu_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="GPU", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")
        self.gpu_info = ttk.Label(f, text="Detectando...", font=("Consolas", 11))
        self.gpu_info.pack(anchor="w", pady=(4, 0))

        self.gpu_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.gpu_ax = self.gpu_fig.add_subplot(111)
        self.gpu_ax.set_xticks([])
        self.gpu_ax.set_yticks([])
        self.gpu_canvas = FigureCanvasTkAgg(self.gpu_fig, master=f)
        self.gpu_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.gpu_data = []

        self.gpu_details = ttk.Label(f, text="", font=("Consolas", 10))
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("gpu")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["gpu"] = f

    def create_sys_panel(self):
        f = ttk.Frame(self.panel_container, padding=8)
        title = ttk.Label(f, text="Sistema", font=("Consolas", 12, "bold"))
        title.pack(anchor="w")
        self.sys_os = ttk.Label(f, text="OS: --", font=("Consolas", 11))
        self.sys_os.pack(anchor="w", pady=(4, 0))
        self.sys_host = ttk.Label(f, text="Host: --", font=("Consolas", 10))
        self.sys_host.pack(anchor="w")
        self.sys_uptime = ttk.Label(f, text="Uptime: --", font=("Consolas", 10))
        self.sys_uptime.pack(anchor="w")

        self.sys_fig = Figure(figsize=(4, 0.9), dpi=75)
        self.sys_ax = self.sys_fig.add_subplot(111)
        self.sys_ax.set_xticks([])
        self.sys_ax.set_yticks([])
        self.sys_canvas = FigureCanvasTkAgg(self.sys_fig, master=f)
        self.sys_canvas.get_tk_widget().pack(anchor="w", pady=(6, 0), fill="x")
        self.sys_data = []
        self.sys_hours = 24

        self.sys_details = ttk.Label(f, text="", font=("Consolas", 10))
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(6, 2))
        ttk.Button(btn_row, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("sys")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="left")
        self.panels["sys"] = f

        

    # ---------------- Toggle pin ----------------
    def toggle_pin(self):
        self.pinned = not self.pinned
        style = SUCCESS if self.pinned else SECONDARY
        # actualizar cualquier botón indicador
        try:
            self.sb_pin_btn.configure(bootstyle=style)
        except Exception:
            pass

    # ---------------- Stats update ----------------
    def update_stats(self):
        now = time.time()
        dt = max(0.001, now - self.prev_time)

        # CPU
        cpu = psutil.cpu_percent(interval=None)
        freq = psutil.cpu_freq()
        freq_text = f"{freq.current:.0f} MHz" if freq and freq.current else "N/D"
        self.cpu_usage.config(text=f"{cpu:.0f} %")
        self.cpu_freq.config(text=f"Freq: {freq_text}")
        self.cpu_cores.config(text=f"Cores: {psutil.cpu_count(logical=False)} (L: {psutil.cpu_count(logical=True)})")

        # gráfica CPU
        self.cpu_data.append(cpu)
        if len(self.cpu_data) > 120:
            self.cpu_data.pop(0)
        self.cpu_ax.clear()
        self.cpu_ax.plot(self.cpu_data)
        self.cpu_ax.set_xticks([])
        self.cpu_ax.set_yticks([])
        self.cpu_canvas.draw()

        # RAM
        vm = psutil.virtual_memory()
        used_gb = vm.used / (1024**3)
        total_gb = vm.total / (1024**3)
        self.ram_usage.config(text=f"{vm.percent:.0f} %")
        self.ram_detail.config(text=f"Usada: {used_gb:.2f} / {total_gb:.2f} GB")

        self.ram_data.append(vm.percent)
        if len(self.ram_data) > 120:
            self.ram_data.pop(0)
        self.ram_ax.clear()
        self.ram_ax.plot(self.ram_data)
        self.ram_ax.set_xticks([])
        self.ram_ax.set_yticks([])
        self.ram_canvas.draw()

        # DISCO
        try:
            du = psutil.disk_usage("C:\\")
        except Exception:
            du = psutil.disk_usage("/")
        self.disk_usage.config(text=f"{du.percent:.0f} %")
        self.disk_free.config(text=f"Libre: {du.free / (1024**3):.2f} GB")

        dio = psutil.disk_io_counters()
        read_mb_s = (dio.read_bytes - self.prev_disk.read_bytes) / (1024*1024) / dt
        write_mb_s = (dio.write_bytes - self.prev_disk.write_bytes) / (1024*1024) / dt
        self.disk_rw.config(text=f"R/W: {read_mb_s:.2f} / {write_mb_s:.2f} MB/s")
        self.prev_disk = dio

        disk_activity = read_mb_s + write_mb_s
        self.disk_data.append(disk_activity)
        if len(self.disk_data) > self.disk_max_points:
            self.disk_data.pop(0)
        self.disk_ax.clear()
        self.disk_ax.plot(self.disk_data)
        self.disk_ax.set_xticks([])
        self.disk_ax.set_yticks([])
        self.disk_canvas.draw()

        # RED
        net = psutil.net_io_counters()
        up_mb_s = (net.bytes_sent - self.prev_net.bytes_sent) / (1024*1024) / dt
        down_mb_s = (net.bytes_recv - self.prev_net.bytes_recv) / (1024*1024) / dt
        self.net_speed.config(text=f"↑ {up_mb_s:.2f} MB/s   ↓ {down_mb_s:.2f} MB/s")
        self.net_total.config(text=f"Total: {net.bytes_sent/1024/1024:.1f} / {net.bytes_recv/1024/1024:.1f} MB")
        self.prev_net = net

        total_net = up_mb_s + down_mb_s
        self.net_data.append(total_net)
        if len(self.net_data) > 120:
            self.net_data.pop(0)
        self.net_ax.clear()
        self.net_ax.plot(self.net_data)
        self.net_ax.set_xticks([])
        self.net_ax.set_yticks([])
        self.net_canvas.draw()

        # GPU
        gpu_load = 0
        if GPUtil_available:
            gpus = GPUtil.getGPUs()
            if gpus:
                lines = []
                for g in gpus:
                    lines.append(f"{g.name}  carga: {g.load*100:.0f}%  mem: {g.memoryUsed}/{g.memoryTotal} MB")
                self.gpu_info.config(text="\n".join(lines))
                gpu_load = gpus[0].load*100
            else:
                self.gpu_info.config(text="No se detectaron GPUs")
        else:
            self.gpu_info.config(text="GPUtil no instalado")

        self.gpu_data.append(gpu_load)
        if len(self.gpu_data) > 120:
            self.gpu_data.pop(0)
        self.gpu_ax.clear()
        self.gpu_ax.plot(self.gpu_data)
        self.gpu_ax.set_xticks([])
        self.gpu_ax.set_yticks([])
        self.gpu_canvas.draw()

        # SISTEMA
                # SISTEMA
        self.sys_os.config(text=f"OS: {platform.system()} {platform.release()}")
        self.sys_host.config(text=f"Host: {platform.node()}")
        boot = psutil.boot_time()
        uptime_s = int(time.time() - boot)
        days = uptime_s // 86400
        hours = (uptime_s % 86400) // 3600
        minutes = (uptime_s % 3600) // 60
        self.sys_uptime.config(text=f"Uptime: {days}d {hours}h {minutes}m")

        # actualizar gráfica de sistema (ejemplo: uptime histórico en horas)
        self.sys_data.append(uptime_s / 3600)  # en horas
        if len(self.sys_data) > self.sys_hours:
            self.sys_data.pop(0)
        self.sys_ax.clear()
        self.sys_ax.plot(self.sys_data)
        self.sys_ax.set_xticks([])
        self.sys_ax.set_yticks([])
        self.sys_canvas.draw()

        # Actualizar time reference
        self.prev_time = now

        # Llamar de nuevo al update cada 1s
        self.root.after(1000, self.update_stats)

    # ---------------- Animaciones (mantengo las tuyas) ----------------
    def on_enter(self, event):
        if self.leave_after:
            self.root.after_cancel(self.leave_after)
            self.leave_after = None
        self.slide_in()

    def on_leave(self, event):
        if self.pinned:
            return
        if self.leave_after:
            self.root.after_cancel(self.leave_after)
        self.leave_after = self.root.after(700, self._maybe_close)

    def _maybe_close(self):
        if self.root.winfo_pointerx() < self.open_x:
            self.slide_out()
        else:
            self.leave_after = None

    def slide_in(self):
        if self.animating or self.is_open:
            return
        self.animating = True
        self._animate_in_step()

    def _animate_in_step(self):
        if self.cur_x > self.open_x:
            self.cur_x = max(self.open_x, self.cur_x - self.step)
            self.root.geometry(f"{self.compact_width}x{self.compact_height}+{self.cur_x}+{self.y}")
            self.root.after(self.delay, self._animate_in_step)
        else:
            self.animating = False
            self.is_open = True

    def slide_out(self):
        if self.animating or not self.is_open:
            return
        self.animating = True
        self._animate_out_step()

    def _animate_out_step(self):
        if self.cur_x < self.closed_x:
            self.cur_x = min(self.closed_x, self.cur_x + self.step)
            self.root.geometry(f"{self.compact_width}x{self.compact_height}+{self.cur_x}+{self.y}")
            self.root.after(self.delay, self._animate_out_step)
        else:
            self.animating = False
            self.is_open = False


if __name__ == "__main__":
    app = EdgeWidget()
    app.root.mainloop()