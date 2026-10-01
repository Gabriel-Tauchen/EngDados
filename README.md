# Trabalho de Engenharia de Dados (ECOX14) da UNIFEI em 2026.2

## Data source
| Fonte | Formato | Acesso | Extraido | Link |

| Our World in Data - COVID-19 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/caesarmario/our-world-in-data-covid19-dataset |

| Air Traffic in Europe from 2016 to 2024 | CSV | token | 20/08/2026 | www.kaggle.com/datasets/samithsachidanandan/air-traffic-in-europe-from-2016-to-2024 |

## Observations

- Air-traffic from Europe are divided in 9 .csv files.

## Decisões de transformação (COVID-19)

- 1) Remoção de espaços em nomes de colunas e valores textuais: 0 registros removidos; padroniza `iso_code`, `location`, `continent` e demais campos para evitar inconsistências de merge, filtros e comparações entre arquivos.
- 2) Filtro de países fora da Europa: 274.291 linhas removidas, restando 75.794 linhas; o conjunto original contém dados globais e o projeto exige apenas registros com `continent == "Europe"`, por isso o total caiu do universo mundial para o escopo europeu.
- 3) Validação da chave temporal: 0 duplicatas detectadas para `iso_code + date`; garante que cada país tenha no máximo uma observação por dia, preservando a integridade da série temporal e evitando registros inconsistentes.
- 4) Conversão da coluna `date` para datetime: 0 linhas removidas; transforma a data em tipo temporal, permitindo ordenação, filtros por período e cálculos de evolução ao longo do tempo.

> Resumo do impacto: o dataset cru tinha 350.085 linhas; após as decisões acima, o dataset final no silver ficou com 75.794 linhas, porque o processo removeu dados fora do escopo europeu e validou a integridade temporal antes de gravar o parquet.
