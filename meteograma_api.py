"""
meteograma_api.py — Integração com a API de Meteogramas do INMET.

Fornece funções para pesquisar municípios brasileiros pelo serviço de autocomplete
do INMET e obter os gráficos meteorológicos (meteogramas dinâmicos) em imagem PNG.
"""

import base64
from datetime import datetime, timedelta
import urllib.parse
import requests

INMET_AUTOCOMPLETE_URL = "https://apiprevmet3.inmet.gov.br/autocomplete"
INMET_METEOGRAMA_API = "https://apiprevmet3.inmet.gov.br/meteograma"
INMET_METEOGRAMA_WEB = "https://meteograma.inmet.gov.br/{geocode}/dinamico"


def get_meteograma_web_url(geocode: int | str) -> str:
    """Retorna a URL oficial do meteograma dinâmico no portal do INMET."""
    return INMET_METEOGRAMA_WEB.format(geocode=geocode)


def search_inmet_cities(query: str, timeout: int = 10) -> list[dict]:
    """
    Pesquisa municípios no autocomplete do INMET.
    Retorna lista de dicionários com 'label', 'geocode', 'lat', 'lon'.
    """
    cleaned = query.strip()
    if not cleaned:
        return []

    # Se for código IBGE numérico direto (ex: 3509601)
    if cleaned.isdigit() and len(cleaned) in (6, 7):
        return [{
            "id": f"IBGE-{cleaned}",
            "label": f"Código IBGE: {cleaned}",
            "value": cleaned,
            "geocode": int(cleaned),
        }]

    # Tentativa 1: busca direta com o texto digitado
    queries_to_try = [cleaned]

    # Tentativa 2: remover sufixos de estado como ", SP" ou " - SP"
    for sep in [",", "-"]:
        if sep in cleaned:
            base_part = cleaned.split(sep)[0].strip()
            if base_part and base_part not in queries_to_try:
                queries_to_try.append(base_part)

    for q in queries_to_try:
        try:
            encoded_query = urllib.parse.quote(q)
            resp = requests.get(f"{INMET_AUTOCOMPLETE_URL}/{encoded_query}", timeout=timeout)
            if resp.status_code == 200:
                results = resp.json()
                if isinstance(results, list) and results:
                    cleaned_results = []
                    for item in results:
                        geocode = item.get("geocode")
                        if geocode:
                            cleaned_results.append({
                                "id": item.get("id", item.get("label", "")),
                                "label": item.get("label", item.get("value", "")),
                                "value": item.get("value", ""),
                                "geocode": int(geocode),
                                "lat": item.get("latitude"),
                                "lon": item.get("longitude"),
                            })
                    if cleaned_results:
                        return cleaned_results
        except Exception:
            continue

    return []


def fetch_meteograma_image(
    geocode: int | str,
    date_str: str | None = None,
    rodada: str | None = None,
    timeout: int = 15,
) -> tuple[bytes, str, str]:
    """
    Obtém a imagem PNG do meteograma do INMET para o código IBGE indicado.
    
    Args:
        geocode: Código IBGE (ex: 3509601)
        date_str: Data no formato YYYY-MM-DD (se None, tenta hoje e recua se necessário)
        rodada: '00' ou '12' (se None, testa automaticamente a mais recente)
        timeout: Timeout em segundos por requisição

    Returns:
        Tupla (png_bytes, data_utilizada, rodada_utilizada)

    Raises:
        ValueError: Se o gráfico não for encontrado para a localidade informada
        requests.RequestException: Em caso de falha de conexão
    """
    today = datetime.now().date()
    
    # Se usuário especificou data e rodada, tenta apenas ela primeiro
    candidates: list[tuple[str, str]] = []
    if date_str and rodada:
        candidates.append((date_str, rodada))
    elif date_str:
        candidates.extend([(date_str, "12"), (date_str, "00")])
    elif rodada:
        d_today = today.strftime("%Y-%m-%d")
        d_prev = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        candidates.extend([(d_today, rodada), (d_prev, rodada)])
    else:
        # Modo automático: tenta hoje 12h, hoje 00h, ontem 12h, ontem 00h
        d_today = today.strftime("%Y-%m-%d")
        d_prev = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        candidates = [
            (d_today, "12"),
            (d_today, "00"),
            (d_prev, "12"),
            (d_prev, "00"),
        ]

    last_error = None
    for d, r in candidates:
        url = f"{INMET_METEOGRAMA_API}/{geocode}/{d}/{r}"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                b64_str = data.get("base64", "")
                if (
                    b64_str
                    and b64_str.startswith("data:image/png;base64,")
                    and "data:text/xml" not in b64_str
                ):
                    raw_data = base64.b64decode(b64_str.split(",", 1)[1])
                    return raw_data, d, r
        except requests.RequestException as err:
            last_error = err
            continue

    if last_error:
        raise last_error

    raise ValueError(f"Gráfico do meteograma não encontrado no INMET para o código {geocode}.")
