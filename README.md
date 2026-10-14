# Weather Finder 🌦️

Ferramenta desktop Windows para monitoramento climático de cidades brasileiras, com
consultas recorrentes, log em tempo real e notificações do *charm*.

---

## Funcionalidades ⚙️

- **Consulta automática (configurável)** a cada 30 minutos via API pública
  Open-Meteo — sem necessidade de API key
- **Dados exibidos**: temperatura atual, previsão horária (6h), máximas e
  mínimas, velocidade do vento e umidade relativa do ar (além da variação máx./mín.)
- **Alertas meteorológicos** oficiais do INMET (Instituto Nacional de
  Meteorologia), com detalhes de riscos e instruções de segurança
- **Log decrescente** (mais recente no topo) com registro completo de cada
  consulta e horário
- **Notificações toast** ("charm") do Windows 11 a cada consulta e alerta
- **Meteogramas dinâmicos do INMET**: visualização integrada dos gráficos oficiais
  do INMET em modal, com pesquisa por município, histórico por rodadas e atalho web
- **Arquivo de configuração** (`config.cfg`) editável para trocar a cidade consultada
  em tempo real

---

## Pré-requisitos 🪧

- 🐍 **Python 3.10+** instalado e disponível no PATH
- 💻 **Windows 10/11** (para notificações toast)
- 🌐 Conexão com a internet

---

## Instalação 🔧

1. Clone ou baixe este repositório:
   ```bash
   git clone https://github.com/neialuc/weather-finder.git
   cd weather-finder
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuração ⌨️

Edite o arquivo **`config.cfg`** com qualquer editor de texto:

```ini
[Localizacao]
# Informe o nome da cidade brasileira para consulta
cidade = São Paulo

[Preferencias]
# Intervalo de consulta em minutos (padrão: 30)
intervalo_minutos = 30
```

> **Dica:** Você pode alterar a cidade enquanto a aplicação estiver aberta.
> A próxima consulta usará automaticamente a nova cidade.

---

## Uso

### Opção 1 — Via script batch
Dê duplo-clique (ou execute em CLI/terminal) no script **`run.bat`**

### Opção 2 — Via terminal + python
```bash
python weather_finder.py
```

### Controles da interface

| Botão              | Ação                                              |
|--------------------|----------------------------------------------------|
| **Consultar Agora** | Força uma consulta imediata                       |
| **Meteograma (INMET)** | Abre o modal com os gráficos dinâmicos do INMET |
| **Encerrar**        | Fecha a aplicação de forma segura                 |

---

## APIs utilizadas

| API | Descrição | Custo |
|-----|-----------|-------|
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | Resolução de nome de cidade → coordenadas | Gratuito |
| [Open-Meteo Forecast](https://open-meteo.com/en/docs) | Dados climáticos atuais e previsão horária | Gratuito |
| [INMET Avisos Ativos](https://alertas2.inmet.gov.br/) | Alertas meteorológicos oficiais do Brasil | Gratuito |
| [INMET Meteogramas](https://meteograma.inmet.gov.br/) | Gráficos meteorológicos dinâmicos por município | Gratuito |

> Nenhuma API key é necessária.

---

## Estrutura do projeto 🗂️

```
weather-finder/
├── weather_finder.py     # Aplicação principal (GUI + lógica)
├── weather_api.py        # Cliente Open-Meteo (geocoding + forecast)
├── alerts_api.py         # Cliente INMET (alertas meteorológicos)
├── meteograma_api.py     # Cliente INMET (pesquisa e imagens de meteograma)
├── meteograma_modal.py   # Modal `Tkinter` com exibição dos gráficos e busca
├── notifier.py           # Notificações toast do Windows 11
├── config.cfg            # Configuração editável
├── wmo_codes.txt         # Lista local com códigos climáticos WMO
├── requirements.txt      # Dependências pip
├── run.bat               # Inicialização rápida
└── README.md             # Este arquivo
```

---

## Licença

Este projeto é de uso livre para fins pessoais e educacionais.
