import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=36, **kwargs)
        self.grid_columnconfigure(1, weight=1)

        self._lbl = ctk.CTkLabel(self, text="Ready", anchor="w")
        self._lbl.grid(row=0, column=0, padx=10, sticky="w")

        self._bar = ctk.CTkProgressBar(self, width=200)
        self._bar.set(0)
        self._bar.grid(row=0, column=1, padx=10, sticky="e")
        self._bar.grid_remove()

    def start_download(self, title: str):
        self._lbl.configure(text=f"Downloading: {title}", text_color="white")
        self._bar.set(0)
        self._bar.grid()

    def set_progress(self, value: float):
        self._bar.set(max(0.0, min(1.0, value)))

    def set_done(self, title: str):
        self._lbl.configure(text=f"Installed: {title}", text_color="#52b788")
        self._bar.set(1.0)
        self.after(3000, self.set_idle)

    def set_error(self, msg: str):
        self._lbl.configure(text=f"Error: {msg}", text_color="#e76f51")
        self._bar.grid_remove()

    def set_idle(self):
        self._lbl.configure(text="Ready", text_color="white")
        self._bar.grid_remove()
        self._bar.set(0)
