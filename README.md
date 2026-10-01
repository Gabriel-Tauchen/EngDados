# Trabalho de Engenharia de Dados (ECOX14) da UNIFEI em 2026.2

## Fontes de dados

| Fonte | Formato | Acesso | Extraído em | Link |
| --- | --- | --- | --- | --- |
| Our World in Data - COVID-19 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/caesarmario/our-world-in-data-covid19-dataset |
| Air Traffic in Europe from 2016 to 2024 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/samithsachidanandan/air-traffic-in-europe-from-2016-to-2024 |

## Observações gerais

- O dataset de COVID-19 foi armazenado em bronze em `data/bronze/covid19`.
- O dataset de tráfego aéreo está em `data/bronze/air-traffic-EU` e foi dividido em arquivos por ano.
- O projeto usa a camada bronze como versão original e a camada silver como versão tratada para análise.

## Decisões de transformação (COVID-19)

- 1) Remoção de espaços em nomes de colunas e valores textuais: 0 registros removidos; padroniza `iso_code`, `location`, `continent` e demais campos para evitar inconsistências de merge, filtros e comparações entre arquivos.
- 2) Filtro de países fora da Europa: 274.291 linhas removidas, restando 75.794 linhas; o conjunto original contém dados globais e o projeto exige apenas registros com `continent == "Europe"`, por isso o total caiu do universo mundial para o escopo europeu.
- 3) Validação da chave temporal: 0 duplicatas detectadas para `iso_code + date`; garante que cada país tenha no máximo uma observação por dia, preservando a integridade da série temporal e evitando registros inconsistentes.
- 4) Conversão da coluna `date` para datetime: 0 linhas removidas; transforma a data em tipo temporal, permitindo ordenação, filtros por período e cálculos de evolução ao longo do tempo.
- 5) Persistência em parquet na silver: 1 arquivo gerado; a camada silver foi criada em formato parquet para reduzir custo de leitura e manter a tabela analítica pronta para consumo.

> Resumo do impacto: o dataset cru tinha 350.085 linhas; após as decisões acima, o dataset final no silver ficou com 75.794 linhas, porque o processo removeu dados fora do escopo europeu e validou a integridade temporal antes de gravar o parquet.

## Decisões de transformação (Air Traffic Europe)

- 1) Seleção dos arquivos mais recentes por ano: 6 arquivos usados (2019 a 2024); o projeto considera apenas os arquivos de extração mais recentes de cada ano e ignora versões antigas para evitar duplicidade na camada bronze.
- 2) Filtro de escopo 2019+ : 0 linhas removidas; o objetivo foi manter apenas o período relevante para a análise atual, evitando dados antigos que não fazem parte do estudo principal.
- 3) Limpeza de colunas e padronização de textos: 0 registros removidos; ajusta nomes e espaços em campos como aeroporto, estado e mês, reduzindo problemas de merge e comparações entre arquivos.
- 4) Seleção das colunas operacionais: 13 colunas mantidas; preserva identificadores de data, aeroporto, estado e métricas de voos sem excluir informação útil para análise de demanda e operação.
- 5) Conversão de tipos: `YEAR` e `MONTH_NUM` convertidos para inteiros; `FLT_DATE` convertido para datetime; campos de voos convertidos para numéricos e faltantes tratados como zero para manter consistência operacional.
- 6) Validação da série temporal por aeroporto e data: 1 linha duplicada removida; a regra garante que não existam registros idênticos repetidos na mesma data e aeroporto, evitando sobrecontagem artificial no total.

> Resumo do impacto: o conjunto bronzedo de tráfego aéreo começou com 677.190 linhas em 2019-2024; após a limpeza, seleção, padronização e remoção de duplicatas, o silver final ficou com 677.189 linhas, preservando a série temporal e eliminando a repetição exata de um registro.

## Estrutura geral do projeto

- `data/bronze/` = dados originais, sem transformação
- `data/silver/` = dados tratados, em parquet, prontos para análise
- `reports/` = relatórios de profiling
- `src/` = scripts de ingestão e transformação

## Execução do pipeline até a camada silver

No PowerShell, a partir da pasta raiz do projeto e com o ambiente virtual ativado, execute os comandos nesta ordem:

```powershell
python -m pip install -r requirements.txt

python src/ingest_covid19.py
python src/ingest_air-traffic-EU.py

python src/transform_covid_data.py
python src/transform_flight_data.py
```

Os scripts de ingestão baixam os CSVs do Kaggle e os copiam para `data/bronze/`. Em seguida, os scripts de transformação tratam os dados e geram arquivos Parquet em `data/silver/covid19/` e `data/silver/air-traffic-EU/`.

> A ingestão requer acesso ao Kaggle configurado. Se os CSVs brutos já estiverem atualizados na camada bronze, pule os dois comandos `ingest` e execute apenas os comandos de transformação. A instalação das dependências pode ser omitida quando elas já estiverem instaladas no ambiente virtual.

## Mapeamento canônico de países

Para manter a compatibilidade entre o dataset de tráfego aéreo (Eurocontrol) e o dataset de COVID-19 (OWID), foi definido um dicionário de padronização em `src/country_mapping.py`.

- A chave de normalização usa texto em minúsculas, sem acentos e sem espaços extras.
- Os nomes canônicos seguem a convenção do OWID, como `United Kingdom`, `Czechia`, `North Macedonia`, `Bosnia and Herzegovina`, `Moldova` e `Turkey`.
- A função `resolve_canonical_country(raw_name)` retorna o nome padrô nato do país quando houver correspondência explícita; caso contrário, preserva o valor original em formato padronizado.

## Chaves primárias e identidade temporal

### COVID-19
- Chave principal de identidade temporal: `iso_code + date`
- Justificativa: cada país deve ter, no máximo, uma observação por dia para manter a integridade da série temporal e evitar duplicatas causadas por reprocessamento ou reaproveitamento de arquivos.

### Air Traffic Europe
- Chave principal de identidade temporal: `YEAR + FLT_DATE + APT_ICAO`
- Justificativa: cada aeroporto pode registrar múltiplos registros em um mesmo dia, mas o identificador de aeroporto + data define a unidade de observação para a série operacional.

## Harmonização de nomes de país

Para permitir a comparação entre a série de voos europeus e a série de casos de COVID, foi criado o módulo [src/country_mapping.py](src/country_mapping.py) com a função `resolve_canonical_country()`.

- Esse passo é aplicado em ambas as transformações antes do merge analítico.
- A coluna `country_name` padroniza nomes divergentes como `Czech Republic` e `Czechia`, `Turkey` e `Turkiye`, `Republic of North Macedonia` e `North Macedonia`.
- A padronização reduz erros de join e garante que a análise comparativa use a mesma identidade geográfica em todos os datasets.

## Atributos derivados

### COVID-19
- `location_key`: chave textual normalizada para o nome do país, usada em junções e comparações entre registros.
- `new_cases_per_million`: casos novos por milhão de habitantes.
- `total_cases_per_million`: casos acumulados por milhão de habitantes.
- `new_deaths_per_million`: mortes novas por milhão de habitantes.
- `new_cases_pct_change`: variação percentual diária de casos novos por país.

### Air Traffic Europe
- `APT_ICAO_KEY`: chave textual normalizada para o código do aeroporto.
- `APT_NAME_KEY`: chave textual normalizada para o nome do aeroporto.
- `STATE_NAME_KEY`: chave textual normalizada para o nome do estado/país.
- `TOTAL_FLIGHTS`: soma de partidas e chegadas diárias.
- `TOTAL_IFR_FLIGHTS`: soma das operações IFR de partida e chegada.
- `IFR_SHARE`: proporção percentual de operações IFR no total de voos.
- `flight_volume_pct_change`: variação percentual do volume diário de voos por aeroporto.

## Decisões de limpeza e padronização

- 1) Remoção de espaços em colunas e strings: elimina espaçamento inconsistente em nomes de colunas e valores textuais antes da análise.
- 2) Filtro por país/escopo: mantém apenas registros relevantes para Europa e para o período de interesse (2019+ no caso do tráfego aéreo).
- 3) Padronização de texto e país: normaliza letras, acentos e variações de nomenclatura para permitir comparações entre fontes e reduzir ruídos de merge.
- 4) Conversão de tipos: datas em `datetime` e campos numéricos em tipos analíticos adequados.
- 5) Validação de duplicatas: remove linhas idênticas e valida integridade temporal por chave principal.
- 6) Persistência em parquet: grava os dados em formato eficiente para análise e consumo da camada silver.

## Observações finais

- O projeto não exige uma terceira fonte de dados; o contexto analítico é derivado dos dois datasets já fornecidos.
- A camada silver foi construída para conter dados limpos, consistentes e prontos para benchmarking temporal e comparativo entre saúde pública e operação aeroportuária.
