"""
alerts_api.py — Cliente INMET para alertas meteorológicos ativos no Brasil.

Consulta a API pública do INMET (Instituto Nacional de Meteorologia)
para obter avisos/alertas meteorológicos ativos e filtra por cidade.
"""

import requests

INMET_ALERTS_URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"


def fetch_alerts(city_name: str) -> list[dict]:
    """
    Busca alertas meteorológicos ativos do INMET para uma cidade específica.

    A API retorna todos os alertas ativos do Brasil. Este método filtra
    os alertas cujo campo 'municipios' contém o nome da cidade informada.

    Args:
        city_name: Nome da cidade (ex: "São Paulo", "Teresina")

    Returns:
        Lista de dicionários com os alertas encontrados:
        [
            {
                "descricao": str,       # Ex: "Baixa Umidade", "Tempestade"
                "severidade": str,      # "Perigo Potencial", "Perigo", "Grande Perigo"
                "cor": str,             # Cor hex do alerta (ex: "#FFFE00")
                "riscos": list[str],    # Lista de riscos descritos
                "instrucoes": list[str],# Lista de instruções de segurança
                "inicio": str,          # Data/hora de início
                "fim": str,             # Data/hora de fim
            },
            ...
        ]
    """
    try:
        response = requests.get(INMET_ALERTS_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        # Em caso de falha de rede, retorna lista vazia sem interromper o fluxo
        return []
    except (ValueError, KeyError):
        return []

    alerts: list[dict] = []
    city_lower = city_name.strip().lower()

    # A API retorna alertas agrupados por chave (ex: "hoje", "amanha", etc.)
    for key, alert_list in data.items():
        if not isinstance(alert_list, list):
            continue

        for alert in alert_list:
            if not isinstance(alert, dict):
                continue

            municipios = alert.get("municipios", "")
            if not isinstance(municipios, str):
                continue

            # Verifica se o nome da cidade aparece na lista de municípios
            if city_lower in municipios.lower():
                alerts.append({
                    "descricao": alert.get("descricao", "Alerta meteorológico"),
                    "severidade": alert.get("severidade", "Desconhecida"),
                    "cor": alert.get("aviso_cor", "#FFFE00"),
                    "riscos": alert.get("riscos", []),
                    "instrucoes": alert.get("instrucoes", []),
                    "inicio": alert.get("inicio", "N/A"),
                    "fim": alert.get("fim", "N/A"),
                })
    print(f'Alertas em atividade no INMET: {len(data)}.')
    print(f'Alertas do municipio {city_lower}: {len(alerts)}.')
    return alerts
