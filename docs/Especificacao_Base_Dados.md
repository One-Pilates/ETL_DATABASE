# OnePilates – Especificação de Base de Dados

**Grupo 8 - InfiniteLoop**  
**Versão 1.6 (gold de quatro grupos) – 15/10/2026**

## Especificação de Base de Dados

**Projeto de Pesquisa e Inovação**

| Campo | Valor |
|---|---|
| **Grupo** | 8 - InfiniteLoop |
| **Integrantes** | Andrei Scafi de Vasconcelos, Guilherme Queiroz de Lima, Gustavo Castro Andrade, Harison Rios de Miranda, Isabella de Sousa Viana, Pedro da Costa Ferreira Gandin |
| **Projeto** | OnePilates |
| **Base especificada** | AACT / ClinicalTrials.gov, camada gold de pilates, fisioterapia, mobilidade e força, com resumos PubMed |
| **Versão do documento** | 1.6 |
| **Data** | 15/10/2026 |
| **Onde está gravada** | DuckDB `data/clinical_trials.duckdb` (schemas `raw`, `silver`, `gold`) e cópia MySQL `estudos_aula` |

A versão 1.5 descrevia outro ouro: CSV `trials_pilates`, n = 652, promovido por `primary_outcomes`. Essa tabela não é a base atual. O dicionário vigente é `gold.estudos` e `gold.referencias`, detalhado também em [gold_estudos.md](gold_estudos.md) e [comparacao_silver_gold.md](comparacao_silver_gold.md).

---

## Seção 0 — Identificação e justificativa da base

### 0.1 Origem da base

| Item | Especificação |
|---|---|
| **Nome da base** | AACT Database (ClinicalTrials.gov) |
| **Origem** | Externa |
| **Sistema ou instituição de origem** | Clinical Trials Transformation Initiative (CTTI) / U.S. National Library of Medicine (NLM) |
| **Link** | https://aact.ctti-clinicaltrials.org/downloads e https://clinicaltrials.gov |
| **Formato recebido** | Arquivos texto delimitados por pipe em `base_dados/` |
| **Recorte da gold** | Ensaio com `overall_status = COMPLETED` cujo nome ou descrição de alguma intervenção contém termo de pilates, fisioterapia, mobilidade ou força. Título, resumo, MeSH e critérios de elegibilidade não decidem a entrada. |

Contagens da gold nesta carga: 12.158 estudos. Pilates 309, fisioterapia 3.848, mobilidade 5.811, força 5.994. A soma passa de 12.158 porque um estudo pode cair em mais de um grupo. Raw e silver permanecem com os 602.514 ensaios do dump.

### 0.2 Por que esta base

A gold responde quais ensaios concluídos testaram pilates, fisioterapia, mobilidade ou força, e qual resumo de artigo está ligado a esse ensaio. O professor descreve a condição da aula e a aplicação devolve até cinco estudos, cada um com título, parágrafo e link. O uso na aplicação está em [manual_ia_aplicacao.md](manual_ia_aplicacao.md) e [referencias_para_a_ia.md](referencias_para_a_ia.md).

O grão é o ensaio registrado, não o aluno e não a aula. A base não prescreve treino.

### 0.3 Limitações conhecidas

- Não traz o texto completo do artigo nem dados individuais de pacientes. O enriquecimento é o resumo (abstract) obtido pelo PMID.
- Só entram estudos registrados no ClinicalTrials.gov. PEDro, SciELO e LILACS sem NCT ficam de fora. O cruzamento PEDro da versão 1.5 não faz parte deste pipeline.
- O índice de busca usado pela IA está em inglês (título, condição, MeSH e nome da intervenção). Prompt em português precisa ser reduzido a termos clínicos em inglês antes da procedure.
- `were_results_reported` diz se o resultado foi postado no registro. Não é o mesmo que existir artigo. O artigo fica em `gold.referencias`.
- 1.105 referências com `busca_status = ok` não têm texto de resumo. 2.606 citações não têm PMID. 52 PMIDs não foram encontrados.
- Não substitui revisão sistemática nem avaliação do aluno.

---

## Seção 1 — Contrato de Interface

| Item | Especificação | D / V |
|---|---|---|
| **Arquivos de origem** | `base_dados/*.txt`, um arquivo por tabela AACT | V |
| **Encoding** | UTF-8 | V |
| **Delimitador** | Pipe (`\|`) | V |
| **Qualificador de texto** | Aspas duplas | V |
| **Cabeçalho** | Primeira linha | V |
| **Datas na origem** | Texto; na silver e na gold, `DATE` quando o parse ISO funciona | V |
| **Decimal** | Ponto | V |
| **Volumetria desta carga** | Raw e silver: 602.514 estudos. Gold: 12.158 estudos e 33.623 referências. MySQL repete esses recortes de consulta. | V |
| **Banco analítico** | DuckDB local | D |
| **Banco da aplicação** | MySQL 8, schema aplicado por `sql/schema_mysql.sql`, charset `utf8mb4` | D |
| **Atualização** | Carga cheia pelos scripts em `pipeline/`. O site AACT atualiza com mais frequência do que este snapshot. | D |

### 1.1 Inconsistências encontradas no arquivo

- Datas de origem às vezes vêm como "Month Year". O que não vira `DATE` fica nulo na silver; o texto original não segue para a gold.
- `phase = NA` é valor do registro (fase não se aplica), frequente em exercício. Não é o mesmo que `phase` nulo.
- A AACT tem dezenas de tabelas. Esta carga usa studies e as tabelas 1:1 e 1:N ligadas por `nct_id` que alimentam `raw.estudos` (condições, intervenções, patrocinadores, países, MeSH, resumo, desenho e elegibilidade). `study_references.txt` entra só na gold.

---

## Seção 2 — Dicionário de Dados

### 2.0 Granularidade (grão)

Uma linha de `gold.estudos` é um ensaio (`nct_id`). Listas repetidas ficam na mesma linha. Uma linha de `gold.referencias` é uma citação desse ensaio.

| Tabela | Onde | Grão | Chave |
|---|---|---|---|
| `raw.estudos` | DuckDB | Um ensaio do dump, texto como veio | `nct_id` |
| `silver.estudos` | DuckDB | O mesmo ensaio, tipado. 133 colunas. Não descarta linha | `nct_id` |
| `silver.qualidade` | DuckDB | Um alerta de uma regra, um ensaio pode ter vários | `nct_id` + regra |
| `gold.estudos` | DuckDB | Um ensaio concluído dos quatro grupos. 24 colunas | `nct_id` |
| `gold.referencias` | DuckDB | Uma citação de um ensaio da gold | `nct_id` + citação |
| `estudo` e filhas | MySQL | O mesmo grão da gold, com listas em tabelas filhas | `nct_id` |
| `referencia` | MySQL | A mesma citação | `nct_id` + `pmid` quando existe |

No MySQL as listas viram `estudo_grupo`, `estudo_condicao`, `estudo_intervencao`, `estudo_mesh`. País e patrocinador não vão para o MySQL. Somar `enrollment` nessas filhas conta o mesmo ensaio várias vezes.

### 2.1 Oito papéis da Aula 4 (âncora)

| Papel | Campo na gold | Tipo | Obrigatório | Regra | Exemplo |
|---|---|---|---|---|---|
| 1. Chave primária | `nct_id` | VARCHAR | Sim | Único. Formato `NCT` + 8 dígitos | NCT00000399 |
| 2. Data | `completion_date` | DATE | Não | Conclusão do ensaio. `start_date` e `primary_completion_date` também são DATE | 2024-11-26 |
| 3. Categórico fechado | `overall_status` | VARCHAR | Sim | Na gold, sempre `COMPLETED` | COMPLETED |
| 4. Numérico | `enrollment` | BIGINT | Não | Participantes inscritos. Nulo em 17 estudos (0,1%) | 54 |
| 5. Texto a comparar | `conditions.name_normalized` | texto dentro da lista | Não | Minúsculas, sem ponto final, espaços repetidos reduzidos | parkinson disease |
| 6. Cruzamento | `nct_id` e `pmid` | VARCHAR | `nct_id` sim; `pmid` não | Liga o ensaio à citação PubMed | 33612123 |
| 7. Grupo do ensaio | `termos_encontrados` | VARCHAR[] | Sim | `pilates`, `fisioterapia`, `mobilidade`, `forca`. Pelo menos um | ['fisioterapia'] |
| 8. Fase | `phase` | VARCHAR | Não | `NA`, PHASE1–4, EARLY_PHASE1 ou combinação com `/`. Nulo em 839 (6,9%). `NA` preenchido é sentinela de "não se aplica", não nulo | NA |

### 2.2 Decisão de discretização

`enrollment` permanece inteiro na gold. A faixa abaixo é regra de leitura, não coluna gravada.

| Faixa | Rótulo |
|---|---|
| 1–20 | Piloto / muito pequeno |
| 21–50 | Pequeno |
| 51–150 | Médio |
| 151–500 | Grande |
| > 500 | Muito grande |
| 0 ou nulo | Indeterminado |

### 2.3 Decisão de cruzamento

| Item | Especificação |
|---|---|
| **Base cruzada** | PubMed, pelo PMID que já vem em `study_references.txt` |
| **Tipo** | Exato: `nct_id` do ensaio com a citação, e `pmid` com o artigo |
| **O que é gravado** | `gold.referencias`: `pmid`, `reference_type`, `citation`, `titulo`, `periodico`, `ano`, `resumo`, `busca_status` |
| **Status da busca** | `ok` 30.965, `sem_pmid` 2.606, `nao_encontrado` 52 |
| **Fora desta fase** | PEDro, fuzzy por título, texto completo do artigo |

`reference_type` nesta carga: `BACKGROUND` 23.922, `DERIVED` 5.203, `RESULT` 4.498. A ficha da IA prefere `RESULT` com resumo.

### 2.4 Canonicalização

Feito na silver e copiado para a gold:

1. Texto vazio vira nulo. Os tokens `NA` e `NONE` não são apagados.
2. `conditions.name_normalized`: minúsculas, sem ponto final, espaços colapsados.
3. `mesh_terms.mesh_term_normalized`: minúsculas, espaços colapsados.
4. Idade em anos (`minimum_age_years`, `maximum_age_years`) a partir do número e da unidade.
5. `termos_encontrados` marca o grupo pelo texto da intervenção, sem acento na comparação e em minúsculas.

Não há mapa DeCS gravado nesta carga. O nome original continua em `conditions.name` e `mesh_terms.mesh_term`.

### 2.5 Dicionário — `gold.estudos`

n = 12.158. Nulos contados nesta carga. Lista vazia (`[]`) não é nulo.

| Nome | Tipo | Regra | Aceita nulo | Qtd | % |
|---|---|---|---|---:|---:|
| nct_id | VARCHAR | PK | Não | 0 | 0,0 |
| brief_title | VARCHAR | Título curto | Não | 0 | 0,0 |
| official_title | VARCHAR | Título do protocolo | Sim | 98 | 0,8 |
| brief_summary | VARCHAR | Resumo do registro, não o abstract | Não | 0 | 0,0 |
| study_type | VARCHAR | INTERVENTIONAL 11.321; OBSERVATIONAL 837 | Não | 0 | 0,0 |
| phase | VARCHAR | Texto único da fase. `NA` é valor | Sim | 839 | 6,9 |
| phases | VARCHAR[] | Fase partida em `/`, ordem fixa | Lista vazia quando `phase` é nulo | 839 vazias | 6,9 |
| overall_status | VARCHAR | Sempre COMPLETED | Não | 0 | 0,0 |
| start_date | DATE | Início | Sim | 8 | 0,1 |
| completion_date | DATE | Conclusão | Sim | 58 | 0,5 |
| primary_completion_date | DATE | Conclusão do desfecho primário | Sim | 56 | 0,5 |
| enrollment | BIGINT | Participantes | Sim | 17 | 0,1 |
| minimum_age_years | DOUBLE | Idade mínima em anos | Sim | 436 | 3,6 |
| maximum_age_years | DOUBLE | Idade máxima em anos. Nulo costuma ser ausência de teto | Sim | 3.785 | 31,1 |
| gender | VARCHAR | ALL 10.140; FEMALE 1.410; MALE 602 | Sim | 6 | 0,0 |
| conditions | lista de struct | `name`, `name_normalized` | Lista vazia não ocorre nesta carga | 0 | 0,0 |
| interventions | lista de struct | `intervention_type`, `name`, `description`. É o texto do filtro | Lista vazia não ocorre | 0 | 0,0 |
| mesh_terms | lista de struct | `mesh_term`, `mesh_type`, `mesh_term_normalized` | Lista pode ser vazia | 2.421 vazias | 19,9 |
| countries_current | lista de struct | `name`, `removed`. País removido já ficou de fora | Lista pode ser vazia | 536 vazias | 4,4 |
| lead_sponsors | lista de struct | `agency_class`, `lead_or_collaborator` = LEAD, `name` | Lista vazia não ocorre | 0 | 0,0 |
| were_results_reported | BOOLEAN | true 1.110; false 11.048 | Não | 0 | 0,0 |
| termos_encontrados | VARCHAR[] | Um ou mais dos quatro grupos | Não | 0 | 0,0 |
| url | VARCHAR | `https://clinicaltrials.gov/study/` + `nct_id` | Não | 0 | 0,0 |
| _gold_at | TIMESTAMP WITH TIME ZONE | Hora da gravação da gold | Não | 0 | 0,0 |

#### 2.5.1 `gold.referencias`

n = 33.623. Uma citação por linha.

| Nome | Tipo | Regra |
|---|---|---|
| nct_id | VARCHAR | Ensaio que está em `gold.estudos` |
| pmid | VARCHAR | Nulo quando `busca_status = sem_pmid` |
| reference_type | VARCHAR | BACKGROUND, DERIVED ou RESULT |
| citation | VARCHAR | Citação como no arquivo de referências |
| titulo | VARCHAR | Título do artigo, quando a busca PubMed deu certo |
| periodico | VARCHAR | Periódico |
| ano | INTEGER | Ano de publicação |
| resumo | VARCHAR | Abstract. Pode faltar mesmo com `busca_status = ok` |
| busca_status | VARCHAR | `ok`, `sem_pmid` ou `nao_encontrado` |

#### 2.5.2 O que a silver tem e a gold não copia

112 colunas ficam só em `silver.estudos`: datas administrativas, desenho (alocação, mascaramento, propósito), idade no texto original, listas completas `sponsors` e `countries`, e indicadores `tem_*`. A lista está em [comparacao_silver_gold.md](comparacao_silver_gold.md).

### 2.6 Nulos disfarçados e sentinelas

| Valor | Campo | Tratamento nesta carga |
|---|---|---|
| texto vazio | campos de texto na silver | Vira nulo |
| `NA` e `NONE` como token | vários códigos | Permanecem. Não são apagados |
| `phase = NA` | `phase` | Valor real: fase não se aplica. 10.035 estudos |
| `phase` nulo | `phase` | Ausência. 839 estudos. `phases` fica `[]` |
| `maximum_age_years` nulo | idade | Em geral o registro não declarou teto |
| `busca_status = sem_pmid` | referência | Citação sem artigo PubMed. Não imputar PMID |
| `busca_status = nao_encontrado` | referência | PMID consultado e não retornado |

### 2.7 Decisões de tratamento

| Tema | Decisão |
|---|---|
| Estudos que não são pilates, fisioterapia, mobilidade ou força | Ficam na silver. Não entram na gold |
| Status diferente de COMPLETED | Fica na silver. Não entra na gold |
| `enrollment` extremo | Mantido. A silver registra alerta; a gold não descarta a linha por isso |
| `phase = NA` | Mantido como categoria. Não imputar PHASE |
| Resumo PubMed ausente | A ficha da IA usa outro resumo `ok` ou, sem artigo, o `brief_summary` |
| PEDro e mapa DeCS da versão 1.5 | Fora desta carga. Não há `pedro_id` nem `condition_canonical` |
| Busca da IA | Termos em inglês. O prompt em português é traduzido antes da procedure |

---

## Seção 3 — Especificação do Pipeline

| Item | Especificação |
|---|---|
| **Origem** | Arquivos em `base_dados/` extraídos do snapshot AACT |
| **Destino analítico** | `data/clinical_trials.duckdb` |
| **Destino da aplicação** | MySQL `estudos_aula`, procedure `buscar_estudos_para_aula` |
| **Tipo de carga** | Cheia, por script local |
| **Idempotência** | `build_gold.py` recria `gold.estudos` e `gold.referencias` e devolve os resumos PubMed já gravados. `load_mysql.py` recria as tabelas MySQL e reinsere a gold |
| **Orquestrador** | Não há Airflow nesta versão. A execução é manual: `ingest_raw.py`, `build_silver.py`, `build_gold.py`, e `load_mysql.py` quando a aplicação precisa da cópia |
| **Rejeição** | A silver não descarta ensaio. O alerta vai para `silver.qualidade`. A gold exclui pelo filtro de status e de grupo, sem tabela de rejeição |

### 3.1 Regras de validação

| Camada | Regra | Severidade |
|---|---|---|
| Estrutural | `build_gold.py` exige o DuckDB e `base_dados/study_references.txt` | Bloqueante |
| Domínio | Toda linha da gold tem `overall_status = COMPLETED` | Bloqueante. O script termina com erro se falhar |
| Integridade | Todo `nct_id` da gold existe na silver. `termos_encontrados` tem ao menos um dos quatro grupos | Bloqueante |
| Negócio | O grupo sai do nome ou da descrição da intervenção, não do título nem do MeSH | Filtro da gold |
| Carga MySQL | `load_mysql.py` confere 12.158 estudos e as contagens 309, 3.848, 5.811 e 5.994 | Bloqueante se divergir |
| Aplicação | A IA só lê o retorno da procedure: título, resumo e link. Não escreve SQL | Guardrail da aplicação |

---

## Seção 4 — Pendências e riscos

| Pendência ou risco | Impacto | Como tratar |
|---|---|---|
| Índice de busca em inglês | Prompt em português não acha "pescoço" nem "idosa" | Traduzir o tema para poucos termos clínicos em inglês antes da procedure. Manual em [manual_ia_aplicacao.md](manual_ia_aplicacao.md) |
| Resumo `RESULT` às vezes descreve outro artigo citado no registro | A ficha pode não corresponder ao protocolo do `titulo` | Mostrar título e link juntos. Não inferir efeito que o parágrafo não traz |
| Sem DeCS e sem PEDro | Condição em português e escore metodológico não estão na gold | Fora desta versão |
| Snapshot AACT envelhece | Ensaios novos não aparecem até uma carga cheia | Repetir raw, silver, gold e, se a aplicação estiver no ar, `load_mysql.py` |
| Mudança de schema AACT | Quebra a ingestão | Conferir o cabeçalho dos `.txt` antes de rerodar `ingest_raw.py` |

---

## Controle de versões

| Versão | Data | Autor | O que mudou |
|---|---|---|---|
| 1.6 | 15/10/2026 | Grupo 8 – InfiniteLoop | Especificação alinhada à gold implementada: 12.158 estudos concluídos de pilates, fisioterapia, mobilidade e força; `gold.referencias` com resumo PubMed; cópia MySQL e procedure da IA. Substitui o ouro `trials_pilates` n = 652 |
| 1.5 | 06/10/2026 | Grupo 8 – InfiniteLoop | Dicionário finalizado: nulos com qtd/%, fórmulas dos derivados, nulos disfarçados (`NA_EXTRA`) e decisões de tratamento da EDA |
| 1.4 | 06/10/2026 | Grupo 8 – InfiniteLoop | Nulos e notas da EDA no ouro n=652; cinco dimensões por campo |
| 1.3 | 21/09/2026 | Grupo 8 – InfiniteLoop | Cruzamento exato PubMed/PEDro no ouro (`pubmed_id`, `pedro_id`, `pedro_score`, `status_cruzamento`) |
| 1.2 | 21/09/2026 | Grupo 8 – InfiniteLoop | Ouro exige `primary_outcomes`; `secondary_outcomes` pode ser nulo ou vazio |
| 1.1 | 15/09/2026 | Grupo 8 – InfiniteLoop | Dicionário da Aula 5: grão, oito papéis âncora e colunas completas do ouro |
| 1.0 | 25/08/2026 | Grupo 8 – InfiniteLoop | Versão inicial – especificação da base AACT com recorte Pilates para o OnePilates |
