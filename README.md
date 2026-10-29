# Trabalho de Engenharia de Dados (ECOX14) da UNIFEI em 2026.2

## Fontes de dados

| Fonte | Formato | Acesso | Extraído em | Link |
| --- | --- | --- | --- | --- |
| Our World in Data - COVID-19 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/caesarmario/our-world-in-data-covid19-dataset |
| Air Traffic in Europe from 2016 to 2024 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/samithsachidanandan/air-traffic-in-europe-from-2016-to-2024 |

## Observações gerais

- O dataset de COVID-19 foi armazenado em bronze em `data/bronze/covid19`.
- O dataset de tráfego aéreo está em `data/bronze/air-traffic-EU` e foi dividido em arquivos por ano.
- O projeto usa a camada bronze como versão original e a camada silver como versão tratada e padronizada para análise.

## Decisões de transformação (COVID-19)

- 1) Remoção de espaços em nomes de colunas e valores textuais: padroniza `iso_code`, `location`, `continent` e demais campos para evitar inconsistências de merge, filtros e comparações entre arquivos.
- 2) Filtro de escopo geográfico (Europa + Parceiros Eurocontrol): 267.366 linhas removidas, restando 82.719 linhas; o dataset original do OWID classifica países como Turquia (`Turkey`), Armênia, Geórgia, Israel e Marrocos fora do continente europeu (`Asia`/`Africa`), mas eles compõem o escopo de monitoramento do Eurocontrol. O filtro preserva esses parceiros essenciais para permitir o cruzamento analítico com a malha aérea.
- 3) Validação da chave temporal: validação para `iso_code + date`; garante que cada país tenha no máximo uma observação por dia, preservando a integridade da série temporal.
- 4) Conversão da coluna `date` para datetime: transforma a data em tipo temporal, permitindo ordenação, filtros por período e cálculos de evolução ao longo do tempo.
- 5) Incorporação do `stringency_index`: preserva o índice de rigor de restrições governamentais (0 a 100), variável analítica essencial para correlacionar o fechamento de fronteiras com a queda no volume de voos.
- 6) Cálculo robusto de variação percentual (`pct_change`): substitui divisões por zero e valores infinitos (`inf`) por zero.
- 7) Persistência canônica e governança na silver: grava `data/silver/covid19/covid19.parquet` e registra a linhagem da transformação em `data/silver/covid19/provenance.jsonl`.

> Resumo do impacto: o dataset cru tinha 350.085 linhas; após a limpeza, filtro harmonizado de escopo e tipagem, o silver final ficou com 82.719 linhas prontas para cruzamento analítico.

## Decisões de transformação (Air Traffic Europe)

- 1) Seleção dos arquivos mais recentes por ano: 6 arquivos usados (2019 a 2024); considera apenas as versões mais recentes de extração de cada ano na camada bronze.
- 2) Filtro de escopo 2019+ : mantém o período de 2019 a 2024 para analisar o padrão pré-pandemia e a recuperação subsequente.
- 3) Limpeza de colunas e padronização de textos: normaliza nomes e espaçamentos em aeroportos, países e códigos ICAO.
- 4) Seleção das colunas operacionais e métricas derivadas: preserva identificadores, calcula `TOTAL_FLIGHTS`, `TOTAL_IFR_FLIGHTS`, `IFR_SHARE` e a variação percentual de voos de forma segura (tratando infinitos e nulos).
- 5) Conversão de tipos: `FLT_DATE` convertido para datetime, métricas numéricas tratadas.
- 6) Remoção de duplicatas exatas: garante integridade sem sobrecontagens artificiais.
- 7) Persistência canônica e linhagem na silver: grava `data/silver/air-traffic-EU/air-traffic-EU.parquet` e registra metadados em `data/silver/air-traffic-EU/provenance.jsonl`.

> Resumo do impacto: o conjunto bruto de 2019-2024 totaliza 677.190 registros operacionais por aeroporto e data, mantidos integralmente sem duplicatas.

## Estrutura geral do projeto

- `data/bronze/` = dados originais, sem transformação
- `data/silver/` = dados tratados, em formato Parquet canônico, com rastreabilidade em `provenance.jsonl`
- `data/gold/` = agregados analíticos, modelos dimensionais e tabelas prontas para consumo de BI
- `reports/` = relatórios de profiling de dados
- `src/` = scripts de ingestão, transformação e orquestração
- `tests/` = testes unitários automatizados

## Execução do pipeline

No PowerShell, a partir da pasta raiz do projeto e com o ambiente virtual ativado:

### 1. Executar todo o pipeline Silver de forma unificada:
```powershell
python src/main.py
```
*(Executa a transformação de COVID-19 e Tráfego Aéreo sequencialmente, gravando arquivos canônicos e registrando a linhagem em `provenance.jsonl`).*

### 2. Executar etapas avulsas (se necessário):
```powershell
# Ingestão do Kaggle (requer token configurado)
python src/main.py --stage ingest

# Ou execução direta dos módulos
python src/transform_covid_data.py
python src/transform_flight_data.py
```

### 3. Executar a suíte de testes automatizados:
```powershell
python -m unittest discover tests
```

### 4. Gerar relatórios de profiling (Exploração):
```powershell
# Profiling de ambos os datasets
python src/explore.py --dataset all

# Ou profiling de um dataset específico
python src/explore.py --dataset covid19
python src/explore.py --dataset air-traffic
```

## Mapeamento canônico de países

Para manter a compatibilidade entre o dataset de tráfego aéreo (Eurocontrol) e o dataset de COVID-19 (OWID), foi definido um dicionário de padronização em `src/country_mapping.py`.

- A chave de normalização usa texto em minúsculas, sem acentos e sem espaços extras.
- Os nomes canônicos seguem a convenção do OWID, como `United Kingdom`, `Czechia`, `North Macedonia`, `Bosnia and Herzegovina`, `Moldova`, `Turkey`, `Armenia`, `Georgia`, `Israel` e `Morocco`.
- A função `resolve_canonical_country(raw_name)` retorna o nome padronizado do país quando houver correspondência explícita; caso contrário, preserva o valor original em formato padronizado (`title()`).

## Chaves primárias e identidade temporal

### COVID-19
- Chave principal de identidade temporal: `iso_code + date`
- Justificativa: cada país possui uma única observação diária de saúde pública.

### Air Traffic Europe
- Chave principal de identidade temporal: `YEAR + FLT_DATE + APT_ICAO`
- Justificativa: cada aeroporto possui um registro por data para partidas, chegadas e operações IFR.

## Atributos derivados

### COVID-19
- `location_key`: chave textual normalizada.
- `country_name`: nome canônico harmonizado com o Eurocontrol.
- `new_cases_per_million`: novos casos por milhão de habitantes.
- `total_cases_per_million`: total acumulado de casos por milhão de habitantes.
- `new_deaths_per_million`: novos óbitos por milhão de habitantes.
- `new_cases_pct_change`: variação percentual diária de casos (com tratamento contra divisões por zero e infinitos).
- `stringency_index`: índice de severidade de restrições de mobilidade e políticas públicas (0 a 100).

### Air Traffic Europe
- `APT_ICAO_KEY`, `APT_NAME_KEY`, `STATE_NAME_KEY`: chaves normalizadas.
- `country_name`: país harmonizado com a nomenclatura do OWID.
- `TOTAL_FLIGHTS`: soma de partidas e chegadas diárias.
- `TOTAL_IFR_FLIGHTS`: soma das operações de instrumentos (IFR).
- `IFR_SHARE`: percentual de operações IFR sobre o total de voos.
- `flight_volume_pct_change`: variação diária de voos por aeroporto sem valores infinitos.
