# OnePilates — base de ensaios clínicos

Pipeline medalhão da base AACT/ClinicalTrials.gov para o projeto OnePilates (Grupo 8 — InfiniteLoop). A gold reúne 12.158 ensaios concluídos de pilates, fisioterapia, mobilidade e força, com resumos da PubMed. Uma cópia MySQL serve a IA que indica estudos ao professor na hora de montar a aula.

O grão é o ensaio (`nct_id`), não o aluno e não a prescrição da aula.

## Camadas

| Camada | Onde | O que guarda |
|---|---|---|
| Raw | `raw.estudos` | 602.514 ensaios, texto como veio do dump |
| Silver | `silver.estudos` | Os mesmos 602.514, tipados. Alertas em `silver.qualidade` |
| Gold | `gold.estudos` | 12.158 concluídos dos quatro grupos |
| Gold | `gold.referencias` | 33.623 citações, com resumo PubMed quando a busca deu certo |
| Aplicação | MySQL `estudos_aula` | Cópia consultável e a procedure `buscar_estudos_para_aula` |

Tudo isso, menos o MySQL, está em `data/clinical_trials.duckdb`. Os arquivos de origem estão em `base_dados/`.

Um estudo entra na gold quando está `COMPLETED` e o nome ou a descrição de alguma intervenção contém termo de pilates, fisioterapia, mobilidade ou força. As contagens são 309, 3.848, 5.811 e 5.994. A soma passa de 12.158 porque um ensaio pode cair em mais de um grupo.

## Como rodar

```bash
py -m pip install -r requirements.txt
py pipeline/ingest_raw.py
py pipeline/build_silver.py
py pipeline/build_gold.py
py pipeline/fetch_pubmed.py
```

`ingest_raw.py` recria o arquivo DuckDB. Não rode essa etapa se a silver, a gold ou os resumos PubMed precisarem ser preservados.

A cópia para o MySQL exige o banco `estudos_aula` já criado e estas variáveis: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.

```bash
py pipeline/load_mysql.py
```

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
