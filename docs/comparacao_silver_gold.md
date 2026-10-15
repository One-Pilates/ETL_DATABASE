# Da silver para a gold

`silver.estudos` guarda os 606.957 ensaios do snapshot AACT de 15/10/2026, com 133 colunas já tipadas. `gold.estudos` fica com 12.405 desses ensaios e 24 colunas. O recorte está no `SELECT` de [pipeline/build_gold.py](../pipeline/build_gold.py). O significado de cada coluna da gold está em [gold_estudos.md](gold_estudos.md).

A gold não reescreve o que copia. As 21 colunas em comum têm o mesmo tipo e o mesmo valor que na silver, na linha do mesmo `nct_id`. O que muda é quem entra, quais colunas viajam e três campos que só existem na gold.

## Quem entra

Uma linha da silver passa para a gold quando as duas condições valem:

- `overall_status` é `COMPLETED`.
- O nome ou a descrição de alguma intervenção contém um termo de pilates, fisioterapia, mobilidade ou força.

Título, resumo, MeSH e critérios de elegibilidade não decidem a entrada. Um estudo pode cair em mais de um grupo.

| Grupo | Estudos na gold |
|---|---:|
| pilates | 317 |
| fisioterapia | 3.933 |
| mobilidade | 5.939 |
| forca | 6.139 |

A soma passa de 12.405 por causa dessa sobreposição.

## Colunas copiadas

Estas 21 colunas saem de `silver.estudos` e entram em `gold.estudos` sem conversão nova.

| Coluna | Tipo | O que a gold leva |
|---|---|---|
| `nct_id` | VARCHAR | Chave do ensaio. |
| `brief_title` | VARCHAR | Título curto. |
| `official_title` | VARCHAR | Título oficial. |
| `brief_summary` | VARCHAR | Resumo do registro, não o abstract da PubMed. |
| `study_type` | VARCHAR | `INTERVENTIONAL` ou `OBSERVATIONAL`. |
| `phase` | VARCHAR | Fase como texto único. |
| `phases` | VARCHAR[] | A mesma fase partida em lista. |
| `overall_status` | VARCHAR | Copiado como está. Na gold toda linha fica `COMPLETED` porque as outras situações foram excluídas. |
| `start_date` | DATE | Início. |
| `completion_date` | DATE | Conclusão do estudo. |
| `primary_completion_date` | DATE | Conclusão do desfecho primário. |
| `enrollment` | BIGINT | Participantes inscritos. |
| `minimum_age_years` | DOUBLE | Idade mínima já em anos, calculada na silver. |
| `maximum_age_years` | DOUBLE | Idade máxima já em anos, calculada na silver. |
| `gender` | VARCHAR | `ALL`, `FEMALE` ou `MALE`. |
| `conditions` | lista de struct | Condição e nome normalizado. |
| `interventions` | lista de struct | Tipo, nome e descrição. É esta lista que o filtro lê. |
| `mesh_terms` | lista de struct | Termo MeSH, papel e nome normalizado. |
| `countries_current` | lista de struct | Países que a silver já deixou sem os removidos. |
| `lead_sponsors` | lista de struct | Patrocinadores que a silver já deixou só como `LEAD`. |
| `were_results_reported` | BOOLEAN | Se o registro diz que os resultados foram postados no ClinicalTrials.gov. |

`countries_current` e `lead_sponsors` já nasceram filtradas na silver. A gold não filtra de novo. As listas completas `countries` e `sponsors` ficam só na silver.

## Colunas que nascem na gold

| Coluna | Tipo | De onde vem |
|---|---|---|
| `termos_encontrados` | VARCHAR[] | Grupos que bateram na intervenção: `pilates`, `fisioterapia`, `mobilidade`, `forca`. A lista tem pelo menos um. |
| `url` | VARCHAR | `https://clinicaltrials.gov/study/` mais o `nct_id`. |
| `_gold_at` | TIMESTAMP WITH TIME ZONE | Hora em que a gold foi gravada. Ocupa o papel de carimbo que `_silver_at` tem na silver. Não é uma cópia daquele valor. |

## Colunas que ficam só na silver

São 112. A gold não as apaga da silver. Elas continuam em `silver.estudos` para os 606.957 estudos.

### Datas administrativas

`study_first_submitted_date`, `results_first_submitted_date`, `disposition_first_submitted_date`, `last_update_submitted_date`, `study_first_submitted_qc_date`, `study_first_posted_date`, `results_first_submitted_qc_date`, `results_first_posted_date`, `disposition_first_submitted_qc_date`, `disposition_first_posted_date`, `last_update_submitted_qc_date`, `last_update_posted_date`, `verification_date`, `nlm_download_date`, `created_at`, `updated_at`, `_ingested_at`, `_silver_at`.

E o tipo ou o texto que acompanha algumas dessas datas: `study_first_posted_date_type`, `results_first_posted_date_type`, `disposition_first_posted_date_type`, `last_update_posted_date_type`, `start_month_year`, `start_date_type`, `verification_month_year`, `completion_month_year`, `completion_date_type`, `primary_completion_month_year`, `primary_completion_date_type`, `nlm_download_date_description`.

As datas de início e de conclusão do ensaio (`start_date`, `completion_date`, `primary_completion_date`) foram as que seguiram para a gold.

### Contagens e duração

`number_of_arms`, `number_of_groups`, `number_of_facilities`, `number_of_nsae_subjects`, `number_of_sae_subjects`, `registered_in_calendar_year`, `actual_duration`, `months_to_report_results`, `number_of_primary_outcomes_to_measure`, `number_of_secondary_outcomes_to_measure`, `number_of_other_outcomes_to_measure`, `enrollment_type`, `target_duration`.

`enrollment` foi a contagem que seguiu.

### Idade no formato original

`minimum_age`, `maximum_age`, `minimum_age_num`, `maximum_age_num`, `minimum_age_unit`, `maximum_age_unit`.

A gold fica com `minimum_age_years` e `maximum_age_years`, que a silver já tinha convertido para anos.

### Desenho do ensaio

`allocation`, `intervention_model`, `observational_model`, `primary_purpose`, `time_perspective`, `masking`, `sampling_method`, `intervention_model_description`, `masking_description`.

### Regulatório e marcadores

`has_expanded_access`, `expanded_access_type_individual`, `expanded_access_type_intermediate`, `expanded_access_type_treatment`, `has_dmc`, `is_fda_regulated_drug`, `is_fda_regulated_device`, `is_unapproved_device`, `is_ppsd`, `is_us_export`, `delayed_posting`, `fdaaa801_violation`, `patient_registry`, `has_us_facility`, `has_single_facility`, `subject_masked`, `caregiver_masked`, `investigator_masked`, `outcomes_assessor_masked`, `healthy_volunteers`, `gender_based`, `adult`, `child`, `older_adult`.

### Texto e identificadores que não foram

`acronym`, `last_known_status`, `source_class`, `source`, `why_stopped`, `plan_to_share_ipd`, `baseline_population`, `limitations_and_caveats`, `biospec_description`, `ipd_time_frame`, `ipd_access_criteria`, `plan_to_share_ipd_description`, `population`, `criteria`, `gender_description`, `biospec_retention`, `ipd_url`, `expanded_access_status_for_nctid`, `baseline_type_units_analyzed`, `expanded_access_nctid`.

`last_known_status` fica na silver. A gold usa `overall_status`, e o filtro só deixa `COMPLETED`.

### Listas completas

`sponsors` e `countries`. A gold leva as versões já recortadas: `lead_sponsors` e `countries_current`.

### Campos calculados na silver

`ano_inicio`, `ano_conclusao_primaria`, `status_efetivo`, `tem_resumo`, `tem_condicao`, `tem_intervencao`, `tem_patrocinador_lead`, `nct_id_valido`.

`ano_inicio` e `ano_conclusao_primaria` continuam recuperáveis pelas datas que foram para a gold.

## Tabela nova

`gold.referencias` não existe na silver. Ela junta as citações de `study_references.txt` aos `nct_id` que permaneceram na gold. São 34.257 linhas, com `nct_id`, `pmid`, `reference_type`, `citation`, `titulo`, `periodico`, `ano`, `resumo` e `busca_status`.
