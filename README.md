# OnePilates — base de ensaios clínicos

Pipeline medalhão da base AACT/ClinicalTrials.gov para o projeto OnePilates (Grupo 8 — InfiniteLoop). No snapshot de 15/10/2026 a gold reúne 12.405 ensaios concluídos de pilates, fisioterapia, mobilidade e força, com resumos da PubMed. Uma cópia MySQL serve a IA que indica estudos ao professor na hora de montar a aula.

O grão é o ensaio (`nct_id`), não o aluno e não a prescrição da aula.

## Camadas

| Camada | Onde | O que guarda |
|---|---|---|
| Raw | `raw.estudos` | 606.957 ensaios, texto como veio do dump |
| Silver | `silver.estudos` | Os mesmos 606.957, tipados. Alertas em `silver.qualidade` |
| Gold | `gold.estudos` | 12.405 concluídos dos quatro grupos |
| Gold | `gold.referencias` | 34.257 citações, com resumo PubMed quando a busca deu certo |
| Aplicação | MySQL `estudos_aula` | Cópia consultável e a procedure `buscar_estudos_para_aula` |

O DuckDB fica em `data/clinical_trials.duckdb` e os txt de origem em `base_dados/`. Essas pastas não vêm no clone: o comando abaixo baixa o snapshot e gera a gold de novo. Um snapshot novo muda as contagens.

Um estudo entra na gold quando está `COMPLETED` e o nome ou a descrição de alguma intervenção contém termo de pilates, fisioterapia, mobilidade ou força. No snapshot de 15/10/2026 as contagens são 317, 3.933, 5.939 e 6.139. A soma passa de 12.405 porque um ensaio pode cair em mais de um grupo.

## Como rodar

```bash
py -m pip install -r requirements.txt
py pipeline/run.py
```

O primeiro download do zip flat file da AACT tem cerca de 2,35 GB. A pipeline extrai só os 11 txt que usa. Se `data/snapshot.txt` já aponta para o zip mais recente e esses txt existem, o download não se repete. Se a rede falhar e os txt locais existirem, a carga segue com o que já está na máquina.

Quando o snapshot muda, ou o DuckDB ainda não existe, `run.py` guarda os resumos PubMed já buscados, recria raw, silver e gold, e devolve esses resumos pelo PMID. O que continuar pendente é buscado na PubMed. Se o snapshot não mudou, raw, silver e gold ficam como estão e só a PubMed do que faltou é tentada.

A cópia para o MySQL roda no mesmo comando quando `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` e `MYSQL_DATABASE` estão definidas. O banco `estudos_aula` precisa existir antes. Sem essas variáveis, a gold no DuckDB fica pronta e o MySQL é pulado.

O notebook `notebooks/analise_gold.ipynb` lê a gold e mostra cortes e uma prévia das tabelas.

## O que a IA chama

O professor escreve a condição em português. A aplicação traduz para poucos termos clínicos em inglês e chama:

```sql
CALL buscar_estudos_para_aula('neck pain', NULL, NULL, NULL);
```

A procedure devolve até cinco linhas, com título, resumo de no máximo 800 caracteres e link. O link é a página PubMed quando a citação tem PMID. Sem PMID, é a página do ensaio no ClinicalTrials.gov. A IA não escreve SQL e não prescreve a aula.

## Documentação

- [Especificação da base](docs/Especificacao_Base_Dados.md)
- [Colunas de `gold.estudos`](docs/gold_estudos.md)
- [O que mudou da silver para a gold](docs/comparacao_silver_gold.md)
- [Como a IA usa as referências](docs/referencias_para_a_ia.md)
- [Manual da IA na aplicação](docs/manual_ia_aplicacao.md)
