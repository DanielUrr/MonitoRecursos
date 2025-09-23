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
        


        # Ventana con tema moderno (puedes cambiar "darkly" por "superhero", "cyborg", "flatly", etc.)
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


        #CREACION DE PANELES

    def build_ui(self):
        pad = 8
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="both", expand=True)

        # fila superior: botones
        top = ttk.Frame(container)
        top.pack(fill="x", pady=(0, 5))

        self.btn_cpu = ttk.Button(top, text="CPU", bootstyle=PRIMARY, command=lambda: self.show_panel("cpu"))
        self.btn_cpu.pack(side="left", padx=2)

        self.btn_ram = ttk.Button(top, text="RAM", bootstyle=INFO, command=lambda: self.show_panel("ram"))
        self.btn_ram.pack(side="left", padx=2)

        self.btn_disk = ttk.Button(top, text="DISCO", bootstyle=WARNING, command=lambda: self.show_panel("disk"))
        self.btn_disk.pack(side="left", padx=2)

        self.btn_net = ttk.Button(top, text="RED", bootstyle=SUCCESS, command=lambda: self.show_panel("net"))
        self.btn_net.pack(side="left", padx=2)

        self.btn_gpu = ttk.Button(top, text="GPU", bootstyle=SECONDARY, command=lambda: self.show_panel("gpu"))
        self.btn_gpu.pack(side="left", padx=2)

        self.btn_sys = ttk.Button(top, text="SISTEMA", bootstyle=DANGER, command=lambda: self.show_panel("sys"))
        self.btn_sys.pack(side="left", padx=2)


        

        # panel dinámico
        self.panel_container = ttk.Frame(container)
        self.panel_container.pack(fill="both", expand=True)

        self.panels = {}
        self.create_cpu_panel()
        self.create_ram_panel()
        self.create_disk_panel()
        self.create_net_panel()
        self.create_gpu_panel()
        self.create_sys_panel()

        self.show_panel("cpu")

        hint = ttk.Label(container, text="Pasa el mouse por la pestaña →", bootstyle=INFO)
        hint.pack(side="bottom", anchor="e")


    # ---------------- MÉTODO DE EXPANSIÓN ----------------
    def toggle_expand(self, name):
        self.expanded = not self.expanded

        if self.expanded:
            new_width = 700
            new_height = 500
            self.root.geometry(f"{new_width}x{new_height}+{self.screen_w - new_width}+{self.y}")

            # Barra vertical
            for btn in [self.btn_cpu, self.btn_ram, self.btn_disk, self.btn_net, self.btn_gpu, self.btn_sys]:
                btn.pack_forget()
                btn.pack(side="top", fill="x", padx=2, pady=2)

            self.show_panel(name)
        else:
            self.root.geometry(f"{self.width}x{self.height}+{self.open_x}+{self.y}")

            for btn in [self.btn_cpu, self.btn_ram, self.btn_disk, self.btn_net, self.btn_gpu, self.btn_sys]:
                btn.pack_forget()
                btn.pack(side="left", padx=2)

            self.show_panel(name)


    #MAS CREACION DE PANELES CON LOS DETALLES

    #PANEL DE LA CPU

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
        self.cpu_fig = Figure(figsize=(4,0.7), dpi=70)
        self.cpu_ax = self.cpu_fig.add_subplot(111)
        self.cpu_ax.set_xticks([])
        self.cpu_ax.set_yticks([])
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_fig, master=f)
        self.cpu_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.cpu_data = []  # Lista para almacenar datos

        
        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("cpu"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)


#PANEL DE LA RAM
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
        self.ram_fig = Figure(figsize=(4,0.7), dpi=70)
        self.ram_ax = self.ram_fig.add_subplot(111)
        self.ram_ax.set_xticks([])
        self.ram_ax.set_yticks([])
        self.ram_canvas = FigureCanvasTkAgg(self.ram_fig, master=f)
        self.ram_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.ram_data = []

        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("ram"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)


#PANEL DEL DISCO

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
        # Mini-gráfica de actividad del disco
        self.disk_fig = Figure(figsize=(4,0.7), dpi=70)
        self.disk_ax = self.disk_fig.add_subplot(111)
        self.disk_ax.set_xticks([])
        self.disk_ax.set_yticks([])
        self.disk_canvas = FigureCanvasTkAgg(self.disk_fig, master=f)
        self.disk_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.disk_data = []  # Lista para almacenar actividad
        self.disk_max_points = 60  # Últimos 60 valores (aprox 60 segundos si update_stats=1s)

        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("disk"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)


#PANEL DEL INTERNET

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
        self.net_fig = Figure(figsize=(4,0.7), dpi=70)
        self.net_ax = self.net_fig.add_subplot(111)
        self.net_ax.set_xticks([])
        self.net_ax.set_yticks([])
        self.net_canvas = FigureCanvasTkAgg(self.net_fig, master=f)
        self.net_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.net_data = []

        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("net"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

#PANEL DE LA GPU

    def create_gpu_panel(self):
        f = ttk.Frame(self.panel_container)
        lbl = ttk.Label(f, text="GPU", font=("Consolas", 12, "bold"))
        lbl.pack(anchor="w")
        self.gpu_info = ttk.Label(f, text="Detectando...")
        self.gpu_info.pack(anchor="w")
        self.panels["gpu"] = f

       # Mini-gráfica GPU en tiempo real
        self.gpu_fig = Figure(figsize=(4,0.7), dpi=70)
        self.gpu_ax = self.gpu_fig.add_subplot(111)
        self.gpu_ax.set_xticks([])
        self.gpu_ax.set_yticks([])
        self.gpu_canvas = FigureCanvasTkAgg(self.gpu_fig, master=f)
        self.gpu_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.gpu_data = []  # Lista para almacenar datos en tiempo real

        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("gpu"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)

#PANEL DEL SISTEMA

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

        # Mini-gráfica de uso diario del sistema (CPU promedio)
        self.sys_fig = Figure(figsize=(4,0.7), dpi=70)
        self.sys_ax = self.sys_fig.add_subplot(111)
        self.sys_ax.set_xticks([])
        self.sys_ax.set_yticks([])
        self.sys_canvas = FigureCanvasTkAgg(self.sys_fig, master=f)
        self.sys_canvas.get_tk_widget().pack(anchor="w", pady=(5,0))
        self.sys_data = []  # Lista para almacenar uso promedio diario
        self.sys_hours = 24  # Máximo 24 valores, uno por hora

        #BOTON PIN
        self.pin_btn = ttk.Button(f, text="📌", bootstyle=SECONDARY, command=self.toggle_pin) 
        self.pin_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=20)

        self.expand_btn = ttk.Button(f, text="⤢", bootstyle=INFO, command=lambda: self.toggle_expand("sys"))
        self.expand_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-50, y=20)


    def show_panel(self, name):
        for p in self.panels.values():
            p.pack_forget()
        self.panels[name].pack(fill="both", expand=True)

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.pin_btn.configure(bootstyle=SUCCESS if self.pinned else SECONDARY)

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

        # Actualizar mini-gráfica CPU
        self.cpu_data.append(cpu)
        if len(self.cpu_data) > 30:
            self.cpu_data.pop(0)
        self.cpu_ax.clear()
        self.cpu_ax.plot(self.cpu_data, color="lime")  # <- Aquí pones tu color deseado
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
        if len(self.ram_data) > 30:
            self.ram_data.pop(0)
        self.ram_ax.clear()
        self.ram_ax.plot(self.ram_data, color="cyan")  # Color azul para RAM
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

# I/O del disco
        dio = psutil.disk_io_counters()
        read_mb_s = (dio.read_bytes - self.prev_disk.read_bytes) / (1024*1024) / dt
        write_mb_s = (dio.write_bytes - self.prev_disk.write_bytes) / (1024*1024) / dt
        self.disk_rw.config(text=f"R/W: {read_mb_s:.2f} / {write_mb_s:.2f} MB/s")
        self.prev_disk = dio

# 🚀 Nueva gráfica: actividad de disco (lectura + escritura)
        disk_activity = read_mb_s + write_mb_s
        self.disk_data.append(disk_activity)
        if len(self.disk_data) > 30:
            self.disk_data.pop(0)

        self.disk_ax.clear()
        self.disk_ax.plot(self.disk_data, color="lime")  # Verde fosforescente
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
        if len(self.net_data) > 30:
            self.net_data.pop(0)
        self.net_ax.clear()
        self.net_ax.plot(self.net_data, color="lime")  # Verde para Red
        self.net_ax.set_xticks([])
        self.net_ax.set_yticks([])
        self.net_canvas.draw()


        # GPU
        if GPUtil_available:
            gpus = GPUtil.getGPUs()
            if gpus:
                lines = []
                for g in gpus:
                    lines.append(f"{g.name}\n carga: {g.load*100:.0f}%  mem: {g.memoryUsed}/{g.memoryTotal} MB")
                self.gpu_info.config(text="\n".join(lines))
            else:
                self.gpu_info.config(text="No se detectaron GPUs")
        else:
            self.gpu_info.config(text="GPUtil no instalado")

            gpu_load = 0
        if GPUtil_available:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_load = gpus[0].load*100

        # Actualizar lista de datos GPU
        self.gpu_data.append(gpu_load)
        if len(self.gpu_data) > 30:  # Mostrar últimos 30 valores
            self.gpu_data.pop(0)

# Dibujar mini-gráfica GPU
        self.gpu_ax.clear()
        self.gpu_ax.plot(self.gpu_data, color="magenta")  # Color morado para GPU
        self.gpu_ax.set_xticks([])
        self.gpu_ax.set_yticks([])
        self.gpu_canvas.draw()


        
        # Sistema
        self.sys_os.config(text=f"OS: {platform.system()} {platform.release()}")
        self.sys_host.config(text=f"Host: {platform.node()}")
        boot = psutil.boot_time()
        uptime_s = int(now - boot)
        self.sys_uptime.config(text=f"Uptime: {uptime_s//3600}h {(uptime_s%3600)//60}m")

        self.prev_time = now
        self.root.after(1000, self.update_stats)

        # Agregar valor promedio de CPU para el sistema
        # Aquí tomamos el CPU actual como ejemplo; podrías usar otro promedio si quieres
        if len(self.sys_data) == 0 or int(time.time()) % 3600 == 0:  # Agrega un punto por hora
            self.sys_data.append(cpu)  # cpu viene de psutil.cpu_percent()

        # Limitar la lista a 24 horas
        if len(self.sys_data) > self.sys_hours:
            self.sys_data.pop(0)

        # Dibujar mini-gráfica del sistema
        self.sys_ax.clear()
        self.sys_ax.plot(self.sys_data, color="cyan")  # Color azul para sistema
        self.sys_ax.set_xticks([])
        self.sys_ax.set_yticks([])
        self.sys_canvas.draw()


    # Animaciones
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
            self.root.geometry(f"{self.width}x{self.height}+{self.cur_x}+{self.y}")
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
            self.root.geometry(f"{self.width}x{self.height}+{self.cur_x}+{self.y}")
            self.root.after(self.delay, self._animate_out_step)
        else:
            self.animating = False
            self.is_open = False


if __name__ == "__main__":
    app = EdgeWidget()
    app.root.mainloop()