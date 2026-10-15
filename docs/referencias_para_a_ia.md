# Como a IA indica os estudos na aula

O professor escreve no prompt a enfermidade ou a particularidade da aula, por exemplo dor lombar ou equilíbrio do idoso. A IA não escreve SQL. Ela chama a procedure com esse texto e devolve até cinco estudos.

```sql
CALL buscar_estudos_para_aula('dor lombar', NULL, NULL, NULL);
```

Os três `NULL` usam o padrão: pilates, fisioterapia, mobilidade e força, sem filtro de idade, cinco estudos. A procedure está em [sql/schema_mysql.sql](../sql/schema_mysql.sql). A base é a gold que já existe. Não há tabela nova.

## O que volta em cada estudo

Cada linha tem três campos:

| Campo | Conteúdo |
|---|---|
| `titulo` | Título curto do ensaio. |
| `resumo` | Um parágrafo. Primeiro o resumo da citação `RESULT` em `gold.referencias` com `busca_status = ok`. Se não houver, outro resumo `ok`. Se não houver artigo, o resumo do próprio ensaio. Texto acima de 800 caracteres é cortado. |
| `link` | `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` quando a citação escolhida tem PMID. Sem PMID, o link é a página do ensaio no ClinicalTrials.gov. |

A ordem junta o quanto o tema aparece no título, nas condições, no MeSH e no nome da intervenção, a existência de um artigo com resumo, e a data de conclusão, da mais recente para a mais antiga.

`BACKGROUND` e `DERIVED` não ocupam o lugar do artigo de resultado enquanto existir um `RESULT` com resumo. No snapshot de 15/10/2026, `gold.referencias` tem 34.257 citações ligadas aos 12.405 estudos da gold. A resposta mostra no máximo cinco, ou dez se o limite for pedido. O teto é 10.

## O que o resumo faz na aula

O professor lê o título, o parágrafo e abre o link da fonte. Isso baliza o foco da aula. O resumo não prescreve o treino, não substitui a avaliação do aluno e não autoriza copiar o protocolo do estudo para a turma. A gold só tem ensaios concluídos de pilates, fisioterapia, mobilidade ou força registrados no ClinicalTrials.gov.
