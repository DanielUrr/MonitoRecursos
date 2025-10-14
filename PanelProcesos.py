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
        self.width = width
        self.height = height
        self.y = y
        self.step = step
        self.delay = delay
        self.hide_gap = hide_gap
        
        # Ventana con tema moderno
        self.root = ttk.Window(themename="darkly")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.root.update_idletasks()
        self.screen_w = self.root.winfo_screenwidth()
        self.open_x = self.screen_w - self.width
        self.closed_x = self.screen_w - self.hide_gap
        self.cur_x = self.closed_x
        self.root.geometry(f"{self.width}x{self.height}+{self.cur_x}+{self.y}")

        self.is_open = False
        self.animating = False
        self.leave_after = None
        self.pinned = False
        self.expanded = False
        self.current_panel = "cpu"

        # prev counters para tasas
        self.prev_net = psutil.net_io_counters()
        self.prev_disk = psutil.disk_io_counters()
        self.prev_time = time.time()
        psutil.cpu_percent(None)

        self.build_ui()

        # eventos
        self.root.bind("<Enter>", self.on_enter)
        self.root.bind("<Leave>", self.on_leave)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.update_stats()

    def build_ui(self):
        self.container = ttk.Frame(self.root, padding=10)
        self.container.pack(fill="both", expand=True)

        self.create_compact_ui()
        self.create_panels()

    def create_compact_ui(self):
        # Interfaz compacta (original)
        self.compact_frame = ttk.Frame(self.container)
        self.compact_frame.pack(fill="both", expand=True)

        # fila superior: botones
        self.top_frame = ttk.Frame(self.compact_frame)
        self.top_frame.pack(fill="x", pady=(0, 5))

        self.btn_cpu = ttk.Button(self.top_frame, text="CPU", bootstyle=PRIMARY, command=lambda: self.show_panel("cpu"))
        self.btn_cpu.pack(side="left", padx=2)

        self.btn_ram = ttk.Button(self.top_frame, text="RAM", bootstyle=INFO, command=lambda: self.show_panel("ram"))
        self.btn_ram.pack(side="left", padx=2)

        self.btn_disk = ttk.Button(self.top_frame, text="DISCO", bootstyle=WARNING, command=lambda: self.show_panel("disk"))
        self.btn_disk.pack(side="left", padx=2)

        self.btn_net = ttk.Button(self.top_frame, text="RED", bootstyle=SUCCESS, command=lambda: self.show_panel("net"))
        self.btn_net.pack(side="left", padx=2)

        self.btn_gpu = ttk.Button(self.top_frame, text="GPU", bootstyle=SECONDARY, command=lambda: self.show_panel("gpu"))
        self.btn_gpu.pack(side="left", padx=2)

        self.btn_sys = ttk.Button(self.top_frame, text="SISTEMA", bootstyle=DANGER, command=lambda: self.show_panel("sys"))
        self.btn_sys.pack(side="left", padx=2)

        # panel dinámico compacto
        self.panel_container = ttk.Frame(self.compact_frame)
        self.panel_container.pack(fill="both", expand=True)

        hint = ttk.Label(self.compact_frame, text="Pasa el mouse por la pestaña →", bootstyle=INFO)
        hint.pack(side="bottom", anchor="e")

    def create_expanded_ui(self):
        # Interfaz expandida
        self.expanded_frame = ttk.Frame(self.container)
        
        # Frame principal dividido en izquierda y derecha
        main_expanded = ttk.Frame(self.expanded_frame)
        main_expanded.pack(fill="both", expand=True, padx=5, pady=5)

        # Panel izquierdo - botones verticales y estadísticas rápidas
        left_panel = ttk.Frame(main_expanded, width=200)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        # Botones verticales
        ttk.Label(left_panel, text="MONITOREO DEL SISTEMA", font=("Consolas", 10, "bold")).pack(pady=(0,10))
        
        self.expanded_buttons = {}
        button_configs = [
            ("cpu", "CPU", PRIMARY), ("ram", "MEMORIA", INFO), ("disk", "DISCO", WARNING),
            ("net", "RED", SUCCESS), ("gpu", "GPU", SECONDARY), ("sys", "SISTEMA", DANGER)
        ]
        
        for key, text, style in button_configs:
            btn = ttk.Button(left_panel, text=text, bootstyle=style, 
                           command=lambda k=key: self.show_expanded_panel(k))
            btn.pack(fill="x", pady=2)
            self.expanded_buttons[key] = btn

        # Estadísticas rápidas en el panel izquierdo
        stats_frame = ttk.LabelFrame(left_panel, text="Resumen", padding=10)
        stats_frame.pack(fill="x", pady=(20, 0))
        
        self.quick_stats = {
            'cpu': ttk.Label(stats_frame, text="CPU: -- %", font=("Consolas", 9)),
            'ram': ttk.Label(stats_frame, text="RAM: -- %", font=("Consolas", 9)),
            'disk': ttk.Label(stats_frame, text="Disco: -- %", font=("Consolas", 9)),
            'net': ttk.Label(stats_frame, text="Red: -- MB/s", font=("Consolas", 9))
        }
        
        for label in self.quick_stats.values():
            label.pack(anchor="w", pady=1)

        # Panel derecho - gráfica grande y detalles
        self.right_panel = ttk.Frame(main_expanded)
        self.right_panel.pack(side="right", fill="both", expand=True)

        # Crear paneles expandidos
        self.expanded_panels = {}
        self.create_expanded_panels()

    def create_expanded_panels(self):
        # Panel CPU expandido
        self.create_expanded_cpu_panel()
        self.create_expanded_ram_panel()
        self.create_expanded_disk_panel()
        self.create_expanded_net_panel()
        self.create_expanded_gpu_panel()
        self.create_expanded_sys_panel()

    def create_expanded_cpu_panel(self):
        f = ttk.Frame(self.right_panel)
        
        # Título y controles
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="PROCESADOR (CPU)", font=("Consolas", 14, "bold")).pack(side="left")
        
        # Botones de control
        controls = ttk.Frame(header)
        controls.pack(side="right")
        
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("cpu")).pack(side="right", padx=2)

        # Información detallada
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="x", pady=(0, 10))
        
        # Columna izquierda
        left_info = ttk.Frame(info_frame)
        left_info.pack(side="left", fill="both", expand=True)
        
        self.cpu_detailed = {
            'usage': ttk.Label(left_info, text="Uso: -- %", font=("Consolas", 12, "bold")),
            'freq': ttk.Label(left_info, text="Frecuencia: -- MHz", font=("Consolas", 10)),
            'cores': ttk.Label(left_info, text="Núcleos: -- físicos (-- lógicos)", font=("Consolas", 10)),
            'temp': ttk.Label(left_info, text="Temperatura: N/A", font=("Consolas", 10))
        }
        
        for label in self.cpu_detailed.values():
            label.pack(anchor="w", pady=2)

        # Columna derecha
        right_info = ttk.Frame(info_frame)
        right_info.pack(side="right", fill="both", expand=True)
        
        self.cpu_detailed_right = {
            'processes': ttk.Label(right_info, text="Procesos: --", font=("Consolas", 10)),
            'threads': ttk.Label(right_info, text="Hilos: --", font=("Consolas", 10)),
            'uptime': ttk.Label(right_info, text="Tiempo activo: --", font=("Consolas", 10))
        }
        
        for label in self.cpu_detailed_right.values():
            label.pack(anchor="w", pady=2)

        # Gráfica grande
        self.cpu_big_fig = Figure(figsize=(8, 4), dpi=100, facecolor='#2b2b2b')
        self.cpu_big_fig.patch.set_facecolor('#2b2b2b')
        self.cpu_big_ax = self.cpu_big_fig.add_subplot(111, facecolor='#2b2b2b')
        self.cpu_big_ax.set_title("Uso del CPU en Tiempo Real", color='white', fontsize=12)
        self.cpu_big_ax.set_ylabel("Uso (%)", color='white')
        self.cpu_big_ax.set_ylim(0, 100)
        self.cpu_big_ax.grid(True, alpha=0.3, color='white')
        self.cpu_big_ax.tick_params(colors='white')
        
        self.cpu_big_canvas = FigureCanvasTkAgg(self.cpu_big_fig, master=f)
        self.cpu_big_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        # Datos extendidos para gráfica grande
        self.cpu_big_data = []
        
        self.expanded_panels["cpu"] = f

    def create_expanded_ram_panel(self):
        f = ttk.Frame(self.right_panel)
        
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="MEMORIA (RAM)", font=("Consolas", 14, "bold")).pack(side="left")
        
        controls = ttk.Frame(header)
        controls.pack(side="right")
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("ram")).pack(side="right", padx=2)

        # Información detallada
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="x", pady=(0, 10))
        
        left_info = ttk.Frame(info_frame)
        left_info.pack(side="left", fill="both", expand=True)
        
        self.ram_detailed = {
            'usage': ttk.Label(left_info, text="Uso: -- %", font=("Consolas", 12, "bold")),
            'used': ttk.Label(left_info, text="Usada: -- GB", font=("Consolas", 10)),
            'available': ttk.Label(left_info, text="Disponible: -- GB", font=("Consolas", 10)),
            'total': ttk.Label(left_info, text="Total: -- GB", font=("Consolas", 10))
        }
        
        for label in self.ram_detailed.values():
            label.pack(anchor="w", pady=2)

        right_info = ttk.Frame(info_frame)
        right_info.pack(side="right", fill="both", expand=True)
        
        self.ram_detailed_right = {
            'cached': ttk.Label(right_info, text="En caché: -- GB", font=("Consolas", 10)),
            'buffers': ttk.Label(right_info, text="Buffers: -- GB", font=("Consolas", 10)),
            'swap': ttk.Label(right_info, text="Swap: -- GB", font=("Consolas", 10))
        }
        
        for label in self.ram_detailed_right.values():
            label.pack(anchor="w", pady=2)

        # Gráfica grande RAM
        self.ram_big_fig = Figure(figsize=(8, 4), dpi=100, facecolor='#2b2b2b')
        self.ram_big_fig.patch.set_facecolor('#2b2b2b')
        self.ram_big_ax = self.ram_big_fig.add_subplot(111, facecolor='#2b2b2b')
        self.ram_big_ax.set_title("Uso de Memoria en Tiempo Real", color='white', fontsize=12)
        self.ram_big_ax.set_ylabel("Uso (%)", color='white')
        self.ram_big_ax.set_ylim(0, 100)
        self.ram_big_ax.grid(True, alpha=0.3, color='white')
        self.ram_big_ax.tick_params(colors='white')
        
        self.ram_big_canvas = FigureCanvasTkAgg(self.ram_big_fig, master=f)
        self.ram_big_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        self.ram_big_data = []
        self.expanded_panels["ram"] = f

    def create_expanded_disk_panel(self):
        f = ttk.Frame(self.right_panel)
        
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="ALMACENAMIENTO (DISCO)", font=("Consolas", 14, "bold")).pack(side="left")
        
        controls = ttk.Frame(header)
        controls.pack(side="right")
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("disk")).pack(side="right", padx=2)

        # Info detallada del disco
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="x", pady=(0, 10))
        
        left_info = ttk.Frame(info_frame)
        left_info.pack(side="left", fill="both", expand=True)
        
        self.disk_detailed = {
            'usage': ttk.Label(left_info, text="Uso: -- %", font=("Consolas", 12, "bold")),
            'free': ttk.Label(left_info, text="Libre: -- GB", font=("Consolas", 10)),
            'used': ttk.Label(left_info, text="Usado: -- GB", font=("Consolas", 10)),
            'total': ttk.Label(left_info, text="Total: -- GB", font=("Consolas", 10))
        }
        
        for label in self.disk_detailed.values():
            label.pack(anchor="w", pady=2)

        right_info = ttk.Frame(info_frame)
        right_info.pack(side="right", fill="both", expand=True)
        
        self.disk_detailed_right = {
            'read_speed': ttk.Label(right_info, text="Lectura: -- MB/s", font=("Consolas", 10)),
            'write_speed': ttk.Label(right_info, text="Escritura: -- MB/s", font=("Consolas", 10)),
            'total_io': ttk.Label(right_info, text="I/O Total: -- MB/s", font=("Consolas", 10))
        }
        
        for label in self.disk_detailed_right.values():
            label.pack(anchor="w", pady=2)

        # Gráfica grande del disco
        self.disk_big_fig = Figure(figsize=(8, 4), dpi=100, facecolor='#2b2b2b')
        self.disk_big_fig.patch.set_facecolor('#2b2b2b')
        self.disk_big_ax = self.disk_big_fig.add_subplot(111, facecolor='#2b2b2b')
        self.disk_big_ax.set_title("Actividad del Disco en Tiempo Real", color='white', fontsize=12)
        self.disk_big_ax.set_ylabel("MB/s", color='white')
        self.disk_big_ax.grid(True, alpha=0.3, color='white')
        self.disk_big_ax.tick_params(colors='white')
        
        self.disk_big_canvas = FigureCanvasTkAgg(self.disk_big_fig, master=f)
        self.disk_big_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        self.disk_big_read_data = []
        self.disk_big_write_data = []
        self.expanded_panels["disk"] = f

    def create_expanded_net_panel(self):
        f = ttk.Frame(self.right_panel)
        
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="RED / INTERNET", font=("Consolas", 14, "bold")).pack(side="left")
        
        controls = ttk.Frame(header)
        controls.pack(side="right")
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("net")).pack(side="right", padx=2)

        # Info de red
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="x", pady=(0, 10))
        
        left_info = ttk.Frame(info_frame)
        left_info.pack(side="left", fill="both", expand=True)
        
        self.net_detailed = {
            'upload': ttk.Label(left_info, text="↑ Subida: -- MB/s", font=("Consolas", 12, "bold")),
            'download': ttk.Label(left_info, text="↓ Bajada: -- MB/s", font=("Consolas", 12, "bold")),
            'total_sent': ttk.Label(left_info, text="Total enviado: -- MB", font=("Consolas", 10)),
            'total_recv': ttk.Label(left_info, text="Total recibido: -- MB", font=("Consolas", 10))
        }
        
        for label in self.net_detailed.values():
            label.pack(anchor="w", pady=2)

        # Gráfica grande de red
        self.net_big_fig = Figure(figsize=(8, 4), dpi=100, facecolor='#2b2b2b')
        self.net_big_fig.patch.set_facecolor('#2b2b2b')
        self.net_big_ax = self.net_big_fig.add_subplot(111, facecolor='#2b2b2b')
        self.net_big_ax.set_title("Actividad de Red en Tiempo Real", color='white', fontsize=12)
        self.net_big_ax.set_ylabel("MB/s", color='white')
        self.net_big_ax.grid(True, alpha=0.3, color='white')
        self.net_big_ax.tick_params(colors='white')
        
        self.net_big_canvas = FigureCanvasTkAgg(self.net_big_fig, master=f)
        self.net_big_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        self.net_big_upload_data = []
        self.net_big_download_data = []
        self.expanded_panels["net"] = f

    def create_expanded_gpu_panel(self):
        f = ttk.Frame(self.right_panel)
        
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="TARJETA GRÁFICA (GPU)", font=("Consolas", 14, "bold")).pack(side="left")
        
        controls = ttk.Frame(header)
        controls.pack(side="right")
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("gpu")).pack(side="right", padx=2)

        # Info GPU
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="x", pady=(0, 10))
        
        self.gpu_detailed = {
            'name': ttk.Label(info_frame, text="GPU: Detectando...", font=("Consolas", 12, "bold")),
            'load': ttk.Label(info_frame, text="Carga: -- %", font=("Consolas", 10)),
            'memory': ttk.Label(info_frame, text="Memoria: -- / -- MB", font=("Consolas", 10)),
            'temp': ttk.Label(info_frame, text="Temperatura: -- °C", font=("Consolas", 10))
        }
        
        for label in self.gpu_detailed.values():
            label.pack(anchor="w", pady=2)

        # Gráfica GPU
        self.gpu_big_fig = Figure(figsize=(8, 4), dpi=100, facecolor='#2b2b2b')
        self.gpu_big_fig.patch.set_facecolor('#2b2b2b')
        self.gpu_big_ax = self.gpu_big_fig.add_subplot(111, facecolor='#2b2b2b')
        self.gpu_big_ax.set_title("Uso de GPU en Tiempo Real", color='white', fontsize=12)
        self.gpu_big_ax.set_ylabel("Uso (%)", color='white')
        self.gpu_big_ax.set_ylim(0, 100)
        self.gpu_big_ax.grid(True, alpha=0.3, color='white')
        self.gpu_big_ax.tick_params(colors='white')
        
        self.gpu_big_canvas = FigureCanvasTkAgg(self.gpu_big_fig, master=f)
        self.gpu_big_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        self.gpu_big_data = []
        self.expanded_panels["gpu"] = f

    def create_expanded_sys_panel(self):
        f = ttk.Frame(self.right_panel)
        
        header = ttk.Frame(f)
        header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header, text="INFORMACIÓN DEL SISTEMA", font=("Consolas", 14, "bold")).pack(side="left")
        
        controls = ttk.Frame(header)
        controls.pack(side="right")
        ttk.Button(controls, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).pack(side="right", padx=2)
        ttk.Button(controls, text="⤡", bootstyle=INFO, command=lambda: self.toggle_expand("sys")).pack(side="right", padx=2)

        # Info del sistema
        info_frame = ttk.Frame(f)
        info_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.sys_detailed = {
            'os': ttk.Label(info_frame, text="Sistema Operativo: --", font=("Consolas", 11)),
            'hostname': ttk.Label(info_frame, text="Nombre del equipo: --", font=("Consolas", 11)),
            'uptime': ttk.Label(info_frame, text="Tiempo activo: --", font=("Consolas", 11)),
            'boot_time': ttk.Label(info_frame, text="Último inicio: --", font=("Consolas", 11)),
            'user': ttk.Label(info_frame, text="Usuario: --", font=("Consolas", 11)),
            'processes': ttk.Label(info_frame, text="Procesos activos: --", font=("Consolas", 11))
        }
        
        for label in self.sys_detailed.values():
            label.pack(anchor="w", pady=3)

        self.expanded_panels["sys"] = f

    # Crear paneles compactos (originales)
    def create_panels(self):
        self.panels = {}
        self.create_cpu_panel()
        self.create_ram_panel()
        self.create_disk_panel()
        self.create_net_panel()
        self.create_gpu_panel()
        self.create_sys_panel()
        self.show_panel("cpu")

    def create_cpu_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="Uso CPU:", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.cpu_usage = ttk.Label(f, text="-- %")
        self.cpu_usage.pack(anchor="w")
        self.cpu_freq = ttk.Label(f, text="Freq: -- MHz")
        self.cpu_freq.pack(anchor="w")
        self.cpu_cores = ttk.Label(f, text="Cores: -- (L: --)")
        self.cpu_cores.pack(anchor="w")
        self.panels["cpu"] = f

        # Mini gráfica CPU
        self.cpu_fig = Figure(figsize=(4,0.7), dpi=70, facecolor='#2b2b2b')
        self.cpu_fig.patch.set_facecolor('#2b2b2b')
        self.cpu_ax = self.cpu_fig.add_subplot(111, facecolor='#2b2b2b')
        self.cpu_ax.set_xticks([])
        self.cpu_ax.set_yticks([])
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_fig, master=f)
        self.cpu_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.cpu_data = []

        # Botones
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin)
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("cpu"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def create_ram_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="Memoria RAM", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.ram_usage = ttk.Label(f, text="-- %")
        self.ram_usage.pack(anchor="w")
        self.ram_detail = ttk.Label(f, text="Usada: -- / -- GB")
        self.ram_detail.pack(anchor="w")
        self.panels["ram"] = f

        # Mini-gráfica RAM
        self.ram_fig = Figure(figsize=(4,0.7), dpi=70, facecolor='#2b2b2b')
        self.ram_fig.patch.set_facecolor('#2b2b2b')
        self.ram_ax = self.ram_fig.add_subplot(111, facecolor='#2b2b2b')
        self.ram_ax.set_xticks([])
        self.ram_ax.set_yticks([])
        self.ram_canvas = FigureCanvasTkAgg(self.ram_fig, master=f)
        self.ram_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.ram_data = []

        # Botones
        ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)
        ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("ram")).place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def create_disk_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="Disco (C:)", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.disk_usage = ttk.Label(f, text="-- %")
        self.disk_usage.pack(anchor="w")
        self.disk_rw = ttk.Label(f, text="R/W: -- / -- MB/s")
        self.disk_rw.pack(anchor="w")
        self.disk_free = ttk.Label(f, text="Libre: -- GB")
        self.disk_free.pack(anchor="w")
        self.panels["disk"] = f

        # Mini-gráfica Disco
        self.disk_fig = Figure(figsize=(4,0.7), dpi=70, facecolor='#2b2b2b')
        self.disk_fig.patch.set_facecolor('#2b2b2b')
        self.disk_ax = self.disk_fig.add_subplot(111, facecolor='#2b2b2b')
        self.disk_ax.set_xticks([])
        self.disk_ax.set_yticks([])
        self.disk_canvas = FigureCanvasTkAgg(self.disk_fig, master=f)
        self.disk_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.disk_data = []

        # Botones
        ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)
        ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("disk")).place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def create_net_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="Red (total)", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.net_speed = ttk.Label(f, text="↑ -- MB/s  ↓ -- MB/s")
        self.net_speed.pack(anchor="w")
        self.net_total = ttk.Label(f, text="Total: -- / -- MB")
        self.net_total.pack(anchor="w")
        self.panels["net"] = f

        # Mini-gráfica Red
        self.net_fig = Figure(figsize=(4,0.7), dpi=70, facecolor='#2b2b2b')
        self.net_fig.patch.set_facecolor('#2b2b2b')
        self.net_ax = self.net_fig.add_subplot(111, facecolor='#2b2b2b')
        self.net_ax.set_xticks([])
        self.net_ax.set_yticks([])
        self.net_canvas = FigureCanvasTkAgg(self.net_fig, master=f)
        self.net_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.net_data = []

        # Botones
        ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)
        ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("net")).place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def create_gpu_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="GPU", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.gpu_info = ttk.Label(f, text="Detectando...")
        self.gpu_info.pack(anchor="w")
        self.panels["gpu"] = f

        # Mini-gráfica GPU
        self.gpu_fig = Figure(figsize=(4,0.7), dpi=70, facecolor='#2b2b2b')
        self.gpu_fig.patch.set_facecolor('#2b2b2b')
        self.gpu_ax = self.gpu_fig.add_subplot(111, facecolor='#2b2b2b')
        self.gpu_ax.set_xticks([])
        self.gpu_ax.set_yticks([])
        self.gpu_canvas = FigureCanvasTkAgg(self.gpu_fig, master=f)
        self.gpu_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.gpu_data = []

        # Botones
        ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)
        ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("gpu")).place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def create_sys_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="Sistema", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.sys_os = ttk.Label(f, text="OS: --")
        self.sys_os.pack(anchor="w")
        self.sys_host = ttk.Label(f, text="Host: --")
        self.sys_host.pack(anchor="w")
        self.sys_uptime = ttk.Label(f, text="Uptime: --")
        self.sys_uptime.pack(anchor="w")
        self.panels["sys"] = f

        # Botones
        ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)
        ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("sys")).place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

    def show_panel(self, name):
        self.current_panel = name
        if not self.expanded:
            for p in self.panels.values():
                p.pack_forget()
            self.panels[name].pack(fill="both", expand=True)

    def show_expanded_panel(self, name):
        self.current_panel = name
        if self.expanded:
            for p in self.expanded_panels.values():
                p.pack_forget()
            self.expanded_panels[name].pack(fill="both", expand=True)
            
            # Resaltar botón activo
            for btn in self.expanded_buttons.values():
                btn.configure(bootstyle=OUTLINE)
            self.expanded_buttons[name].configure(bootstyle=PRIMARY)

    def toggle_expand(self, name):
        self.expanded = not self.expanded
        self.current_panel = name

        if self.expanded:
            new_width = 900
            new_height = 600
            self.open_x = self.screen_w - new_width
            
            # Primero crear la interfaz expandida si no existe
            if not hasattr(self, 'expanded_frame'):
                self.create_expanded_ui()
            
            # Cambiar geometría y mostrar interfaz expandida
            self.root.geometry(f"{new_width}x{new_height}+{self.open_x}+{self.y}")
            self.compact_frame.pack_forget()
            self.expanded_frame.pack(fill="both", expand=True)
            self.show_expanded_panel(name)
            
        else:
            # Volver a modo compacto
            self.root.geometry(f"{self.width}x{self.height}+{self.screen_w - self.width}+{self.y}")
            self.open_x = self.screen_w - self.width
            
            if hasattr(self, 'expanded_frame'):
                self.expanded_frame.pack_forget()
            self.compact_frame.pack(fill="both", expand=True)
            self.show_panel(name)

    def toggle_pin(self):
        self.pinned = not self.pinned
        if hasattr(self, 'pin_btn'):
            self.pin_btn.configure(bootstyle=SUCCESS if self.pinned else SECONDARY)

    def update_stats(self):
        now = time.time()
        dt = max(0.001, now - self.prev_time)

        # CPU
        cpu = psutil.cpu_percent(interval=None)
        freq = psutil.cpu_freq()
        freq_text = f"{freq.current:.0f} MHz" if freq and freq.current else "N/D"
        
        # Actualizar interfaz compacta
        if hasattr(self, 'cpu_usage'):
            self.cpu_usage.config(text=f"{cpu:.0f} %")
            self.cpu_freq.config(text=f"Freq: {freq_text}")
            self.cpu_cores.config(text=f"Cores: {psutil.cpu_count(logical=False)} (L: {psutil.cpu_count(logical=True)})")

        # Actualizar mini-gráfica CPU
        self.cpu_data.append(cpu)
        if len(self.cpu_data) > 30:
            self.cpu_data.pop(0)
        
        if hasattr(self, 'cpu_ax'):
            self.cpu_ax.clear()
            self.cpu_ax.set_facecolor('#2b2b2b')
            self.cpu_ax.plot(self.cpu_data, color="lime", linewidth=2)
            self.cpu_ax.set_xticks([])
            self.cpu_ax.set_yticks([])
            self.cpu_canvas.draw()

        # Actualizar gráfica expandida CPU
        if self.expanded and hasattr(self, 'cpu_big_ax'):
            self.cpu_big_data.append(cpu)
            if len(self.cpu_big_data) > 100:
                self.cpu_big_data.pop(0)
            
            self.cpu_big_ax.clear()
            self.cpu_big_ax.set_facecolor('#2b2b2b')
            self.cpu_big_ax.plot(self.cpu_big_data, color="lime", linewidth=2)
            self.cpu_big_ax.set_title("Uso del CPU en Tiempo Real", color='white', fontsize=12)
            self.cpu_big_ax.set_ylabel("Uso (%)", color='white')
            self.cpu_big_ax.set_ylim(0, 100)
            self.cpu_big_ax.grid(True, alpha=0.3, color='white')
            self.cpu_big_ax.tick_params(colors='white')
            self.cpu_big_canvas.draw()
            
            # Actualizar información detallada
            if hasattr(self, 'cpu_detailed'):
                self.cpu_detailed['usage'].config(text=f"Uso: {cpu:.1f} %")
                self.cpu_detailed['freq'].config(text=f"Frecuencia: {freq_text}")
                self.cpu_detailed['cores'].config(text=f"Núcleos: {psutil.cpu_count(logical=False)} físicos ({psutil.cpu_count(logical=True)} lógicos)")
                
                try:
                    processes = len(psutil.pids())
                    self.cpu_detailed_right['processes'].config(text=f"Procesos: {processes}")
                    
                    boot_time = psutil.boot_time()
                    uptime_seconds = int(now - boot_time)
                    uptime_text = f"{uptime_seconds//3600}h {(uptime_seconds%3600)//60}m"
                    self.cpu_detailed_right['uptime'].config(text=f"Tiempo activo: {uptime_text}")
                except:
                    pass

        # RAM
        vm = psutil.virtual_memory()
        used_gb = vm.used / (1024**3)
        total_gb = vm.total / (1024**3)
        
        if hasattr(self, 'ram_usage'):
            self.ram_usage.config(text=f"{vm.percent:.0f} %")
            self.ram_detail.config(text=f"Usada: {used_gb:.2f} / {total_gb:.2f} GB")

        self.ram_data.append(vm.percent)
        if len(self.ram_data) > 30:
            self.ram_data.pop(0)
        
        if hasattr(self, 'ram_ax'):
            self.ram_ax.clear()
            self.ram_ax.set_facecolor('#2b2b2b')
            self.ram_ax.plot(self.ram_data, color="cyan", linewidth=2)
            self.ram_ax.set_xticks([])
            self.ram_ax.set_yticks([])
            self.ram_canvas.draw()

        # Actualizar RAM expandida
        if self.expanded and hasattr(self, 'ram_big_ax'):
            self.ram_big_data.append(vm.percent)
            if len(self.ram_big_data) > 100:
                self.ram_big_data.pop(0)
            
            self.ram_big_ax.clear()
            self.ram_big_ax.set_facecolor('#2b2b2b')
            self.ram_big_ax.plot(self.ram_big_data, color="cyan", linewidth=2)
            self.ram_big_ax.set_title("Uso de Memoria en Tiempo Real", color='white', fontsize=12)
            self.ram_big_ax.set_ylabel("Uso (%)", color='white')
            self.ram_big_ax.set_ylim(0, 100)
            self.ram_big_ax.grid(True, alpha=0.3, color='white')
            self.ram_big_ax.tick_params(colors='white')
            self.ram_big_canvas.draw()
            
            if hasattr(self, 'ram_detailed'):
                available_gb = vm.available / (1024**3)
                self.ram_detailed['usage'].config(text=f"Uso: {vm.percent:.1f} %")
                self.ram_detailed['used'].config(text=f"Usada: {used_gb:.2f} GB")
                self.ram_detailed['available'].config(text=f"Disponible: {available_gb:.2f} GB")
                self.ram_detailed['total'].config(text=f"Total: {total_gb:.2f} GB")

        # DISCO
        try:
            du = psutil.disk_usage("C:\\")
        except Exception:
            du = psutil.disk_usage("/")
        
        if hasattr(self, 'disk_usage'):
            self.disk_usage.config(text=f"{du.percent:.0f} %")
            self.disk_free.config(text=f"Libre: {du.free / (1024**3):.2f} GB")

        # I/O del disco
        dio = psutil.disk_io_counters()
        read_mb_s = (dio.read_bytes - self.prev_disk.read_bytes) / (1024*1024) / dt
        write_mb_s = (dio.write_bytes - self.prev_disk.write_bytes) / (1024*1024) / dt
        
        if hasattr(self, 'disk_rw'):
            self.disk_rw.config(text=f"R/W: {read_mb_s:.2f} / {write_mb_s:.2f} MB/s")
        
        self.prev_disk = dio

        disk_activity = read_mb_s + write_mb_s
        self.disk_data.append(disk_activity)
        if len(self.disk_data) > 30:
            self.disk_data.pop(0)

        if hasattr(self, 'disk_ax'):
            self.disk_ax.clear()
            self.disk_ax.set_facecolor('#2b2b2b')
            self.disk_ax.plot(self.disk_data, color="orange", linewidth=2)
            self.disk_ax.set_xticks([])
            self.disk_ax.set_yticks([])
            self.disk_canvas.draw()

        # Actualizar disco expandido
        if self.expanded and hasattr(self, 'disk_big_ax'):
            self.disk_big_read_data.append(read_mb_s)
            self.disk_big_write_data.append(write_mb_s)
            if len(self.disk_big_read_data) > 100:
                self.disk_big_read_data.pop(0)
                self.disk_big_write_data.pop(0)
            
            self.disk_big_ax.clear()
            self.disk_big_ax.set_facecolor('#2b2b2b')
            self.disk_big_ax.plot(self.disk_big_read_data, color="green", linewidth=2, label="Lectura")
            self.disk_big_ax.plot(self.disk_big_write_data, color="red", linewidth=2, label="Escritura")
            self.disk_big_ax.set_title("Actividad del Disco en Tiempo Real", color='white', fontsize=12)
            self.disk_big_ax.set_ylabel("MB/s", color='white')
            self.disk_big_ax.legend()
            self.disk_big_ax.grid(True, alpha=0.3, color='white')
            self.disk_big_ax.tick_params(colors='white')
            self.disk_big_canvas.draw()
            
            if hasattr(self, 'disk_detailed'):
                used_gb = du.used / (1024**3)
                free_gb = du.free / (1024**3)
                total_gb = du.total / (1024**3)
                
                self.disk_detailed['usage'].config(text=f"Uso: {du.percent:.1f} %")
                self.disk_detailed['free'].config(text=f"Libre: {free_gb:.2f} GB")
                self.disk_detailed['used'].config(text=f"Usado: {used_gb:.2f} GB")
                self.disk_detailed['total'].config(text=f"Total: {total_gb:.2f} GB")
                
                self.disk_detailed_right['read_speed'].config(text=f"Lectura: {read_mb_s:.2f} MB/s")
                self.disk_detailed_right['write_speed'].config(text=f"Escritura: {write_mb_s:.2f} MB/s")
                self.disk_detailed_right['total_io'].config(text=f"I/O Total: {read_mb_s + write_mb_s:.2f} MB/s")

        # RED
        net = psutil.net_io_counters()
        up_mb_s = (net.bytes_sent - self.prev_net.bytes_sent) / (1024*1024) / dt
        down_mb_s = (net.bytes_recv - self.prev_net.bytes_recv) / (1024*1024) / dt
        
        if hasattr(self, 'net_speed'):
            self.net_speed.config(text=f"↑ {up_mb_s:.2f} MB/s   ↓ {down_mb_s:.2f} MB/s")
            self.net_total.config(text=f"Total: {net.bytes_sent/1024/1024:.1f} / {net.bytes_recv/1024/1024:.1f} MB")
        
        self.prev_net = net

        total_net = up_mb_s + down_mb_s
        self.net_data.append(total_net)
        if len(self.net_data) > 30:
            self.net_data.pop(0)
        
        if hasattr(self, 'net_ax'):
            self.net_ax.clear()
            self.net_ax.set_facecolor('#2b2b2b')
            self.net_ax.plot(self.net_data, color="yellow", linewidth=2)
            self.net_ax.set_xticks([])
            self.net_ax.set_yticks([])
            self.net_canvas.draw()

        # Actualizar red expandida
        if self.expanded and hasattr(self, 'net_big_ax'):
            self.net_big_upload_data.append(up_mb_s)
            self.net_big_download_data.append(down_mb_s)
            if len(self.net_big_upload_data) > 100:
                self.net_big_upload_data.pop(0)
                self.net_big_download_data.pop(0)
            
            self.net_big_ax.clear()
            self.net_big_ax.set_facecolor('#2b2b2b')
            self.net_big_ax.plot(self.net_big_upload_data, color="red", linewidth=2, label="↑ Subida")
            self.net_big_ax.plot(self.net_big_download_data, color="green", linewidth=2, label="↓ Bajada")
            self.net_big_ax.set_title("Actividad de Red en Tiempo Real", color='white', fontsize=12)
            self.net_big_ax.set_ylabel("MB/s", color='white')
            self.net_big_ax.legend()
            self.net_big_ax.grid(True, alpha=0.3, color='white')
            self.net_big_ax.tick_params(colors='white')
            self.net_big_canvas.draw()
            
            if hasattr(self, 'net_detailed'):
                self.net_detailed['upload'].config(text=f"↑ Subida: {up_mb_s:.2f} MB/s")
                self.net_detailed['download'].config(text=f"↓ Bajada: {down_mb_s:.2f} MB/s")
                self.net_detailed['total_sent'].config(text=f"Total enviado: {net.bytes_sent/1024/1024:.1f} MB")
                self.net_detailed['total_recv'].config(text=f"Total recibido: {net.bytes_recv/1024/1024:.1f} MB")

        # GPU
        gpu_load = 0
        if GPUtil_available:
            gpus = GPUtil.getGPUs()
            if gpus:
                lines = []
                for g in gpus:
                    lines.append(f"{g.name}\n carga: {g.load*100:.0f}%  mem: {g.memoryUsed}/{g.memoryTotal} MB")
                if hasattr(self, 'gpu_info'):
                    self.gpu_info.config(text="\n".join(lines))
                gpu_load = gpus[0].load*100
                
                # Actualizar GPU expandida
                if self.expanded and hasattr(self, 'gpu_detailed'):
                    gpu = gpus[0]
                    self.gpu_detailed['name'].config(text=f"GPU: {gpu.name}")
                    self.gpu_detailed['load'].config(text=f"Carga: {gpu.load*100:.1f} %")
                    self.gpu_detailed['memory'].config(text=f"Memoria: {gpu.memoryUsed} / {gpu.memoryTotal} MB")
                    if hasattr(gpu, 'temperature'):
                        self.gpu_detailed['temp'].config(text=f"Temperatura: {gpu.temperature} °C")
            else:
                if hasattr(self, 'gpu_info'):
                    self.gpu_info.config(text="No se detectaron GPUs")
        else:
            if hasattr(self, 'gpu_info'):
                self.gpu_info.config(text="GPUtil no instalado")

        self.gpu_data.append(gpu_load)
        if len(self.gpu_data) > 30:
            self.gpu_data.pop(0)

        if hasattr(self, 'gpu_ax'):
            self.gpu_ax.clear()
            self.gpu_ax.set_facecolor('#2b2b2b')
            self.gpu_ax.plot(self.gpu_data, color="magenta", linewidth=2)
            self.gpu_ax.set_xticks([])
            self.gpu_ax.set_yticks([])
            self.gpu_canvas.draw()

        # Actualizar GPU expandida
        if self.expanded and hasattr(self, 'gpu_big_ax'):
            self.gpu_big_data.append(gpu_load)
            if len(self.gpu_big_data) > 100:
                self.gpu_big_data.pop(0)
            
            self.gpu_big_ax.clear()
            self.gpu_big_ax.set_facecolor('#2b2b2b')
            self.gpu_big_ax.plot(self.gpu_big_data, color="magenta", linewidth=2)
            self.gpu_big_ax.set_title("Uso de GPU en Tiempo Real", color='white', fontsize=12)
            self.gpu_big_ax.set_ylabel("Uso (%)", color='white')
            self.gpu_big_ax.set_ylim(0, 100)
            self.gpu_big_ax.grid(True, alpha=0.3, color='white')
            self.gpu_big_ax.tick_params(colors='white')
            self.gpu_big_canvas.draw()

        # SISTEMA
        if hasattr(self, 'sys_os'):
            self.sys_os.config(text=f"OS: {platform.system()} {platform.release()}")
            self.sys_host.config(text=f"Host: {platform.node()}")
            boot = psutil.boot_time()
            uptime_s = int(now - boot)
            self.sys_uptime.config(text=f"Uptime: {uptime_s//3600}h {(uptime_s%3600)//60}m")

        # Actualizar sistema expandido
        if self.expanded and hasattr(self, 'sys_detailed'):
            try:
                import getpass
                user = getpass.getuser()
            except:
                user = "N/A"
            
            boot_time = psutil.boot_time()
            boot_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(boot_time))
            uptime_seconds = int(now - boot_time)
            uptime_text = f"{uptime_seconds//86400}d {(uptime_seconds%86400)//3600}h {(uptime_seconds%3600)//60}m"
            
            self.sys_detailed['os'].config(text=f"Sistema Operativo: {platform.system()} {platform.release()}")
            self.sys_detailed['hostname'].config(text=f"Nombre del equipo: {platform.node()}")
            self.sys_detailed['uptime'].config(text=f"Tiempo activo: {uptime_text}")
            self.sys_detailed['boot_time'].config(text=f"Último inicio: {boot_time_str}")
            self.sys_detailed['user'].config(text=f"Usuario: {user}")
            try:
                processes = len(psutil.pids())
                self.sys_detailed['processes'].config(text=f"Procesos activos: {processes}")
            except:
                pass

        # Actualizar estadísticas rápidas (solo en modo expandido)
        if self.expanded and hasattr(self, 'quick_stats'):
            self.quick_stats['cpu'].config(text=f"CPU: {cpu:.0f} %")
            self.quick_stats['ram'].config(text=f"RAM: {vm.percent:.0f} %")
            self.quick_stats['disk'].config(text=f"Disco: {du.percent:.0f} %")
            self.quick_stats['net'].config(text=f"Red: {total_net:.1f} MB/s")

        self.prev_time = now
        self.root.after(1000, self.update_stats)

    # Animaciones (mantener las originales)
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
            current_width = 900 if self.expanded else self.width
            current_height = 600 if self.expanded else self.height
            self.root.geometry(f"{current_width}x{current_height}+{self.cur_x}+{self.y}")
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
            current_width = 900 if self.expanded else self.width
            current_height = 600 if self.expanded else self.height
            self.root.geometry(f"{current_width}x{current_height}+{self.cur_x}+{self.y}")
            self.root.after(self.delay, self._animate_out_step)
        else:
            self.animating = False
            self.is_open = False


if __name__ == "__main__":
    app = EdgeWidget()
    app.root.mainloop()