"""Native Tkinter control panel for Website & App Blocker."""

import contextlib
import ctypes
import io
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.parse

import blocker


APP_TITLE = "Website & App Blocker"
WINDOW_SIZE = "940x650"


def relaunch_as_admin():
    """Restart this UI with administrator privileges."""
    script = os.path.abspath(__file__)
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}"', None, 1
    )
    return result > 32


class BlockerUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(820, 560)
        self.events = queue.Queue()
        self.busy = False
        self.status_var = tk.StringVar(value="Loading status ...")
        self.detail_var = tk.StringVar(value="")

        self._configure_style()
        self._build_layout()
        self.reload_config()
        self.refresh_status()
        self.root.after(100, self._poll_events)

    def _configure_style(self):
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Action.TButton", padding=(10, 7))

    def _build_layout(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        status_box = ttk.Frame(header)
        status_box.pack(side="right")
        ttk.Label(status_box, textvariable=self.status_var, style="Status.TLabel").pack(anchor="e")
        ttk.Label(status_box, textvariable=self.detail_var).pack(anchor="e")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 14))
        self.block_button = ttk.Button(
            actions, text="Enable Blocking", style="Primary.TButton", command=self.apply_blocking
        )
        self.block_button.pack(side="left", padx=(0, 8))
        self.unblock_button = ttk.Button(
            actions, text="Remove Blocking", style="Action.TButton", command=self.remove_blocking
        )
        self.unblock_button.pack(side="left", padx=(0, 8))
        self.update_button = ttk.Button(
            actions, text="Update Lists", style="Action.TButton", command=self.update_sources
        )
        self.update_button.pack(side="left", padx=(0, 8))
        ttk.Button(
            actions, text="Refresh Status", style="Action.TButton", command=self.refresh_status
        ).pack(side="left")

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        self.site_list = self._build_simple_list_tab(
            "Websites", "Domain", self.add_site, "example.com"
        )
        self.url_list = self._build_simple_list_tab(
            "URL Paths", "URL Pattern", self.add_url, "youtube.com/shorts/*"
        )
        self.app_list = self._build_simple_list_tab(
            "Apps", "Process Name", self.add_app, "example.exe"
        )
        self._build_sources_tab()
        self._build_log_tab()

    def _build_simple_list_tab(self, title, field_label, add_command, placeholder):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text=title)

        listbox = tk.Listbox(tab, selectmode=tk.EXTENDED, font=("Segoe UI", 10))
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        controls = ttk.Frame(tab, padding=(14, 0, 0, 0))
        controls.pack(side="right", fill="y")
        ttk.Label(controls, text=field_label).pack(anchor="w")
        entry = ttk.Entry(controls, width=34)
        entry.pack(fill="x", pady=(4, 8))
        entry.insert(0, placeholder)
        entry.bind("<FocusIn>", lambda _event, widget=entry, text=placeholder: self._clear_placeholder(widget, text))
        entry.bind("<Return>", lambda _event, widget=entry: add_command(widget))
        ttk.Button(controls, text="Add", command=lambda: add_command(entry)).pack(fill="x", pady=(0, 6))
        ttk.Button(
            controls, text="Remove Selected", command=lambda: self.remove_selected(listbox)
        ).pack(fill="x")
        listbox._entry = entry
        return listbox

    def _build_sources_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Hosts Sources")

        self.sources_tree = ttk.Treeview(
            tab, columns=("enabled", "name", "url"), show="headings", selectmode="browse"
        )
        self.sources_tree.heading("enabled", text="Enabled")
        self.sources_tree.heading("name", text="Name")
        self.sources_tree.heading("url", text="HTTPS Address")
        self.sources_tree.column("enabled", width=65, anchor="center", stretch=False)
        self.sources_tree.column("name", width=190)
        self.sources_tree.column("url", width=470)
        self.sources_tree.pack(fill="both", expand=True)

        form = ttk.Frame(tab)
        form.pack(fill="x", pady=(12, 0))
        ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="HTTPS Address").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.source_name = ttk.Entry(form)
        self.source_url = ttk.Entry(form)
        self.source_name.grid(row=1, column=0, sticky="ew")
        self.source_url.grid(row=1, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(form, text="Add Source", command=self.add_source).grid(row=1, column=2)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=3)

        source_actions = ttk.Frame(tab)
        source_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(source_actions, text="Enable/Disable", command=self.toggle_source).pack(side="left")
        ttk.Button(source_actions, text="Remove Source", command=self.remove_source).pack(
            side="left", padx=(8, 0)
        )

    def _build_log_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="Activity")
        self.log_text = tk.Text(tab, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    @staticmethod
    def _clear_placeholder(entry, placeholder):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)

    @staticmethod
    def _listbox_values(listbox):
        return list(listbox.get(0, tk.END))

    def _set_listbox(self, listbox, values):
        listbox.delete(0, tk.END)
        for value in values:
            listbox.insert(tk.END, value)

    def reload_config(self):
        try:
            config = blocker.load_full_config()
            self._set_listbox(self.site_list, config.get("blocked_sites", []))
            self._set_listbox(self.url_list, config.get("blocked_urls", []))
            self._set_listbox(self.app_list, config.get("blocked_apps", []))
            for item in self.sources_tree.get_children():
                self.sources_tree.delete(item)
            for source in config.get("hosts_sources", []):
                if isinstance(source, dict):
                    self.sources_tree.insert(
                        "", tk.END,
                    values=("Yes" if source.get("enabled", True) else "No", source.get("name", ""), source.get("url", "")),
                    )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"The configuration could not be loaded:\n{exc}")

    def save_config(self):
        sources = []
        for item in self.sources_tree.get_children():
            enabled, name, url = self.sources_tree.item(item, "values")
            sources.append({"name": name, "url": url, "enabled": enabled == "Yes"})
        blocker.save_full_config(
            {
                "blocked_sites": self._listbox_values(self.site_list),
                "blocked_urls": self._listbox_values(self.url_list),
                "blocked_apps": self._listbox_values(self.app_list),
                "hosts_sources": sources,
            }
        )

    def _add_unique(self, listbox, value):
        if value and value not in self._listbox_values(listbox):
            listbox.insert(tk.END, value)
            self.save_config()
            return True
        return False

    def add_site(self, entry):
        domain = blocker.normalize_domain(entry.get())
        if not domain:
            messagebox.showwarning(APP_TITLE, "Enter a valid domain, for example example.com.")
            return
        if self._add_unique(self.site_list, domain):
            entry.delete(0, tk.END)

    def add_url(self, entry):
        value = entry.get().strip().lower()
        if (
            not value
            or len(value) > 2048
            or "://" in value
            or " " in value
            or "/" not in value
            or any(ord(char) < 32 for char in value)
        ):
            messagebox.showwarning(APP_TITLE, "Enter a pattern without http://, for example youtube.com/shorts/*.")
            return
        if self._add_unique(self.url_list, value):
            entry.delete(0, tk.END)

    def add_app(self, entry):
        value = blocker.normalize_process_name(os.path.basename(entry.get().strip()))
        if not value:
            messagebox.showwarning(
                APP_TITLE, "Enter a valid process name without a path or wildcards."
            )
            return
        if self._add_unique(self.app_list, value):
            entry.delete(0, tk.END)

    def remove_selected(self, listbox):
        selected = list(listbox.curselection())
        for index in reversed(selected):
            listbox.delete(index)
        if selected:
            self.save_config()

    def add_source(self):
        name = self.source_name.get().strip()
        url = self.source_url.get().strip()
        if not name or urllib.parse.urlsplit(url).scheme.lower() != "https":
            messagebox.showwarning(APP_TITLE, "A name and a valid HTTPS address are required.")
            return
        existing_urls = [self.sources_tree.item(item, "values")[2] for item in self.sources_tree.get_children()]
        if url in existing_urls:
            messagebox.showinfo(APP_TITLE, "This source already exists.")
            return
        self.sources_tree.insert("", tk.END, values=("Yes", name, url))
        self.source_name.delete(0, tk.END)
        self.source_url.delete(0, tk.END)
        self.save_config()

    def toggle_source(self):
        selected = self.sources_tree.selection()
        if not selected:
            return
        item = selected[0]
        enabled, name, url = self.sources_tree.item(item, "values")
        self.sources_tree.item(item, values=("No" if enabled == "Yes" else "Yes", name, url))
        self.save_config()

    def remove_source(self):
        selected = self.sources_tree.selection()
        if selected:
            self.sources_tree.delete(selected[0])
            self.save_config()

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.block_button.configure(state=state)
        self.unblock_button.configure(state=state)
        self.update_button.configure(state=state)

    def _run_task(self, label, task):
        if self.busy:
            return
        self.save_config()
        self._set_busy(True)
        self.status_var.set(label)

        def worker():
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    task()
                self.events.put(("success", label, output.getvalue()))
            except Exception as exc:
                self.events.put(("error", label, output.getvalue(), str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "success":
                    _, label, output = event
                    self._append_log(f"{label}: successful\n{output}")
                else:
                    _, label, output, error = event
                    self._append_log(f"{label}: Error\n{output}{error}\n")
                    messagebox.showerror(APP_TITLE, f"{label} failed:\n{error}")
                self._set_busy(False)
                self._update_status_display()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _append_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message.rstrip() + "\n\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _update_status_display(self):
        try:
            content = blocker.read_hosts()
            active = blocker.BLOCK_MARKER_START in content and blocker.BLOCK_MARKER_END in content
            config = blocker.load_full_config()
            domain_count = len(config.get("blocked_sites", []))
            app_count = len(config.get("blocked_apps", []))
            source_count = len(config.get("hosts_sources", []))
            self.status_var.set("Blocking ACTIVE" if active else "Blocking INACTIVE")
            self.detail_var.set(
                f"{domain_count} custom domain{'s' if domain_count != 1 else ''} | "
                f"{app_count} app{'s' if app_count != 1 else ''} | "
                f"{source_count} source{'s' if source_count != 1 else ''}"
            )
        except Exception as exc:
            self.status_var.set("Status unavailable")
            self.detail_var.set(str(exc))

    def refresh_status(self):
        self._update_status_display()

    def apply_blocking(self):
        def task():
            blocker.block_sites(blocker.load_blocked_domains())
            blocker.apply_url_blocks(blocker.load_blocked_urls())
            blocker.kill_blocked_apps(blocker.load_blocked_apps())

        self._run_task("Enable blocking", task)

    def remove_blocking(self):
        def task():
            blocker.unblock_sites()
            blocker.remove_url_blocks()

        self._run_task("Remove blocking", task)

    def update_sources(self):
        def task():
            blocker.update_hosts_sources()
            content = blocker.read_hosts()
            if blocker.BLOCK_MARKER_START in content and blocker.BLOCK_MARKER_END in content:
                blocker.block_sites(blocker.load_blocked_domains())

        self._run_task("Update hosts lists", task)


def main():
    if os.name == "nt" and not blocker.is_admin():
        root = tk.Tk()
        root.withdraw()
        proceed = messagebox.askyesno(
            APP_TITLE,
            "Administrator privileges are required to edit the Windows hosts file.\n\n"
            "Restart the application as administrator now?",
        )
        if proceed and relaunch_as_admin():
            root.destroy()
            return
        messagebox.showerror(
            APP_TITLE,
            "The blocker cannot modify the Windows hosts file without administrator privileges.",
            parent=root,
        )
        root.destroy()
        return

    root = tk.Tk()
    BlockerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
