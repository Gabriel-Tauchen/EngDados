# Trabalho de Engenharia de Dados (ECOX14) da UNIFEI em 2026.2

## Fontes de dados

| Fonte | Formato | Acesso | Extraído em | Link |
| --- | --- | --- | --- | --- |
| Our World in Data - COVID-19 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/caesarmario/our-world-in-data-covid19-dataset |
| Air Traffic in Europe from 2016 to 2024 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/samithsachidanandan/air-traffic-in-europe-from-2016-to-2024 |

## Arquitetura e Decisões de Projeto

O projeto adota os princípios de Engenharia de Dados na Prática apresentados nas aulas da disciplina:
1. **Centralização de Configurações (`src/config.py`)**: Caminhos calculados dinamicamente a partir de `ROOT_DIR = Path(__file__).resolve().parent.parent`. Elimina erros de dependência do diretório corrente e centraliza parâmetros e pastas.
2. **Substituição de `print` por `logging`**: Rastreabilidade com carimbo de data, hora, nível (`INFO`, `WARNING`, `ERROR`) e gravação simultânea no terminal e em `pipeline.log` (ignorado no versionamento).
3. **Orquestração e Retomada (`src/pipeline.py`)**: O pipeline é estruturado em etapas sequenciais com declaração explícita de etapas futuras (`None`), suportando execução total ou retomada a partir de uma etapa intermediária (`python src/pipeline.py enrich`).
4. **Camada Prata e Enriquecimento**: O cruzamento entre as fontes tratadas é uma etapa de **Enriquecimento** que ainda pertence à camada **Prata** (`data/silver/enriched/`). A camada **Ouro** virá nas próximas semanas com modelagem dimensional e carga em banco.

---

## Execução do Pipeline

No PowerShell, a partir da pasta raiz do projeto e com o ambiente virtual ativado:

### 1. Executar o pipeline a partir da etapa de transformação:
```powershell
python src/pipeline.py transform
```
*(Executa a transformação de COVID-19, tráfego aéreo e o enriquecimento na Prata).*

### 2. Retomar apenas a etapa de enriquecimento (juntar fontes):
```powershell
python src/pipeline.py enrich
```

### 3. Rodar a suíte de testes automatizados:
```powershell
python -m unittest discover tests
```

---

## Decisões de Transformação (Camada Prata)

### COVID-19 (`data/silver/covid19/covid19.parquet`)
- **Remoção de espaços**: Padroniza nomes de colunas e textos.
- **Harmonização de escopo geográfico**: Inclui países europeus e parceiros Eurocontrol classificados pelo OWID fora do continente (Turquia, Armênia, Geórgia, Israel e Marrocos), totalizando **82.719 registros**.
- **Chave de identidade temporal**: `iso_code + date`.
- **Atributos de saúde e políticas públicas**: Preserva `stringency_index` (índice de rigor governamental de 0 a 100), `new_cases_per_million`, `total_cases_per_million` e variação percentual segura de novos casos.
- **Linhagem**: Registrada em `data/silver/covid19/provenance.jsonl`.

### Air Traffic Europe (`data/silver/air-traffic-EU/air-traffic-EU.parquet`)
- **Filtro de período**: Anos de 2019 a 2024 (período pré-pandêmico de referência e recuperação), com **677.190 registros**.
- **Chave de identidade temporal**: `YEAR + FLT_DATE + APT_ICAO`.
- **Métricas operacionais**: Cálculo de `TOTAL_FLIGHTS`, `TOTAL_IFR_FLIGHTS`, `IFR_SHARE` e variação percentual diária por aeroporto tratando divisões por zero.
- **Linhagem**: Registrada em `data/silver/air-traffic-EU/provenance.jsonl`.

---

## Junção e Enriquecimento (`data/silver/enriched/flights_covid_enriched.parquet`)

A série de voos foi unida ao contexto de COVID-19 por `(country_name, FLT_DATE)` $\leftrightarrow$ `(country_name, date)` utilizando `how="left"` e `validate="many_to_one"`.

- **Linhas na série (voos):** 677.190
- **Linhas no resultado:** 677.190 (o grão foi rigorosamente preservado, sem duplicação de linhas)
- **Sem par no cadastro de COVID:** 251.947

### Quem não casou

Uma junção `left` preserva todos os registros da série, permitindo diagnosticar exatamente quem não casou em vez de apagar os dados silenciosamente como faria um `inner join`:

- **113.975 registros são de 2019:** Período pré-pandêmico. A coleta de dados do OWID só se inicia em 03/01/2020. Manter 2019 sem par é fundamental para servir como linha de base (*baseline*) para o cálculo de índices de recuperação.
- **114.754 registros são de 2024:** O dataset público do OWID encerrou suas coletas no final de 2023, enquanto a Eurocontrol cobre 2024.
- **22.622 registros são do final de 2023:** Meses de novembro e dezembro após a interrupção das métricas diárias do OWID.
- **596 registros são do início de janeiro de 2020:** Dias anteriores ao primeiro caso notificado em pequenos parceiros Eurocontrol.
- **Durante os anos mais críticos da pandemia (2021 e 2022):** **0 registros sem par** (100% de correspondência entre voos e métricas de COVID).

### Atributos que só existem após a junção

Conforme o método ensinado em aula, foram calculados atributos que só são possíveis com a fusão das duas fontes:

1. `flights_per_million_pop`: Volume diário de voos do aeroporto normalizado pela população nacional do país (`TOTAL_FLIGHTS / (population / 1_000_000)`). Permite comparar a densidade e a dependência do transporte aéreo entre países de portes populacionais discrepantes (como Luxemburgo/Holanda vs. Alemanha).
2. `flights_to_cases_ratio`: Razão entre as operações de voo diárias e os novos casos de COVID no país (`TOTAL_FLIGHTS / (new_cases + 1)`), expressando a resiliência operacional da aviação frente à intensidade do contágio diário.
