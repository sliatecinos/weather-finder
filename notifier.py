"""
notifier.py — Notificações toast (charm) do Windows 11 via winotify.

Dispara notificações no Action Center do Windows para:
- Resumo de novas consultas climáticas
- Alertas meteorológicos com sinal de aviso
"""

import os

from winotify import Notification, audio

APP_ID = "Weather Finder"


def _get_icon_path() -> str:
    """Retorna o caminho absoluto do ícone, se existir."""
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icon.ico"
    )
    if os.path.exists(icon_path):
        return icon_path
    return ""


def notify_weather_update(city: str, temperature, condition: str) -> None:
    """
    Dispara toast notification com o resumo da consulta climática.

    Args:
        city: Nome da cidade consultada
        temperature: Temperatura atual em °C
        condition: Descrição da condição climática
    """
    temp_str = f"{temperature}°C" if temperature is not None else "N/A"

    toast = Notification(
        app_id=APP_ID,
        title=f"Weather Finder — {city}",
        msg=f"Temperatura: {temp_str} | {condition}",
        icon=_get_icon_path(),
        duration="short",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()


def notify_alert(
    city: str, severity: str, description: str, risks: list[str]
) -> None:
    """
    Dispara toast notification de alerta meteorológico com sinal de aviso.

    Args:
        city: Nome da cidade
        severity: Nível de severidade (Perigo Potencial / Perigo / Grande Perigo)
        description: Tipo do alerta (ex: "Baixa Umidade", "Tempestade")
        risks: Lista de riscos descritos no alerta
    """
    risk_text = (
        "; ".join(r.strip() for r in risks[:2])
        if risks
        else "Consulte o aplicativo para detalhes."
    )

    toast = Notification(
        app_id=APP_ID,
        title=f"ALERTA: {description} — {city}",
        msg=f"Severidade: {severity}\n{risk_text}",
        icon=_get_icon_path(),
        duration="long",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()
