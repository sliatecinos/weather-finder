"""
meteograma_modal.py — Modal de visualização dos gráficos de meteogramas do INMET.

Exibe os meteogramas dinâmicos do INMET (semelhante à página
https://meteograma.inmet.gov.br/{geocode}/dinamico) em janela Tkinter Toplevel,
com campo de busca de município (//*[@id="search"]), visualização da imagem
(/html/body/div[1]/div/div/div/div/img), rolagem vertical/horizontal,
opções de rodada (00/12 UTC), salvamento em PNG e atalho para o navegador.
"""

import io
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from PIL import Image, ImageTk

from meteograma_api import (
    search_inmet_cities,
    fetch_meteograma_image,
    get_meteograma_web_url,
)


class MeteogramaModal:
    """Janela modal para consulta e exibição dos meteogramas do INMET."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, initial_city: str = "Campo Limpo Paulista") -> None:
        self.parent = parent
        self.initial_city = initial_city.strip() or "Campo Limpo Paulista"

        # Fila thread-safe para comunicação entre background workers e a thread da UI
        self._queue: queue.Queue = queue.Queue()

        # Janela Toplevel
        self.window = tk.Toplevel(parent)
        self.window.title(f"INMET — Meteograma Dinâmico ({self.initial_city})")
        self.window.geometry("860x720")
        self.window.minsize(680, 480)
        self.window.configure(bg="#F4F6F9")

        # Tenta herdar ícone do parent
        try:
            self.window.iconbitmap(parent.iconbitmap())
        except Exception:
            pass

        # Estado interno
        self._current_geocode: int | None = None
        self._current_city_label: str = self.initial_city
        self._raw_image_bytes: bytes | None = None
        self._pil_image: Image.Image | None = None
        self._tk_image: ImageTk.PhotoImage | None = None
        self._fit_to_width: bool = False
        self._is_loading: bool = False
        self._found_cities: list[dict] = []
        self._poll_active = True

        self._build_ui()

        # Inicia loop de escuta de eventos da fila
        self._poll_queue()

        # Inicia a busca e carregamento com a cidade inicial
        self.window.after(100, lambda: self._start_search(self.initial_city))

        # Encerramento limpo
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        self._poll_active = False
        self.window.destroy()

    def _poll_queue(self) -> None:
        """Processa funções enfileiradas pelas threads na thread principal do Tkinter."""
        if not self._poll_active or not self.window.winfo_exists():
            return
        try:
            while True:
                callback = self._queue.get_nowait()
                try:
                    callback()
                except Exception:
                    pass
        except queue.Empty:
            pass

        if self._poll_active and self.window.winfo_exists():
            self.window.after(50, self._poll_queue)

    # -----------------------------------------------------------------------
    # Construção da Interface Gráfica
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 1. Barra de cabeçalho
        header = tk.Frame(self.window, bg="#1E3A8A", padx=16, pady=10)
        header.pack(fill=tk.X)

        header_title = tk.Label(
            header,
            text="INMET :: Meteogramas Dinâmicos",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg="#1E3A8A",
            anchor="w",
        )
        header_title.pack(side=tk.LEFT)

        self.web_btn = tk.Button(
            header,
            text="🌐 Abrir no Navegador",
            command=self._open_in_browser,
            font=("Segoe UI", 9, "bold"),
            bg="#3B82F6",
            fg="white",
            activebackground="#2563EB",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=12,
            pady=4,
        )
        self.web_btn.pack(side=tk.RIGHT)

        # 2. Barra de pesquisa e controle (representando //*[@id="search"] e rodadas)
        control_frame = tk.Frame(self.window, bg="#FFFFFF", padx=14, pady=10, relief=tk.RIDGE, bd=1)
        control_frame.pack(fill=tk.X, padx=10, pady=8)

        # Label do input de busca
        search_lbl = tk.Label(
            control_frame,
            text="Município:",
            font=("Segoe UI", 10, "bold"),
            bg="#FFFFFF",
            fg="#1F2937",
        )
        search_lbl.pack(side=tk.LEFT, padx=(0, 6))

        # Campo de entrada (//*[@id="search"])
        self.search_entry = tk.Entry(
            control_frame,
            font=("Segoe UI", 10),
            bg="#F9FAFB",
            fg="#111827",
            relief=tk.SOLID,
            bd=1,
            width=26,
        )
        self.search_entry.insert(0, self.initial_city)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 6))
        self.search_entry.bind("<Return>", lambda event: self._on_search_click())

        # Botão Buscar
        self.search_btn = tk.Button(
            control_frame,
            text="🔍 Buscar",
            command=self._on_search_click,
            font=("Segoe UI", 9, "bold"),
            bg="#2563EB",
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            pady=4,
        )
        self.search_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Seletor de cidades encontradas (Combobox)
        self.cities_combo = ttk.Combobox(
            control_frame,
            state="readonly",
            width=28,
            font=("Segoe UI", 9),
        )
        self.cities_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.cities_combo.bind("<<ComboboxSelected>>", self._on_city_selected)

        # Seletor de Rodada
        rodada_lbl = tk.Label(
            control_frame,
            text="Rodada:",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#374151",
        )
        rodada_lbl.pack(side=tk.LEFT, padx=(6, 4))

        self.rodada_combo = ttk.Combobox(
            control_frame,
            values=["Automática", "00 UTC", "12 UTC"],
            state="readonly",
            width=12,
            font=("Segoe UI", 9),
        )
        self.rodada_combo.current(0)
        self.rodada_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.rodada_combo.bind("<<ComboboxSelected>>", lambda e: self._reload_current())

        # Botões de visualização à direita
        self.save_btn = tk.Button(
            control_frame,
            text="💾 Salvar Imagem",
            command=self._save_image,
            font=("Segoe UI", 9),
            bg="#10B981",
            fg="white",
            activebackground="#059669",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(4, 0))

        self.zoom_btn = tk.Button(
            control_frame,
            text="↔️ Ajustar Largura",
            command=self._toggle_zoom,
            font=("Segoe UI", 9),
            bg="#6B7280",
            fg="white",
            activebackground="#4B5563",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )
        self.zoom_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # 3. Área de visualização do gráfico com Canvas e Scrollbars
        view_frame = tk.Frame(self.window, bg="#E5E7EB")
        view_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        self.canvas = tk.Canvas(
            view_frame,
            bg="#FFFFFF",
            highlightthickness=0,
            cursor="cross",
        )
        self.v_scrollbar = tk.Scrollbar(view_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scrollbar = tk.Scrollbar(view_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set,
        )

        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Suporte a Scroll do Mouse (Windows)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.window.bind("<Configure>", self._on_window_resize)

        # 4. Barra de status inferior
        self.status_var = tk.StringVar(value="Pronto para consulta.")
        status_bar = tk.Label(
            self.window,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg="#4B5563",
            bg="#E5E7EB",
            anchor="w",
            padx=12,
            pady=4,
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # -----------------------------------------------------------------------
    # Controle de Mouse e Scroll
    # -----------------------------------------------------------------------
    def _on_mousewheel(self, event) -> None:
        """Permite rolagem vertical rápida pelo mouse wheel."""
        if not self.window.winfo_exists():
            return
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_window_resize(self, event) -> None:
        """Reajusta imagem caso modo 'ajustar largura' esteja ativo."""
        if self._fit_to_width and self._pil_image is not None:
            self._render_image()

    # -----------------------------------------------------------------------
    # Pesquisa e Carregamento (Thread-Safe via Queue)
    # -----------------------------------------------------------------------
    def _on_search_click(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Aviso", "Informe o nome de um município para pesquisar.", parent=self.window)
            return
        self._start_search(query)

    def _start_search(self, query: str) -> None:
        if self._is_loading:
            return
        self._is_loading = True
        self.search_btn.config(state=tk.DISABLED)
        self.status_var.set(f"Pesquisando município '{query}' no INMET...")
        self._draw_message(f"🔍 Pesquisando '{query}' no INMET...")

        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query: str) -> None:
        try:
            results = search_inmet_cities(query)
            self._queue.put(lambda: self._handle_search_results(results, query))
        except Exception as e:
            err_msg = f"Erro ao pesquisar município: {e}"
            self._queue.put(lambda: self._handle_error(err_msg))

    def _handle_search_results(self, results: list[dict], query: str) -> None:
        self._found_cities = results
        if not results:
            self._is_loading = False
            self.search_btn.config(state=tk.NORMAL)
            self.cities_combo.config(values=[])
            self.cities_combo.set("Nenhum município encontrado")
            msg = f"Nenhum município encontrado para '{query}'. Tente outro nome ou código IBGE."
            self.status_var.set(msg)
            self._draw_message(f"⚠️ {msg}")
            return

        # Popula o Combobox com as opções encontradas
        labels = [item["label"] for item in results]
        self.cities_combo.config(values=labels)
        self.cities_combo.current(0)

        # Seleciona o primeiro resultado automaticamente
        chosen = results[0]
        self._load_meteograma(chosen["geocode"], chosen["label"])

    def _on_city_selected(self, event) -> None:
        idx = self.cities_combo.current()
        if 0 <= idx < len(self._found_cities):
            chosen = self._found_cities[idx]
            self._load_meteograma(chosen["geocode"], chosen["label"])

    def _reload_current(self) -> None:
        if self._current_geocode:
            self._load_meteograma(self._current_geocode, self._current_city_label)

    def _load_meteograma(self, geocode: int, city_label: str) -> None:
        self._current_geocode = geocode
        self._current_city_label = city_label
        self._is_loading = True
        self.search_btn.config(state=tk.DISABLED)

        # Atualiza título da janela
        self.window.title(f"INMET — Meteograma Dinâmico ({city_label})")

        rodada_choice = self.rodada_combo.get()
        rodada_arg = None
        if "00" in rodada_choice:
            rodada_arg = "00"
        elif "12" in rodada_choice:
            rodada_arg = "12"

        self.status_var.set(f"Baixando meteograma para {city_label} (IBGE: {geocode})...")
        self._draw_message(f"⏳ Baixando gráfico de meteograma para {city_label}...\nAguarde alguns instantes.")

        threading.Thread(
            target=self._fetch_image_thread,
            args=(geocode, city_label, rodada_arg),
            daemon=True,
        ).start()

    def _fetch_image_thread(self, geocode: int, city_label: str, rodada_arg: str | None) -> None:
        try:
            img_bytes, date_used, rodada_used = fetch_meteograma_image(geocode, rodada=rodada_arg)
            self._queue.put(
                lambda: self._handle_image_success(img_bytes, geocode, city_label, date_used, rodada_used)
            )
        except Exception as err:
            err_msg = str(err)
            self._queue.put(lambda: self._handle_error(err_msg))

    def _handle_image_success(
        self,
        img_bytes: bytes,
        geocode: int,
        city_label: str,
        date_used: str,
        rodada_used: str,
    ) -> None:
        self._is_loading = False
        self.search_btn.config(state=tk.NORMAL)
        self._raw_image_bytes = img_bytes

        try:
            pil_img = Image.open(io.BytesIO(img_bytes))
            self._pil_image = pil_img
            self._render_image()

            status_text = (
                f"Município: {city_label} | IBGE: {geocode} | Data: {date_used} | "
                f"Rodada: {rodada_used} UTC | Resolução: {pil_img.width}x{pil_img.height} px"
            )
            self.status_var.set(status_text)
        except Exception as e:
            self._handle_error(f"Erro ao processar imagem retornada: {e}")

    def _handle_error(self, message: str) -> None:
        self._is_loading = False
        self.search_btn.config(state=tk.NORMAL)
        self.status_var.set(f"Erro: {message}")
        self._draw_message(f"⚠️ {message}\n\nTente selecionar outra rodada ou verificar a conexão.")

    # -----------------------------------------------------------------------
    # Renderização e Manipulação da Imagem
    # -----------------------------------------------------------------------
    def _render_image(self) -> None:
        if self._pil_image is None:
            return

        img = self._pil_image
        canvas_width = self.canvas.winfo_width()

        if self._fit_to_width and canvas_width > 200:
            target_width = canvas_width - 10
            scale = target_width / img.width
            target_height = int(img.height * scale)
            img_to_show = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            img_to_show = img

        self._tk_image = ImageTk.PhotoImage(img_to_show)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_image)
        self.canvas.config(scrollregion=(0, 0, img_to_show.width, img_to_show.height))

    def _toggle_zoom(self) -> None:
        self._fit_to_width = not self._fit_to_width
        self.zoom_btn.config(text="🔍 100% (Real)" if self._fit_to_width else "↔️ Ajustar Largura")
        self._render_image()

    def _draw_message(self, text: str) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            30,
            50,
            anchor=tk.NW,
            text=text,
            font=("Segoe UI", 11),
            fill="#374151",
        )
        self.canvas.config(scrollregion=(0, 0, 400, 200))

    # -----------------------------------------------------------------------
    # Ações Extras
    # -----------------------------------------------------------------------
    def _open_in_browser(self) -> None:
        """Abre a página oficial do meteograma no navegador."""
        if self._current_geocode:
            url = get_meteograma_web_url(self._current_geocode)
        else:
            url = "https://meteograma.inmet.gov.br/"
        webbrowser.open(url)

    def _save_image(self) -> None:
        """Salva a imagem do meteograma no computador."""
        if not self._raw_image_bytes:
            messagebox.showinfo("Aviso", "Nenhum gráfico carregado para salvar.", parent=self.window)
            return

        default_name = f"meteograma_{self._current_geocode or 'inmet'}.png"
        filepath = filedialog.asksaveasfilename(
            parent=self.window,
            title="Salvar Gráfico do Meteograma",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("Imagem PNG", "*.png"), ("Todos os arquivos", "*.*")],
        )
        if filepath:
            try:
                with open(filepath, "wb") as f:
                    f.write(self._raw_image_bytes)
                messagebox.showinfo("Sucesso", f"Gráfico salvo com sucesso em:\n{filepath}", parent=self.window)
            except Exception as e:
                messagebox.showerror("Erro ao salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self.window)
