# Evitável

Identifica **internações evitáveis** nos municípios do Rio Grande do Sul a partir
dos dados públicos do SUS.

Internações por condições sensíveis à atenção primária (ICSAP) são as que
poderiam ter sido evitadas com um bom atendimento no posto de saúde: diabetes,
hipertensão, asma, pneumonias bacterianas, infecções urinárias, entre outras.
Uma proporção alta de ICSAP num município indica que a atenção básica de lá
precisa de reforço.

**Objetivo:** prever quais municípios ou regiões vão ter mais internações
evitáveis, para ajudar gestores de saúde a decidir onde investir.

## Status

Fase 4: série 2015–2025 por município e região de saúde, com taxas
padronizadas por idade e sexo, e previsão para 2026. Próximo: mapa ou painel.

## Como rodar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync

# Baixa as internações do RS em 2024 (um arquivo por mês, ~10 MB cada)
uv run evitavel baixar --uf RS --ano 2024

# Ou só alguns meses, para testar
uv run evitavel baixar --uf RS --ano 2024 --meses 1

# Calcula as internações evitáveis por município (um ano ou um período)
uv run evitavel analisar --uf RS --anos 2024
uv run evitavel analisar --uf RS --anos 2015-2025

# Prevê a RME do ano seguinte (usa a série gerada acima)
uv run evitavel prever --uf RS

# Testes
uv run pytest
```

Para fechar um ano, o `analisar` também lê os arquivos do ano seguinte (veja
Limitações), então baixe os dois. A população (POPSVS) e as regiões de saúde
são baixadas sozinhas na primeira vez.

Saem duas tabelas em `reports/`, com uma linha por área e ano:
`icsap_municipios_RS_<período>.csv` e `icsap_regioes_RS_<período>.csv`
(as 30 regiões de saúde).

| Coluna | Significado |
| --- | --- |
| `internacoes` | Internações de residentes do município pagas pelo SUS |
| `internacoes_sem_parto` | Idem, sem partos normais e cesarianas |
| `icsap` | Internações evitáveis |
| `proporcao_icsap_pct` | `icsap` / `internacoes_sem_parto` |
| `taxa_icsap_10mil` | `icsap` por 10 mil habitantes (taxa bruta) |
| `icsap_esperado` | ICSAP esperadas se a área tivesse as taxas do estado em cada faixa de idade e sexo |
| `rme` | Razão de morbidade padronizada: `icsap` / `icsap_esperado` |
| `rme_ic95_inf`, `rme_ic95_sup` | Intervalo de confiança de 95% da RME |
| `taxa_padronizada_10mil` | Taxa ajustada por idade e sexo: `rme` × taxa bruta do estado |

**Como ler a RME:** 1,3 quer dizer 30% mais internações evitáveis do que o
esperado para a idade e o sexo da população; 0,8 quer dizer 20% menos. A
referência é o estado no mesmo ano. Quando `rme_ic95_inf` é maior que 1, a área
está acima do esperado com pouca chance de ser só acaso. Prefira a RME e a
taxa padronizada para comparar áreas: a taxa bruta pune municípios mais velhos.

Os arquivos lidos ficam em cache como Parquet em `data/processed/sih/`. Se o
`.dbc` original for apagado, o `analisar` usa o cache.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `src/evitavel/icsap.py` | Lista brasileira de ICSAP (19 grupos de CID-10) |
| `src/evitavel/download.py` | Download dos arquivos do SIH/SUS do FTP do DATASUS |
| `src/evitavel/process.py` | Leitura dos arquivos e resumo por município |
| `src/evitavel/populacao.py` | População por município, idade e sexo (POPSVS) |
| `src/evitavel/territorio.py` | Regiões e macrorregiões de saúde |
| `src/evitavel/padronizacao.py` | Padronização indireta por idade e sexo |
| `src/evitavel/previsao.py` | Modelo de previsão e validação |
| `src/evitavel/__init__.py` | Comandos `baixar` e `analisar` |
| `data/raw/` | Arquivos `.dbc` baixados (fora do git) |
| `data/processed/` | Cache em Parquet (fora do git) |
| `reports/` | Tabelas de resultado |
| `tests/` | Testes |

## Dados

- **SIH/SUS (arquivos RD):** uma linha por internação paga pelo SUS. Não
  identifica pacientes. Fonte: FTP público do DATASUS.
- **Municípios:** nomes pela API de localidades do IBGE.
- **População:** estimativas do Ministério da Saúde por município, sexo e
  idade (arquivos POPSVS do DATASUS, as mesmas do TabNet). Foram refeitas
  depois do Censo 2022 e formam uma série contínua de 2000 a 2025. As
  estimativas anuais do IBGE não servem para série: as de 2011–2021 vêm do
  Censo 2010 e superestimaram muitos municípios (Porto Alegre: 1,49 milhão em
  2021 contra 1,33 milhão no Censo 2022), e as de 2024 em diante corrigem a
  subcontagem do censo. O POPSVS coincide com o IBGE a partir de 2024.
- **Regiões de saúde:** base territorial do DATASUS (30 regiões e 7
  macrorregiões no RS).

## Limitações conhecidas

- Os arquivos são organizados pelo **mês de processamento** da internação,
  não pelo mês em que ela aconteceu. Por isso cada internação é contada pelo
  ano da data de internação, lendo também os arquivos do ano seguinte. Os anos
  mais recentes ainda podem ganhar internações processadas com atraso.
- Só entram **residentes do estado**. Gaúchos internados em outros estados
  ficam de fora (estão nos arquivos daqueles estados).
- Em municípios pequenos (231 têm menos de 5 mil habitantes) as taxas oscilam
  muito de um ano para o outro só por acaso. Use o intervalo de confiança da
  RME, ou a tabela por região.
- A RME compara cada área com o estado **no mesmo ano**. Ela mostra a posição
  relativa ao longo do tempo, mas não a tendência do estado: para isso, veja a
  taxa bruta do estado.
- A população POPSVS é estimativa e pode ser revista quando sair um novo
  censo ou uma nova rodada de estimativas.
- Só cobre internações pagas pelo SUS. Internações por planos de saúde ficam
  de fora.
- Partos são identificados pelo procedimento realizado (SIGTAP 03.10.01,
  parto normal, e 04.11.01, cesariana).
- A lista de CIDs em `icsap.py` segue a [Portaria SAS/MS nº 221/2008](https://bvsms.saude.gov.br/bvs/saudelegis/sas/2008/prt0221_17_04_2008.html),
  conferida com o texto publicado no site do Ministério da Saúde.

## Resultados (RS, residentes)

| Ano | Internações (sem partos) | Evitáveis (ICSAP) | % | Por 10 mil hab. | Custo das evitáveis |
| --- | --- | --- | --- | --- | --- |
| 2015 | 667.999 | 151.351 | 22,7% | 136,7 | R$ 165 mi |
| 2016 | 660.018 | 147.608 | 22,4% | 132,9 | R$ 169 mi |
| 2017 | 660.535 | 143.133 | 21,7% | 128,5 | R$ 167 mi |
| 2018 | 653.691 | 138.185 | 21,1% | 123,7 | R$ 167 mi |
| 2019 | 677.947 | 139.622 | 20,6% | 124,7 | R$ 172 mi |
| 2020 | 575.114 | 101.558 | 17,7% | 90,5 | R$ 142 mi |
| 2021 | 633.759 | 104.034 | 16,4% | 92,7 | R$ 143 mi |
| 2022 | 689.382 | 130.041 | 18,9% | 115,9 | R$ 177 mi |
| 2023 | 716.831 | 133.962 | 18,7% | 119,4 | R$ 187 mi |
| 2024 | 753.074 | 135.880 | 18,0% | 121,0 | R$ 210 mi |
| 2025 | 779.169 | 133.736 | 17,2% | 119,1 | R$ 215 mi |

Custos em valores nominais (sem correção pela inflação).

- A taxa caiu de 137 para 125 por 10 mil entre 2015 e 2019.
- Em 2020–2021 a pandemia derrubou as internações. A queda não significa que a
  atenção básica melhorou: muita gente deixou de procurar atendimento.
- De 2022 em diante a taxa ficou entre 116 e 121 por 10 mil, abaixo do nível
  de antes da pandemia.
- As causas mais comuns continuam sendo doenças cerebrovasculares, doenças
  pulmonares, insuficiência cardíaca, infecção urinária e pneumonias
  bacterianas.

### Regiões de saúde (2025, ajustado por idade e sexo)

A diferença entre regiões é grande: a que está pior tem quase três vezes a
RME da que está melhor.

| Região | Taxa padronizada (por 10 mil) | RME |
| --- | --- | --- |
| 15 Caminho das Águas | 191 | 1,61 |
| 20 Rota da Produção | 164 | 1,38 |
| 06 Vale do Paranhana e Costa Serra | 164 | 1,37 |
| 22 Pampa | 152 | 1,27 |
| 27 Jacuí Centro | 144 | 1,21 |
| … | | |
| 04 Belas Praias | 84 | 0,70 |
| 23 Caxias e Hortênsias | 81 | 0,68 |
| 26 Uva Vale | 80 | 0,67 |
| 25 Vinhedos e Basalto | 71 | 0,60 |

A região 10 (Capital e Vale do Gravataí), com 2,2 milhões de habitantes e quase
um quarto das ICSAP do estado, também fica acima do esperado (RME 1,19).

### Municípios (2025)

Entre os municípios com 20 mil habitantes ou mais, 32 ficam claramente acima
do esperado (limite inferior do IC 95% da RME acima de 1). Os de maior RME são
Encruzilhada do Sul (1,96), São Francisco de Paula (1,91), Charqueadas (1,91),
São Jerônimo (1,81) e Rosário do Sul (1,71).

A padronização muda o retrato de municípios com população jovem. Alvorada
tem taxa bruta de 164 por 10 mil, mas taxa padronizada de 188. Parobé passa
de 176 para 201.

A RME é estável de um ano para o outro: a correlação entre 2024 e 2025 é de
0,91 entre municípios e 0,97 entre regiões. Isso indica que dá para prever
quem vai ficar acima do esperado.

## Previsão para 2026

O `prever` estima a RME do ano seguinte de cada município. O modelo é uma
regressão de Poisson que usa as RMEs dos três anos anteriores (encolhidas em
direção à média do estado nos municípios pequenos), a RME da região de saúde e
a população. Detalhes em `src/evitavel/previsao.py`.

**Validação.** Para cada ano de 2023 a 2025, o modelo foi treinado só com os
anos anteriores e comparado com a regra mais simples possível: "a RME do ano
que vem é igual à deste ano" (persistência).

| Nível | Método | Erro médio na RME | Acerto dos 50 piores | Intervalo de 80% contém o real |
| --- | --- | --- | --- | --- |
| Município | Persistência | 0,108 | 72% | — |
| Município | Modelo | 0,105 | 74% | 83% |
| Região | Persistência | 0,051 | — | — |
| Região | Modelo | 0,051 | — | 81% |

"Acerto dos 50 piores" é a fração dos 50 municípios com maior RME real
(entre os com 20+ ICSAP esperadas) que o método colocou entre os 50 maiores.

- **O ganho do modelo sobre a persistência é pequeno.** Nos municípios, a
  deviance de Poisson cai cerca de 9% (6,1 contra 6,7), sobretudo porque o
  modelo não leva a sério picos de um ano só em municípios pequenos. Nas
  regiões, os dois empatam. A RME muda pouco de um ano para o outro, então o
  ano passado já é um bom previsor, e o modelo pesa basicamente a RME do
  último ano (coeficiente 0,69) e a média dos três últimos (0,26).
- **O valor prático está nos intervalos.** Eles foram calibrados na validação
  e permitem dizer quais municípios devem continuar acima do esperado com
  pouca chance de ser acaso. Nas regiões, o intervalo é alargado (fator 1,31)
  porque municípios vizinhos sobem e descem juntos.
- O modelo não sabe de mudanças que ainda não aparecem nos dados, como uma
  nova equipe de saúde da família, o fechamento de um hospital ou uma
  epidemia. Ele diz onde o problema deve continuar, não por quê.

**Maiores RMEs previstas para 2026:**

- Regiões: Caminho das Águas (1,55; intervalo de 80%: 1,43–1,66), Rota da
  Produção (1,35) e Vale do Paranhana e Costa Serra (1,34).
- Municípios com 20 mil habitantes ou mais: Encruzilhada do Sul (1,92;
  1,59–2,26), Charqueadas (1,87), São Jerônimo (1,77), São Francisco de Paula
  (1,77) e Parobé (1,66).

As tabelas completas ficam em `reports/previsao_municipios_RS_2026.csv`,
`reports/previsao_regioes_RS_2026.csv` e `reports/previsao_validacao_RS.csv`.

## Próximos passos

1. ~~Baixar a população dos municípios (IBGE) e calcular taxas por 10 mil habitantes~~
2. ~~Montar uma série histórica de 2015 em diante~~
3. ~~Padronizar as taxas por idade e agrupar por região de saúde~~
4. ~~Treinar um primeiro modelo de previsão por município e região de saúde~~
5. Fazer um mapa ou painel para mostrar os resultados
6. Apresentar para um grupo de pesquisa em saúde pública ou para o COSEMS-RS
