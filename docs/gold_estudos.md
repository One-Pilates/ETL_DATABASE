# Tabela `gold.estudos`

Uma linha por ensaio clínico concluído cuja intervenção testada é pilates, fisioterapia, mobilidade ou força. A tabela está no DuckDB `data/clinical_trials.duckdb`, schema `gold`. Hoje são **12.158** estudos.

O estudo entra se `overall_status` é `COMPLETED` e o nome ou a descrição de alguma intervenção contém um termo de pelo menos um destes grupos. Título, resumo, MeSH e critérios de elegibilidade não decidem a entrada. Um estudo pode cair em mais de um grupo, então a soma das contagens passa de 12.158.

| Grupo | Estudos | O que a intervenção precisa mencionar |
|---|---:|---|
| pilates | 309 | pilates |
| fisioterapia | 3.848 | physiotherap, physical therapy, fisioterapia |
| mobilidade | 5.811 | mobility, mobilidade, mobilization, mobilisation, mobilização, range of motion, amplitude de movimento, stretching, alongamento, flexibility, flexibilidade, exercise therapy, therapeutic exercise, exercício terapêutico, exercicio terapeutico |
| forca | 5.994 | strength, resistance training, weight training, weightlifting, fortalecimento, treino de força |

A busca ignora maiúsculas e acentos do jeito que o termo está escrito acima. `physiotherap` pega physiotherapy e physiotherapist.

As colunas vêm de `silver.estudos`, exceto `termos_encontrados`, `url` e `_gold_at`, que nascem na gold. Listas vazias ficam `[]`, não nulas. Texto que não coube no tipo (data, número, booleano) fica nulo.

## Colunas

### `nct_id`

Identificador do ensaio no ClinicalTrials.gov, por exemplo `NCT00000399`. É a chave da linha. Não se repete.

### `brief_title`

Título curto publicado no registro. É o nome que aparece na busca do ClinicalTrials.gov.

### `official_title`

Título científico completo do protocolo. Pode ser bem mais longo que o título curto e pode estar vazio.

### `brief_summary`

Resumo do ensaio escrito por quem registrou o estudo. Descreve o objetivo e o desenho. Não é o resumo de um artigo da PubMed. Esse texto fica em `gold.referencias.resumo`.

### `study_type`

Tipo do estudo, em maiúsculas.

| Valor | Estudos |
|---|---:|
| INTERVENTIONAL | 11.321 |
| OBSERVATIONAL | 837 |

Intervencional testa uma intervenção. Observacional acompanha pessoas sem atribuir a intervenção como parte do protocolo.

### `phase`

Fase do ensaio como veio no registro, em um único texto. Estudos de exercício e comportamento costumam ser `NA` (não se aplica). Observacionais em geral não têm fase.

| Valor | Estudos |
|---|---:|
| NA | 10.035 |
| vazio | 839 |
| PHASE1 | 350 |
| PHASE2 | 343 |
| PHASE3 | 239 |
| PHASE4 | 163 |
| PHASE1/PHASE2 | 83 |
| PHASE2/PHASE3 | 68 |
| EARLY_PHASE1 | 38 |

### `phases`

A mesma fase, partida em lista quando o registro junta duas fases com `/`. A ordem é fixa: `EARLY_PHASE1`, `PHASE1`, `PHASE2`, `PHASE3`, `PHASE4`, `NA`. Um `PHASE1/PHASE2` vira `['PHASE1', 'PHASE2']`. Se `phase` está vazio, a lista é `[]`.

### `overall_status`

Situação do ensaio. Nesta tabela o valor é sempre `COMPLETED`: o estudo foi concluído.

### `start_date`

Data de início. Tipo `DATE` (`AAAA-MM-DD`). Fica nula quando o texto original não era uma data reconhecível.

### `completion_date`

Data de conclusão do estudo inteiro. Mesma regra de data da coluna anterior.

### `primary_completion_date`

Data em que o desfecho primário foi coletado no último participante. Pode ser anterior a `completion_date`, porque o estudo às vezes continua para desfechos secundários ou acompanhamento.

### `enrollment`

Número de participantes inscritos. Número inteiro. Pode estar vazio. O registro não distingue aqui se o número é o planejado ou o real.

### `minimum_age_years`

Idade mínima de inclusão, em anos. Um critério de 6 meses vira `0,5`. A conta usa 12 meses, 52,1775 semanas ou 365,25 dias por ano. Fica nula se a idade ou a unidade não vieram no registro.

### `maximum_age_years`

Idade máxima de inclusão, na mesma unidade. Nula quando o estudo não declara teto, o que é comum (“18 anos ou mais”).

### `gender`

Sexo elegível, como o registro classifica.

| Valor | Estudos |
|---|---:|
| ALL | 10.140 |
| FEMALE | 1.410 |
| MALE | 602 |
| vazio | 6 |

### `conditions`

Lista de condições de saúde do ensaio. Cada item tem dois campos.

| Campo | Significado |
|---|---|
| `name` | Nome da condição como foi registrado, por exemplo `Parkinson Disease`. |
| `name_normalized` | O mesmo nome em minúsculas, sem ponto final e com espaços repetidos reduzidos a um. Serve para agrupar grafias parecidas. |

### `interventions`

Lista do que o ensaio testou ou observou. É a lista usada para decidir se o estudo entra na gold. Cada item tem três campos.

| Campo | Significado |
|---|---|
| `intervention_type` | Tipo em maiúsculas, como `BEHAVIORAL`, `OTHER`, `DEVICE` ou `DRUG`. |
| `name` | Nome curto da intervenção. |
| `description` | Texto livre do que foi feito. Quebras de linha do registro original são preservadas. |

### `mesh_terms`

Lista de termos MeSH ligados à condição. MeSH é o vocabulário controlado da National Library of Medicine. Cada item tem três campos.

| Campo | Significado |
|---|---|
| `mesh_term` | Termo oficial, por exemplo `Parkinsonian Disorders`. |
| `mesh_type` | Papel do termo na árvore MeSH, como `mesh-list` (termo direto) ou `mesh-ancestor` (termo mais amplo). |
| `mesh_term_normalized` | O termo em minúsculas, sem espaços sobrando. |

### `countries_current`

Lista de países em que o estudo tem centro ativo. Países marcados como removidos no registro ficam de fora. Cada item tem dois campos.

| Campo | Significado |
|---|---|
| `name` | Nome do país em inglês, como vem do ClinicalTrials.gov. |
| `removed` | `false` quando o país continua no estudo. Pode ser nulo se o registro não disse. `true` não aparece, porque esses países já foram filtrados. |

### `lead_sponsors`

Lista de patrocinadores responsáveis pelo estudo. Colaboradores ficam de fora. Cada item tem três campos.

| Campo | Significado |
|---|---|
| `agency_class` | Tipo da instituição em maiúsculas, como `OTHER`, `INDUSTRY`, `NIH` ou `FED`. |
| `lead_or_collaborator` | Sempre `LEAD` nesta lista. |
| `name` | Nome da instituição. |

### `were_results_reported`

`true` quando o registro informa que os resultados foram publicados no ClinicalTrials.gov. `false` quando não foram. Na gold, 1.110 estudos estão com `true` e 11.048 com `false`. Isso não diz se existe artigo: a citação fica em `gold.referencias`.

### `termos_encontrados`

Lista dos grupos que fizeram o estudo entrar. Os valores possíveis são `pilates`, `fisioterapia`, `mobilidade` e `forca`. A lista tem pelo menos um. A ordem segue a definição dos grupos: mobilidade, força, fisioterapia, pilates.

### `url`

Endereço do estudo no ClinicalTrials.gov: `https://clinicaltrials.gov/study/` seguido do `nct_id`.

### `_gold_at`

Data e hora em que esta versão da tabela foi gravada, com fuso horário. Não faz parte do ensaio. Serve para saber qual carga gerou a linha.

## `gold.referencias`

Tabela irmã, no mesmo schema. Uma linha por citação dos estudos que continuam em `gold.estudos`. Hoje são **33.623** referências. A ligação é `nct_id`. Um estudo pode ter várias citações, e uma citação sem PMID também entra.

| Coluna | Significado |
|---|---|
| `nct_id` | Estudo ao qual a citação pertence. Existe em `gold.estudos`. |
| `pmid` | Identificador PubMed. Nulo quando a citação não tem PMID. |
| `reference_type` | Papel da citação, em maiúsculas. Na carga atual: `BACKGROUND` (23.922), `DERIVED` (5.203) e `RESULT` (4.498). `RESULT` é o artigo de resultado do ensaio. |
| `citation` | Citação bibliográfica como está no arquivo de referências do ClinicalTrials.gov. |
| `titulo` | Título do artigo na PubMed. Preenchido quando a busca deu certo. |
| `periodico` | Periódico do artigo. |
| `ano` | Ano de publicação. Número inteiro. |
| `resumo` | Resumo do artigo (abstract). Não inclui o texto completo. |
| `busca_status` | O que aconteceu na busca do resumo: `ok` (30.965), `sem_pmid` (2.606) ou `nao_encontrado` (52). |
