import contextlib
import io
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tstodlc.tools import pack


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class QueueWriter(io.TextIOBase):
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def writable(self):
        return True

    def write(self, text):
        text = ANSI_RE.sub("", text)
        text = text.replace("\r", "\n")
        if text:
            self.output_queue.put(("output", text))
        return len(text)

    def flush(self):
        return None


class TstoDlcGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("tstodlc")
        self.geometry("980x720")
        self.minsize(820, 620)

        self.output_queue = queue.Queue()
        self.worker = None

        self.operation = tk.StringVar(value="install")
        self.destination = tk.StringVar()
        self.platform = tk.StringVar()
        self.version = tk.StringVar()
        self.tier = tk.StringVar()
        self.language = tk.StringVar()
        self.priority = tk.StringVar()
        self.unzip = tk.BooleanVar(value=False)
        self.initial = tk.BooleanVar(value=False)
        self.tutorial = tk.BooleanVar(value=False)
        self.norevision = tk.BooleanVar(value=False)
        self.nozip = tk.BooleanVar(value=False)

        self._build_ui()
        self._poll_output()
        self._refresh_command()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(12, 10, 12, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)

        mode_frame = ttk.LabelFrame(toolbar, text="Operation", padding=8)
        mode_frame.grid(row=0, column=0, sticky="ew")
        for index, (label, value) in enumerate(
            (
                ("Install / update", "install"),
                ("Index only", "index"),
                ("View", "view"),
                ("Show files", "show"),
                ("Clean missing", "clean"),
            )
        ):
            ttk.Radiobutton(
                mode_frame,
                text=label,
                value=value,
                variable=self.operation,
                command=self._refresh_command,
            ).grid(row=0, column=index, padx=(0, 14), sticky="w")

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        left = ttk.Frame(main, padding=0)
        right = ttk.Frame(main, padding=0)
        main.add(left, weight=1)
        main.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        paths_header = ttk.Frame(left)
        paths_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        paths_header.columnconfigure(0, weight=1)
        ttk.Label(paths_header, text="DLC inputs").grid(row=0, column=0, sticky="w")
        ttk.Button(paths_header, text="Add folder", command=self._add_folders).grid(
            row=0, column=1, padx=(6, 0)
        )
        ttk.Button(paths_header, text="Add zip", command=self._add_files).grid(
            row=0, column=2, padx=(6, 0)
        )

        list_frame = ttk.Frame(left)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.inputs = tk.Listbox(list_frame, activestyle="dotbox", exportselection=False)
        self.inputs.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.inputs.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.inputs.configure(yscrollcommand=scroll.set)
        self.inputs.bind("<<ListboxSelect>>", lambda _event: self._refresh_command())

        path_actions = ttk.Frame(left)
        path_actions.grid(row=2, column=0, sticky="ew", pady=(6, 12))
        for column, (label, command) in enumerate(
            (
                ("Remove", self._remove_selected),
                ("Up", lambda: self._move_selected(-1)),
                ("Down", lambda: self._move_selected(1)),
                ("Clear", self._clear_inputs),
            )
        ):
            ttk.Button(path_actions, text=label, command=command).grid(
                row=0, column=column, padx=(0 if column == 0 else 6, 0), sticky="ew"
            )

        dest = ttk.LabelFrame(left, text="Destination", padding=8)
        dest.grid(row=3, column=0, sticky="ew")
        dest.columnconfigure(0, weight=1)
        ttk.Entry(dest, textvariable=self.destination).grid(row=0, column=0, sticky="ew")
        ttk.Button(dest, text="Browse", command=self._choose_destination).grid(
            row=0, column=1, padx=(6, 0)
        )

        options = ttk.LabelFrame(left, text="Options", padding=8)
        options.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        options.columnconfigure(1, weight=1)
        entries = (
            ("Platform", self.platform),
            ("Version", self.version),
            ("Tier", self.tier),
            ("Language", self.language),
            ("Priority", self.priority),
        )
        for row, (label, variable) in enumerate(entries):
            ttk.Label(options, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(options, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            entry.bind("<KeyRelease>", lambda _event: self._refresh_command())

        checks = (
            ("Unzip", self.unzip),
            ("Initial", self.initial),
            ("Tutorial", self.tutorial),
            ("No revision", self.norevision),
            ("No zip", self.nozip),
        )
        for row, (label, variable) in enumerate(checks, start=len(entries)):
            ttk.Checkbutton(
                options, text=label, variable=variable, command=self._refresh_command
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        command_frame = ttk.LabelFrame(right, text="Command preview", padding=8)
        command_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        command_frame.columnconfigure(0, weight=1)
        self.command_preview = tk.Text(command_frame, height=3, wrap=tk.WORD)
        self.command_preview.grid(row=0, column=0, sticky="ew")
        self.command_preview.configure(state=tk.DISABLED)

        run_frame = ttk.Frame(right)
        run_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        run_frame.columnconfigure(1, weight=1)
        self.run_button = ttk.Button(run_frame, text="Run", command=self._run)
        self.run_button.grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(run_frame, mode="indeterminate")
        self.progress.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        output_frame = ttk.LabelFrame(right, text="Output", padding=8)
        output_frame.grid(row=2, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(output_frame, wrap=tk.WORD)
        self.output.grid(row=0, column=0, sticky="nsew")
        output_scroll = ttk.Scrollbar(
            output_frame, orient=tk.VERTICAL, command=self.output.yview
        )
        output_scroll.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=output_scroll.set)

        self.destination.trace_add("write", lambda *_args: self._refresh_command())

    def _add_folders(self):
        folder = filedialog.askdirectory(title="Choose DLC directory")
        if folder:
            self.inputs.insert(tk.END, folder)
            self._refresh_command()

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Choose DLC zip file",
            filetypes=(("Zip files", "*.zip"), ("All files", "*.*")),
        )
        for file in files:
            self.inputs.insert(tk.END, file)
        self._refresh_command()

    def _choose_destination(self):
        folder = filedialog.askdirectory(title="Choose destination directory")
        if folder:
            self.destination.set(folder)

    def _selected_index(self):
        selection = self.inputs.curselection()
        return selection[0] if selection else None

    def _remove_selected(self):
        index = self._selected_index()
        if index is not None:
            self.inputs.delete(index)
            self._refresh_command()

    def _move_selected(self, direction):
        index = self._selected_index()
        if index is None:
            return
        new_index = index + direction
        if new_index < 0 or new_index >= self.inputs.size():
            return
        value = self.inputs.get(index)
        self.inputs.delete(index)
        self.inputs.insert(new_index, value)
        self.inputs.selection_set(new_index)
        self._refresh_command()

    def _clear_inputs(self):
        self.inputs.delete(0, tk.END)
        self._refresh_command()

    def _get_inputs(self):
        return list(self.inputs.get(0, tk.END))

    def _build_args(self):
        args = []
        operation = self.operation.get()

        if operation == "index":
            args.append("--index_only")
        elif operation == "view":
            args.append("--view")
        elif operation == "show":
            args.append("--show")
        elif operation == "clean":
            args.append("--clean")

        if operation == "install":
            values = (
                ("--platform", self.platform.get().strip()),
                ("--version", self.version.get().strip()),
                ("--tier", self.tier.get().strip()),
                ("--language", self.language.get().strip()),
            )
            for option, value in values:
                if value:
                    args.extend((option, value))

            priority = self.priority.get().strip()
            if priority:
                args.extend(("--priority", priority))

            if self.unzip.get():
                args.append("--unzip")
            if self.initial.get():
                args.append("--initial")
            if self.tutorial.get():
                args.append("--tutorial")
            if self.norevision.get():
                args.append("--norevision")
            if self.nozip.get():
                args.append("--nozip")

        inputs = self._get_inputs()
        destination = self.destination.get().strip()
        if operation == "clean" and not inputs:
            inputs = ["."]
        args.extend(inputs)
        if destination:
            args.append(destination)
        return args

    def _validate(self):
        operation = self.operation.get()
        inputs = self._get_inputs()
        destination = self.destination.get().strip()

        if operation != "clean" and not inputs:
            messagebox.showerror("Missing input", "Add at least one DLC input.")
            return False
        if not destination:
            messagebox.showerror("Missing destination", "Choose a destination directory.")
            return False

        priority = self.priority.get().strip()
        if priority:
            try:
                int(priority)
            except ValueError:
                messagebox.showerror("Invalid priority", "Priority must be an integer.")
                return False

        missing = [path for path in inputs if not Path(path).exists()]
        if missing:
            messagebox.showerror("Missing path", f"Path does not exist:\n{missing[0]}")
            return False
        return True

    def _refresh_command(self):
        args = self._build_args()
        preview = "tstodlc " + " ".join(self._quote_arg(arg) for arg in args)
        self.command_preview.configure(state=tk.NORMAL)
        self.command_preview.delete("1.0", tk.END)
        self.command_preview.insert("1.0", preview)
        self.command_preview.configure(state=tk.DISABLED)

    def _quote_arg(self, arg):
        return f'"{arg}"' if any(character.isspace() for character in arg) else arg

    def _run(self):
        if self.worker is not None and self.worker.is_alive():
            return
        if not self._validate():
            return

        args = self._build_args()
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, f"$ tstodlc {' '.join(self._quote_arg(arg) for arg in args)}\n\n")
        self.run_button.configure(state=tk.DISABLED)
        self.progress.start(12)

        self.worker = threading.Thread(target=self._run_worker, args=(args,), daemon=True)
        self.worker.start()

    def _run_worker(self, args):
        writer = QueueWriter(self.output_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                pack.main(args)
        except SystemExit as error:
            if error.code not in (None, 0):
                self.output_queue.put(("output", f"\nExited with status {error.code}\n"))
        except Exception as error:
            self.output_queue.put(("output", f"\nError: {error}\n"))
        finally:
            self.output_queue.put(("done", None))

    def _poll_output(self):
        while True:
            try:
                event, payload = self.output_queue.get_nowait()
            except queue.Empty:
                break

            if event == "output":
                self.output.insert(tk.END, payload)
                self.output.see(tk.END)
            elif event == "done":
                self.progress.stop()
                self.run_button.configure(state=tk.NORMAL)

        self.after(80, self._poll_output)


def main():
    app = TstoDlcGui()
    app.mainloop()


if __name__ == "__main__":
    main()
