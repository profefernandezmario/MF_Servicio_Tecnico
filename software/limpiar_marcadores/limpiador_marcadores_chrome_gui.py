import json
import os
import shutil
import threading
import time
import queue
from datetime import datetime
from urllib.parse import urlparse

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import requests
except ImportError:
    requests = None


APP_TITLE = "Limpiador de Marcadores de Chrome"
TIMEOUT = 12
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0 Safari/537.36"
)

DEAD_CODES = {404, 410}
REVIEW_CODES = {401, 403, 405, 407, 408, 429, 451, 500, 502, 503, 504}


def chrome_profiles():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    found = []
    if os.path.isdir(base):
        for name in os.listdir(base):
            path = os.path.join(base, name)
            bookmarks = os.path.join(path, "Bookmarks")
            if os.path.isdir(path) and os.path.isfile(bookmarks):
                found.append((name, bookmarks))
    return sorted(found)


def read_bookmarks(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_urls(node, folder="", out=None):
    if out is None:
        out = []
    typ = node.get("type")
    if typ == "url":
        out.append({
            "name": node.get("name", "(sin nombre)"),
            "url": node.get("url", ""),
            "folder": folder,
            "node": node,
            "status": "Pendiente",
            "detail": ""
        })
    elif typ == "folder":
        name = node.get("name", "")
        new_folder = f"{folder} / {name}" if folder else name
        for child in node.get("children", []):
            collect_urls(child, new_folder, out)
    return out


def all_bookmarks(data):
    result = []
    for root_key, root in data.get("roots", {}).items():
        if isinstance(root, dict):
            root_name = root.get("name", root_key)
            for child in root.get("children", []):
                collect_urls(child, root_name, result)
    return result


def check_url(url):
    if not url:
        return "REVISAR", "URL vacía"
    if not url.lower().startswith(("http://", "https://")):
        return "IGNORADO", "No es HTTP/HTTPS"

    headers = {"User-Agent": USER_AGENT}

    try:
        try:
            r = requests.head(url, timeout=TIMEOUT, allow_redirects=True, headers=headers)
            if r.status_code == 405:
                raise RuntimeError("HEAD no permitido")
        except Exception:
            r = requests.get(
                url, timeout=TIMEOUT, allow_redirects=True,
                headers=headers, stream=True
            )

        code = r.status_code
        if code in DEAD_CODES:
            return "MUERTO", f"HTTP {code}"
        if code in REVIEW_CODES:
            return "REVISAR", f"HTTP {code}"
        if 200 <= code < 400:
            return "OK", f"HTTP {code}"
        if code >= 400:
            return "REVISAR", f"HTTP {code}"
        return "OK", f"HTTP {code}"

    except requests.exceptions.SSLError:
        return "REVISAR", "Error SSL/certificado"
    except requests.exceptions.ConnectionError:
        return "MUERTO", "No se pudo conectar"
    except requests.exceptions.Timeout:
        return "REVISAR", "Tiempo de espera agotado"
    except requests.exceptions.RequestException as e:
        return "REVISAR", type(e).__name__
    except Exception as e:
        return "REVISAR", str(e)[:100]


def make_backup(path):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(os.path.dirname(path), f"Bookmarks_BACKUP_{stamp}")
    shutil.copy2(path, backup)
    return backup


def remove_urls(node, urls):
    if not isinstance(node, dict):
        return
    if node.get("type") == "folder":
        children = node.get("children", [])
        kept = []
        for child in children:
            if child.get("type") == "url" and child.get("url") in urls:
                continue
            remove_urls(child, urls)
            kept.append(child)
        node["children"] = kept


def save_bookmarks(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x720")
        self.minsize(900, 600)

        self.profiles = chrome_profiles()
        self.profile_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="Todos")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Listo.")
        self.count_var = tk.StringVar(value="0 marcadores")
        self.results = []
        self.data = None
        self.bookmarks_path = None
        self.backup_path = None
        self.running = False
        self.stop_requested = False
        self.msg_queue = queue.Queue()

        self.build_style()
        self.build_ui()
        self.populate_profiles()
        self.after(100, self.process_queue)

        if requests is None:
            messagebox.showerror(
                "Falta una dependencia",
                "No está instalado el módulo 'requests'.\n\n"
                "Abre CMD y ejecuta:\n\npip install requests"
            )

    def build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def build_ui(self):
        top = ttk.Frame(self, padding=(18, 15, 18, 8))
        top.pack(fill="x")

        ttk.Label(top, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            top,
            text="Analiza tus favoritos, identifica enlaces caídos y elimina solo los que selecciones.",
            style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(3, 12))

        controls = ttk.Frame(top)
        controls.pack(fill="x")

        ttk.Label(controls, text="Perfil de Chrome:").pack(side="left")
        self.profile_combo = ttk.Combobox(
            controls, textvariable=self.profile_var, state="readonly", width=28
        )
        self.profile_combo.pack(side="left", padx=(8, 18))

        ttk.Button(
            controls, text="Cargar marcadores", command=self.load_bookmarks
        ).pack(side="left")

        ttk.Label(controls, text="  Buscar:").pack(side="left", padx=(20, 4))
        search = ttk.Entry(controls, textvariable=self.search_var, width=30)
        search.pack(side="left")
        search.bind("<KeyRelease>", lambda e: self.refresh_tree())

        ttk.Label(controls, text="  Mostrar:").pack(side="left", padx=(15, 4))
        self.filter_combo = ttk.Combobox(
            controls, textvariable=self.filter_var,
            values=["Todos", "Pendiente", "OK", "MUERTO", "REVISAR", "IGNORADO"],
            state="readonly", width=12
        )
        self.filter_combo.pack(side="left")
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_tree())

        main = ttk.Frame(self, padding=(18, 5, 18, 8))
        main.pack(fill="both", expand=True)

        columns = ("select", "name", "url", "folder", "status", "detail")
        self.tree = ttk.Treeview(main, columns=columns, show="headings", selectmode="extended")

        headings = {
            "select": "✓",
            "name": "Marcador",
            "url": "URL",
            "folder": "Carpeta",
            "status": "Estado",
            "detail": "Detalle"
        }
        widths = {
            "select": 42, "name": 210, "url": 390,
            "folder": 190, "status": 100, "detail": 180
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=35)

        vsb = ttk.Scrollbar(main, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(main, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.toggle_selected_row)

        actions = ttk.Frame(self, padding=(18, 5, 18, 8))
        actions.pack(fill="x")

        self.select_dead_btn = ttk.Button(
            actions, text="Seleccionar muertos", command=self.select_dead
        )
        self.select_dead_btn.pack(side="left", padx=(0, 7))

        ttk.Button(
            actions, text="Deseleccionar todo", command=self.clear_selection
        ).pack(side="left", padx=7)

        self.analyze_btn = ttk.Button(
            actions, text="▶ Analizar enlaces", style="Accent.TButton",
            command=self.start_analysis
        )
        self.analyze_btn.pack(side="left", padx=7)

        self.delete_btn = ttk.Button(
            actions, text="🗑 Eliminar seleccionados", command=self.delete_selected
        )
        self.delete_btn.pack(side="left", padx=7)

        ttk.Button(
            actions, text="Guardar informe", command=self.save_report
        ).pack(side="right", padx=(7, 0))

        ttk.Button(
            actions, text="Salir", command=self.destroy
        ).pack(side="right")

        bottom = ttk.Frame(self, padding=(18, 5, 18, 15))
        bottom.pack(fill="x")

        ttk.Label(bottom, textvariable=self.count_var).pack(side="left")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")

        self.progress = ttk.Progressbar(
            bottom, variable=self.progress_var, maximum=100, mode="determinate"
        )
        self.progress.pack(fill="x", side="bottom", pady=(7, 0))

    def populate_profiles(self):
        if not self.profiles:
            self.profile_combo["values"] = []
            self.status_var.set("No se encontró ningún perfil de Chrome.")
            return
        names = [p[0] for p in self.profiles]
        self.profile_combo["values"] = names
        self.profile_combo.current(0)

    def load_bookmarks(self):
        if requests is None:
            return

        if not self.profiles:
            messagebox.showerror(
                "Chrome no encontrado",
                "No se encontró el archivo Bookmarks de Google Chrome."
            )
            return

        if self.running:
            return

        index = self.profile_combo.current()
        if index < 0:
            return

        name, path = self.profiles[index]

        try:
            self.data = read_bookmarks(path)
            self.results = all_bookmarks(self.data)
            self.bookmarks_path = path
            self.backup_path = None
            self.refresh_tree()
            self.status_var.set(f"Perfil cargado: {name}")
            self.count_var.set(f"{len(self.results)} marcadores")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron leer los marcadores:\n\n{e}")

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        q = self.search_var.get().strip().lower()
        filt = self.filter_var.get()

        shown = 0
        for idx, r in enumerate(self.results):
            text = f"{r['name']} {r['url']} {r['folder']}".lower()
            if q and q not in text:
                continue
            if filt != "Todos" and r["status"] != filt:
                continue

            self.tree.insert(
                "", "end", iid=str(idx),
                values=("☐", r["name"], r["url"], r["folder"], r["status"], r["detail"])
            )
            shown += 1

        self.count_var.set(f"{len(self.results)} marcadores · {shown} visibles")

    def toggle_selected_row(self, event=None):
        item = self.tree.focus()
        if not item:
            return
        vals = list(self.tree.item(item, "values"))
        vals[0] = "☑" if vals[0] != "☑" else "☐"
        self.tree.item(item, values=vals)

    def selected_indices(self):
        indices = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals and vals[0] == "☑":
                indices.append(int(iid))
        return indices

    def select_dead(self):
        for iid in self.tree.get_children():
            idx = int(iid)
            if self.results[idx]["status"] == "MUERTO":
                vals = list(self.tree.item(iid, "values"))
                vals[0] = "☑"
                self.tree.item(iid, values=vals)

    def clear_selection(self):
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            vals[0] = "☐"
            self.tree.item(iid, values=vals)

    def start_analysis(self):
        if self.running:
            return
        if not self.results:
            messagebox.showinfo("Sin marcadores", "Primero carga los marcadores de Chrome.")
            return
        if not self.bookmarks_path:
            return
        self.running = True
        self.stop_requested = False
        self.analyze_btn.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.select_dead_btn.config(state="disabled")
        self.progress_var.set(0)
        self.status_var.set("Analizando...")
        threading.Thread(target=self.analysis_worker, daemon=True).start()

    def analysis_worker(self):
        total = len(self.results)
        for i, r in enumerate(self.results, 1):
            if self.stop_requested:
                break
            status, detail = check_url(r["url"])
            r["status"] = status
            r["detail"] = detail
            self.msg_queue.put(("row", i - 1))
            self.msg_queue.put(("progress", i, total))

        self.msg_queue.put(("done",))

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg[0] == "row":
                    self.refresh_tree()
                elif msg[0] == "progress":
                    done, total = msg[1], msg[2]
                    self.progress_var.set(done / total * 100)
                    self.status_var.set(f"Analizando {done} de {total}...")
                elif msg[0] == "done":
                    self.running = False
                    self.analyze_btn.config(state="normal")
                    self.delete_btn.config(state="normal")
                    self.select_dead_btn.config(state="normal")
                    dead = sum(r["status"] == "MUERTO" for r in self.results)
                    review = sum(r["status"] == "REVISAR" for r in self.results)
                    self.status_var.set(f"Análisis terminado · {dead} muertos · {review} para revisar")
                    self.refresh_tree()
                    messagebox.showinfo(
                        "Análisis terminado",
                        f"Análisis completado.\n\n"
                        f"Marcadores: {len(self.results)}\n"
                        f"Activos: {sum(r['status'] == 'OK' for r in self.results)}\n"
                        f"Muertos: {dead}\n"
                        f"Revisar: {review}\n\n"
                        f"Los enlaces no se eliminaron automáticamente."
                    )
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def delete_selected(self):
        if self.running:
            return

        indices = self.selected_indices()
        if not indices:
            messagebox.showinfo("Nada seleccionado", "Selecciona los marcadores que quieras eliminar.")
            return

        selected = [self.results[i] for i in indices]

        dead = [r for r in selected if r["status"] == "MUERTO"]
        other = [r for r in selected if r["status"] != "MUERTO"]

        msg = f"Has seleccionado {len(selected)} marcador(es).\n\n"
        msg += f"Muertos: {len(dead)}\n"
        msg += f"Otros estados: {len(other)}\n\n"
        msg += "Se recomienda eliminar solamente los que aparecen como MUERTO.\n\n"
        msg += "¿Crear una copia de seguridad y continuar?"

        if not messagebox.askyesno("Confirmar eliminación", msg):
            return

        if not self.bookmarks_path or not self.data:
            messagebox.showerror("Error", "No hay un archivo de marcadores cargado.")
            return

        try:
            if not self.backup_path:
                self.backup_path = make_backup(self.bookmarks_path)

            urls = {r["url"] for r in selected}
            for root in self.data.get("roots", {}).values():
                remove_urls(root, urls)

            save_bookmarks(self.bookmarks_path, self.data)

            self.results = [r for r in self.results if r["url"] not in urls]
            self.refresh_tree()
            self.count_var.set(f"{len(self.results)} marcadores")
            self.status_var.set(f"Eliminados: {len(selected)} · Copia: {os.path.basename(self.backup_path)}")

            messagebox.showinfo(
                "Listo",
                f"Se eliminaron {len(selected)} marcador(es).\n\n"
                f"Copia de seguridad:\n{self.backup_path}\n\n"
                "Puedes restaurarla manualmente si necesitas recuperar los marcadores."
            )

        except Exception as e:
            messagebox.showerror("Error al eliminar", str(e))

    def save_report(self):
        if not self.results:
            messagebox.showinfo("Sin datos", "Primero carga y analiza los marcadores.")
            return

        path = filedialog.asksaveasfilename(
            title="Guardar informe",
            defaultextension=".txt",
            filetypes=[("Archivo de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("INFORME DE MARCADORES DE CHROME\n")
                f.write("=" * 90 + "\n")
                f.write(f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
                for i, r in enumerate(self.results, 1):
                    f.write(f"{i}. {r['name']}\n")
                    f.write(f"   URL: {r['url']}\n")
                    f.write(f"   Carpeta: {r['folder']}\n")
                    f.write(f"   Estado: {r['status']}\n")
                    f.write(f"   Detalle: {r['detail']}\n\n")
            messagebox.showinfo("Informe guardado", f"Informe guardado en:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    app = App()
    app.mainloop()
