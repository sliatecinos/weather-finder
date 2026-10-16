"""
weather_finder.py — Aplicação principal Weather Finder.

Ferramenta desktop para monitoramento climático de cidades brasileiras.
Consulta dados da API Open-Meteo e alertas do INMET a cada 30 minutos
(configurável), exibindo resultados em log e disparando notificações
toast no Windows 11.
"""

import configparser
import os
import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta

from weather_api import geocode_city, fetch_weather
from alerts_api import fetch_alerts
from notifier import notify_weather_update, notify_alert
from meteograma_modal import MeteogramaModal

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.cfg")
ICON_FILE = os.path.join(BASE_DIR, "icon.ico")


# ---------------------------------------------------------------------------
# Geração de ícone
# ---------------------------------------------------------------------------
def _create_icon() -> str | None:
    """Gera um ícone simples da aplicação usando Pillow (se disponível)."""
    if os.path.exists(ICON_FILE):
        return ICON_FILE
    try:
        from PIL import Image, ImageDraw  # noqa: F401

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Sol
        draw.ellipse([8, 8, 40, 40], fill="#FFD700", outline="#FFA500", width=2)
        # Nuvem
        draw.ellipse([24, 28, 56, 52], fill="#FFFFFF", outline="#B0BEC5", width=1)
        draw.ellipse([32, 20, 60, 46], fill="#FFFFFF", outline="#B0BEC5", width=1)
        img.save(ICON_FILE, format="ICO", sizes=[(64, 64)])
        return ICON_FILE
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Leitura de configuração
# ---------------------------------------------------------------------------
def _read_config() -> tuple[str, int]:
    """Lê config.cfg e retorna (cidade, intervalo_minutos)."""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    city = cfg.get("Localizacao", "cidade", fallback="São Paulo").strip()
    interval = cfg.getint("Preferencias", "intervalo_minutos", fallback=30)
    return city, max(1, interval)


def _ensure_config() -> None:
    """Cria config.cfg com valores padrão caso não exista."""
    if os.path.exists(CONFIG_FILE):
        return
    cfg = configparser.ConfigParser()
    cfg["Localizacao"] = {"cidade": "São Paulo"}
    cfg["Preferencias"] = {"intervalo_minutos": "30"}
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        cfg.write(fh)


# ---------------------------------------------------------------------------
# Aplicação principal
# ---------------------------------------------------------------------------
class WeatherFinderApp:
    """Interface gráfica Tkinter + lógica de consulta em background."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Weather Finder")
        self.root.geometry("720x620")
        self.root.minsize(620, 420)
        self.root.resizable(True, True)
        self.root.configure(bg="#F0F0F0")

        # Ícone da janela
        icon = _create_icon()
        if icon and os.path.exists(icon):
            try:
                self.root.iconbitmap(icon)
            except tk.TclError:
                pass

        # Estado interno
        self._timer: threading.Timer | None = None
        self._running = True
        self._current_city_name: str = _read_config()[0]

        self._build_gui()

        # Primeira consulta logo após abertura
        self.root.after(500, self._trigger_fetch)

    # -----------------------------------------------------------------------
    # Construção da GUI
    # -----------------------------------------------------------------------
    def _build_gui(self) -> None:
        # --- Cabeçalho ---
        header = tk.Frame(self.root, bg="#2C3E50", padx=12, pady=10)
        header.pack(fill=tk.X)

        self.city_label = tk.Label(
            header,
            text="Weather Finder — Carregando...",
            fg="#ECF0F1",
            bg="#2C3E50",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self.city_label.pack(fill=tk.X)

        # --- Frame de alertas (oculto por padrão) ---
        self.alert_frame = tk.Frame(self.root, bg="#CCCCCC")
        self._last_alert_width: int = 0
        self.alert_frame.bind("<Configure>", self._on_alert_frame_configure)
        # Não exibir até que haja alertas

        # --- Área de log ---
        log_frame = tk.Frame(self.root, bg="#F0F0F0")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 2))

        self.log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 10),
            bg="#1E1E1E",
            fg="#D4D4D4",
            insertbackground="white",
            selectbackground="#264F78",
            padx=10,
            pady=10,
            relief=tk.FLAT,
            borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            log_frame, command=self.log_text.yview, troughcolor="#2D2D2D"
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Botões ---
        btn_frame = tk.Frame(self.root, bg="#F0F0F0", padx=10, pady=6)
        btn_frame.pack(fill=tk.X)

        self.fetch_btn = tk.Button(
            btn_frame,
            text="  Consultar Agora  ",
            command=self._manual_fetch,
            font=("Segoe UI", 10, "bold"),
            bg="#3498DB",
            fg="white",
            activebackground="#2980B9",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=16,
            pady=6,
        )
        self.fetch_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.meteograma_btn = tk.Button(
            btn_frame,
            text="  📊 Gráficos Meteograma (INMET)  ",
            command=self._open_meteograma_modal,
            font=("Segoe UI", 10, "bold"),
            bg="#16A085",
            fg="white",
            activebackground="#117A65",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=16,
            pady=6,
        )
        self.meteograma_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.quit_btn = tk.Button(
            btn_frame,
            text="  Encerrar  ",
            command=self._quit_app,
            font=("Segoe UI", 10, "bold"),
            bg="#E74C3C",
            fg="white",
            activebackground="#C0392B",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            padx=16,
            pady=6,
        )
        self.quit_btn.pack(side=tk.RIGHT)

        # --- Barra de status ---
        self.status_var = tk.StringVar(value="Aguardando primeira consulta...")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg="#555555",
            bg="#E8E8E8",
            anchor="w",
            padx=12,
            pady=4,
            relief=tk.FLAT,
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Fechar via "X" da janela = encerrar de forma limpa
        self.root.protocol("WM_DELETE_WINDOW", self._quit_app)

    # -----------------------------------------------------------------------
    # Controle de ciclo de vida
    # -----------------------------------------------------------------------
    def _quit_app(self) -> None:
        """Encerra a aplicação de forma segura."""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.root.destroy()

    # -----------------------------------------------------------------------
    # Disparo de consulta
    # -----------------------------------------------------------------------
    def _open_meteograma_modal(self) -> None:
        """Abre a janela modal com os gráficos de meteograma do INMET."""
        city = self._current_city_name or _read_config()[0]
        MeteogramaModal(self.root, initial_city=city)

    def _manual_fetch(self) -> None:
        """Consulta imediata acionada pelo botão."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._trigger_fetch()

    def _trigger_fetch(self) -> None:
        """Inicia a consulta em thread separada."""
        if not self._running:
            return
        t = threading.Thread(target=self._do_fetch, daemon=True)
        t.start()

    # -----------------------------------------------------------------------
    # Lógica de consulta (executa em thread de background)
    # -----------------------------------------------------------------------
    def _do_fetch(self) -> None:
        if not self._running:
            return

        try:
            # 1. Ler configuração (permite trocar cidade em tempo real)
            city_name, interval_min = _read_config()
            self._safe_ui(
                lambda: self.status_var.set(
                    f"Consultando dados para {city_name}..."
                )
            )

            # 2. Geocoding
            lat, lon, resolved_name = geocode_city(city_name)

            # 3. Dados climáticos
            weather = fetch_weather(lat, lon)

            # 4. Alertas INMET
            alerts = fetch_alerts(city_name)

            # 5. Montar log formatado
            now = datetime.now()
            log_entry = self._format_log(now, resolved_name, weather, alerts)

            # 6. Atualizar GUI (thread-safe)
            self._safe_ui(
                lambda: self._update_gui(
                    resolved_name, weather, alerts, log_entry
                )
            )

            # 7. Notificação toast — resumo da consulta
            try:
                atual = weather["atual"]
                notify_weather_update(
                    resolved_name, atual["temperatura"], atual["condicao"]
                )
            except Exception:
                pass  # Falha de notificação não deve travar o fluxo

            # 8. Notificações de alerta (uma por alerta encontrado)
            for alert in alerts:
                try:
                    notify_alert(
                        resolved_name,
                        alert["severidade"],
                        alert["descricao"],
                        alert["riscos"],
                    )
                except Exception:
                    pass

            # 9. Agendar próxima consulta
            self._schedule_next(now, interval_min)

        except Exception as exc:
            error_msg = str(exc)
            self._safe_ui(lambda: self._show_error(error_msg))
            # Tentar novamente em 2 minutos em caso de erro
            self._schedule_next(datetime.now(), 2, is_retry=True)

    # -----------------------------------------------------------------------
    # Agendamento
    # -----------------------------------------------------------------------
    def _schedule_next(
        self, last_time: datetime, minutes: int, *, is_retry: bool = False
    ) -> None:
        if not self._running:
            return

        next_dt = datetime.now() + timedelta(minutes=minutes)
        next_str = next_dt.strftime("%H:%M")

        if is_retry:
            status = (
                f"Erro na consulta — nova tentativa às {next_str}"
            )
        else:
            status = (
                f"Última consulta: {last_time.strftime('%H:%M:%S')} | "
                f"Próxima: {next_str} | Intervalo: {minutes} min"
            )

        self._safe_ui(lambda: self.status_var.set(status))

        self._timer = threading.Timer(minutes * 60, self._trigger_fetch)
        self._timer.daemon = True
        self._timer.start()

    # -----------------------------------------------------------------------
    # Formatação de log
    # -----------------------------------------------------------------------
    @staticmethod
    def _format_log(
        now: datetime, city: str, weather: dict, alerts: list[dict]
    ) -> str:
        atual = weather["atual"]
        sep = "=" * 55
        thin = "-" * 55
        lines: list[str] = [
            sep,
            f"  {now.strftime('%d/%m/%Y %H:%M:%S')} — {city}",
            thin,
            f"  Temperatura atual: {atual['temperatura']}°C  |  "
            f"Condição: {atual['condicao']}",
            f"  Vento: {atual['vento']} km/h  |  "
            f"Umidade: {atual['umidade']}%",
            "",
            "  Previsão próximas 6 horas:",
        ]

        for h in weather["previsao_horaria"]:
            lines.append(
                f"    {h['hora']}  ->  {h['temperatura']}°C  |  "
                f"Vento: {h['vento']} km/h  |  Umidade: {h['umidade']}%"
            )

        lines.append("")
        lines.append(
            f"  Máxima (6h): {weather['maxima_6h']}°C  |  "
            f"Mínima (6h): {weather['minima_6h']}°C  |  "
            f"Variação (6h): -/+{weather['maxima_6h'] - weather['minima_6h']:0.1f}°C"
        )

        if alerts:
            lines.append("")
            lines.append("  *** ALERTAS METEOROLÓGICOS ATIVOS ***")
            for a in alerts:
                lines.append(
                    f"    [{a['severidade']}] {a['descricao']}"
                )
                lines.append(
                    f"    Período: {a['inicio']} até {a['fim']}"
                )
                for risk in a.get("riscos", []):
                    lines.append(f"      - {risk.strip()}")
                for instr in a.get("instrucoes", []):
                    lines.append(f"      > {instr.strip()}")

        lines.append(sep)
        lines.append("")

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Atualização da GUI (chamado via root.after — thread-safe)
    # -----------------------------------------------------------------------
    def _update_gui(
        self,
        city: str,
        weather: dict,
        alerts: list[dict],
        log_entry: str,
    ) -> None:
        if not self._running:
            return

        atual = weather["atual"]
        self._current_city_name = city
        self.city_label.config(
            text=(
                f"Weather Finder — {city}  |  "
                f"{atual['temperatura']}°C  |  {atual['condicao']}"
            )
        )

        # --- Painel de alertas ---
        for widget in self.alert_frame.winfo_children():
            widget.destroy()

        if alerts:
            current_w = self.alert_frame.winfo_width()
            if current_w <= 1:
                current_w = self.root.winfo_width()
            if current_w <= 1:
                current_w = 720
            initial_wraplength = max(100, current_w - 28)

            for a in alerts:
                risk_str = "; ".join(r.strip() for r in a.get("riscos", [])[:2])
                alert_text = (
                    f"[{a.get('severidade', 'Alerta')}] {a.get('descricao', '')} — {risk_str}"
                )

                # Cor de fundo e fonte conforme severidade de cada alerta
                sev = a.get("severidade", "")
                if sev in ["Grande Perigo", "Perigo Potencial"]:
                    bg, fg = "#CC0000", "#FFFFFF"
                elif sev == "Perigo":
                    bg, fg = "#FF8C00", "#000000"
                else:
                    bg, fg = "#FFFE00", "#333333"

                lbl = tk.Label(
                    self.alert_frame,
                    text=alert_text,
                    bg=bg,
                    fg=fg,
                    font=("Segoe UI", 10),
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=initial_wraplength,
                    padx=12,
                    pady=4,
                )
                lbl.pack(fill=tk.X, pady=(0, 1))

            self.alert_frame.pack(
                fill=tk.X, after=self.city_label.master
            )
        else:
            self.alert_frame.pack_forget()
            self._last_alert_width = 0

        # --- Inserir log no topo (ordem decrescente) ---
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert("1.0", log_entry)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see("1.0")

    def _on_alert_frame_configure(self, event: tk.Event) -> None:
        """Ajusta dinamicamente a largura de quebra (wraplength) dos alertas ao redimensionar a janela."""
        if event.widget != self.alert_frame:
            return
        if event.width == self._last_alert_width or event.width <= 1:
            return
        self._last_alert_width = event.width
        new_wraplength = max(100, event.width - 28)
        for widget in self.alert_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(wraplength=new_wraplength)

    def _show_error(self, error_msg: str) -> None:
        if not self._running:
            return
        now = datetime.now()
        sep = "=" * 55
        thin = "-" * 55
        block = (
            f"{sep}\n"
            f"  {now.strftime('%d/%m/%Y %H:%M:%S')} — ERRO NA CONSULTA\n"
            f"{thin}\n"
            f"  {error_msg}\n"
            f"{sep}\n\n"
        )
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert("1.0", block)
        self.log_text.config(state=tk.DISABLED)
        self.city_label.config(text="Weather Finder — Erro na última consulta")

    # -----------------------------------------------------------------------
    # Utilitário thread-safe
    # -----------------------------------------------------------------------
    def _safe_ui(self, func) -> None:
        """Agenda execução de *func* na thread principal do Tkinter."""
        try:
            self.root.after(0, func)
        except tk.TclError:
            pass  # Janela já foi destruída


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def main() -> None:
    _ensure_config()
    root = tk.Tk()
    WeatherFinderApp(root)  # noqa: F841 — referência mantida pelo Tk
    root.mainloop()


if __name__ == "__main__":
    main()
