"""
weather_api.py — Cliente Open-Meteo para dados climáticos e geocoding.

Utiliza a API pública Open-Meteo (sem API key) para:
- Resolver nome de cidade brasileira em coordenadas (geocoding)
- Obter condições climáticas atuais e previsão horária
"""
import os
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WMO_CODES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wmo_codes.txt")

# Cache de geocoding para evitar chamadas repetidas na mesma sessão
_geocode_cache: dict[str, tuple[float, float, str]] = {}


def load_wmo_codes(file_path: str = WMO_CODES_FILE) -> dict[int, str]:
    """
    Carrega o mapeamento de códigos WMO a partir de um arquivo de texto local.
    Formato esperado: cada linha no formato 'código: descrição' (ex: '0: Céu limpo').
    """
    codes: dict[int, str] = {}
    if not os.path.exists(file_path):
        return codes

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
            elif "=" in line:
                key, val = line.split("=", 1)
            else:
                continue
            try:
                code = int(key.strip())
                codes[code] = val.strip()
            except ValueError:
                continue

    return codes


# Tradução dos códigos WMO para português lida do arquivo local
WMO_CODES: dict[int, str] = load_wmo_codes()



def weather_code_to_description(code: int) -> str:
    """
    Traduz um código WMO para descrição em português.
    -------------------------------------------------
    Definição:
        99: Descrição mapeada.
    -------------------------------------------------
    """
    return WMO_CODES.get(code, f"Código desconhecido ({code})")


def geocode_city(city_name: str) -> tuple[float, float, str]:
    """
    Resolve o nome de uma cidade brasileira em coordenadas geográficas.

    Args:
        city_name: Nome da cidade (ex: "São Paulo", "Curitiba")

    Returns:
        Tupla (latitude, longitude, nome_resolvido)

    Raises:
        ValueError: Se a cidade não for encontrada
        requests.RequestException: Em caso de erro de rede
    """
    cache_key = city_name.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    params = {
        "name": city_name.strip(),
        "count": 5,
        "language": "pt",
        "format": "json",
    }

    response = requests.get(GEOCODING_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if "results" not in data or len(data["results"]) == 0:
        raise ValueError(f"Cidade não encontrada: '{city_name}'")

    # Priorizar resultados do Brasil (country_code == "BR")
    br_results = [r for r in data["results"] if r.get("country_code") == "BR"]
    result = br_results[0] if br_results else data["results"][0]

    lat = result["latitude"]
    lon = result["longitude"]
    admin1 = result.get("admin1", "")
    
    # Preserva o nome original digitado pelo usuário, mas adiciona o estado se disponível
    resolved = f"{city_name.strip()}, {admin1}" if admin1 else city_name.strip()

    _geocode_cache[cache_key] = (lat, lon, resolved)
    return lat, lon, resolved


def fetch_weather(lat: float, lon: float) -> dict:
    """
    Consulta dados climáticos atuais e previsão horária para as próximas 6 horas.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dicionário com estrutura:
        {
            "atual": {
                "temperatura": float,
                "umidade": int,
                "vento": float,
                "condicao_codigo": int,
                "condicao": str,
            },
            "previsao_horaria": [
                {"hora": str, "temperatura": float, "umidade": int, "vento": float},
                ...
            ],
            "maxima_6h": float,
            "minima_6h": float,
        }
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "forecast_hours": 7,  # hora atual + 6 próximas
        "timezone": "America/Sao_Paulo",
    }

    response = requests.get(FORECAST_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})

    # Extrair dados horários (pular primeira entrada = hora atual)
    hours: list[dict] = []
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humids = hourly.get("relative_humidity_2m", [])
    winds = hourly.get("wind_speed_10m", [])

    for i in range(1, min(7, len(times))):
        hora_str = times[i].split("T")[1][:5] if "T" in times[i] else times[i]
        hours.append({
            "hora": hora_str,
            "temperatura": temps[i] if i < len(temps) else None,
            "umidade": humids[i] if i < len(humids) else None,
            "vento": winds[i] if i < len(winds) else None,
        })

    # Calcular máxima/mínima nas próximas 6 horas
    future_temps = [h["temperatura"] for h in hours if h["temperatura"] is not None]

    return {
        "atual": {
            "temperatura": current.get("temperature_2m"),
            "umidade": current.get("relative_humidity_2m"),
            "vento": current.get("wind_speed_10m"),
            "condicao_codigo": current.get("weather_code", 0),
            "condicao": weather_code_to_description(
                current.get("weather_code", 0)
            ),
        },
        "previsao_horaria": hours,
        "maxima_6h": max(future_temps) if future_temps else None,
        "minima_6h": min(future_temps) if future_temps else None,
    }
