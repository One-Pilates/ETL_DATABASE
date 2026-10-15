-- Base consultada pela IA do professor.
-- CALL buscar_estudos_para_aula('dor lombar', NULL, NULL, NULL)
-- O padrão usa pilates, fisioterapia, mobilidade e forca, sem filtro de idade, com 5 estudos.
-- Cada linha devolve titulo, resumo de até 800 caracteres e link.

DROP PROCEDURE IF EXISTS buscar_estudos_para_aula;
DROP FUNCTION IF EXISTS sem_acento;

DROP TABLE IF EXISTS referencia;
DROP TABLE IF EXISTS estudo_mesh;
DROP TABLE IF EXISTS estudo_intervencao;
DROP TABLE IF EXISTS estudo_condicao;
DROP TABLE IF EXISTS estudo_grupo;
DROP TABLE IF EXISTS estudo;

CREATE TABLE estudo (
    nct_id VARCHAR(20) NOT NULL,
    brief_title TEXT,
    official_title TEXT,
    brief_summary MEDIUMTEXT,
    study_type VARCHAR(64),
    phase VARCHAR(64),
    overall_status VARCHAR(32) NOT NULL,
    start_date DATE,
    completion_date DATE,
    primary_completion_date DATE,
    enrollment BIGINT,
    minimum_age_years DECIMAL(8, 2),
    maximum_age_years DECIMAL(8, 2),
    gender VARCHAR(32),
    were_results_reported TINYINT(1),
    url VARCHAR(255),
    texto_busca MEDIUMTEXT,
    gold_at DATETIME,
    PRIMARY KEY (nct_id),
    FULLTEXT KEY ft_estudo_texto (texto_busca)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE estudo_grupo (
    nct_id VARCHAR(20) NOT NULL,
    grupo VARCHAR(32) NOT NULL,
    PRIMARY KEY (nct_id, grupo),
    KEY idx_estudo_grupo_grupo (grupo),
    CONSTRAINT fk_estudo_grupo_estudo
        FOREIGN KEY (nct_id) REFERENCES estudo (nct_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE estudo_condicao (
    id BIGINT NOT NULL AUTO_INCREMENT,
    nct_id VARCHAR(20) NOT NULL,
    nome TEXT,
    nome_normalizado VARCHAR(512),
    PRIMARY KEY (id),
    KEY idx_estudo_condicao_nct (nct_id),
    KEY idx_estudo_condicao_nome (nome_normalizado),
    CONSTRAINT fk_estudo_condicao_estudo
        FOREIGN KEY (nct_id) REFERENCES estudo (nct_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE estudo_intervencao (
    id BIGINT NOT NULL AUTO_INCREMENT,
    nct_id VARCHAR(20) NOT NULL,
    tipo VARCHAR(64),
    nome TEXT,
    descricao MEDIUMTEXT,
    PRIMARY KEY (id),
    KEY idx_estudo_intervencao_nct (nct_id),
    CONSTRAINT fk_estudo_intervencao_estudo
        FOREIGN KEY (nct_id) REFERENCES estudo (nct_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE estudo_mesh (
    id BIGINT NOT NULL AUTO_INCREMENT,
    nct_id VARCHAR(20) NOT NULL,
    termo TEXT,
    tipo VARCHAR(64),
    termo_normalizado VARCHAR(512),
    PRIMARY KEY (id),
    KEY idx_estudo_mesh_nct (nct_id),
    KEY idx_estudo_mesh_termo (termo_normalizado),
    CONSTRAINT fk_estudo_mesh_estudo
        FOREIGN KEY (nct_id) REFERENCES estudo (nct_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE referencia (
    id BIGINT NOT NULL AUTO_INCREMENT,
    nct_id VARCHAR(20) NOT NULL,
    pmid VARCHAR(32),
    reference_type VARCHAR(32),
    citation TEXT,
    titulo TEXT,
    periodico VARCHAR(512),
    ano INT,
    resumo MEDIUMTEXT,
    busca_status VARCHAR(32),
    PRIMARY KEY (id),
    KEY idx_referencia_nct (nct_id, busca_status, reference_type),
    CONSTRAINT fk_referencia_estudo
        FOREIGN KEY (nct_id) REFERENCES estudo (nct_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER $$

CREATE FUNCTION sem_acento(p_texto VARCHAR(200))
RETURNS VARCHAR(200)
NO SQL
DETERMINISTIC
BEGIN
    DECLARE v VARCHAR(200);
    SET v = LOWER(IFNULL(p_texto, ''));
    SET v = REPLACE(v, 'á', 'a');
    SET v = REPLACE(v, 'à', 'a');
    SET v = REPLACE(v, 'â', 'a');
    SET v = REPLACE(v, 'ã', 'a');
    SET v = REPLACE(v, 'ä', 'a');
    SET v = REPLACE(v, 'é', 'e');
    SET v = REPLACE(v, 'è', 'e');
    SET v = REPLACE(v, 'ê', 'e');
    SET v = REPLACE(v, 'ë', 'e');
    SET v = REPLACE(v, 'í', 'i');
    SET v = REPLACE(v, 'ì', 'i');
    SET v = REPLACE(v, 'î', 'i');
    SET v = REPLACE(v, 'ï', 'i');
    SET v = REPLACE(v, 'ó', 'o');
    SET v = REPLACE(v, 'ò', 'o');
    SET v = REPLACE(v, 'ô', 'o');
    SET v = REPLACE(v, 'õ', 'o');
    SET v = REPLACE(v, 'ö', 'o');
    SET v = REPLACE(v, 'ú', 'u');
    SET v = REPLACE(v, 'ù', 'u');
    SET v = REPLACE(v, 'û', 'u');
    SET v = REPLACE(v, 'ü', 'u');
    SET v = REPLACE(v, 'ç', 'c');
    SET v = REPLACE(v, 'ñ', 'n');
    RETURN TRIM(v);
END$$

CREATE PROCEDURE buscar_estudos_para_aula(
    IN p_tema VARCHAR(200),
    IN p_grupos VARCHAR(200),
    IN p_idade INT,
    IN p_limite INT
)
BEGIN
    DECLARE v_tema VARCHAR(200);
    DECLARE v_grupos VARCHAR(200) DEFAULT '';
    DECLARE v_rest VARCHAR(220);
    DECLARE v_token VARCHAR(32);
    DECLARE v_limite INT;
    DECLARE v_idade_sql VARCHAR(400);
    DECLARE v_guard INT DEFAULT 0;

    SET v_tema = sem_acento(TRIM(p_tema));
    SET v_tema = REPLACE(v_tema, '''', ' ');
    SET v_tema = REPLACE(v_tema, '"', ' ');
    SET v_tema = REPLACE(v_tema, '\\', ' ');
    SET v_tema = REPLACE(v_tema, ';', ' ');
    SET v_tema = REPLACE(v_tema, '(', ' ');
    SET v_tema = REPLACE(v_tema, ')', ' ');
    WHILE INSTR(v_tema, '  ') > 0 AND v_guard < 40 DO
        SET v_tema = REPLACE(v_tema, '  ', ' ');
        SET v_guard = v_guard + 1;
    END WHILE;
    SET v_tema = TRIM(v_tema);
    IF v_tema = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Tema obrigatório';
    END IF;

    SET v_rest = CONCAT(
        REPLACE(
            sem_acento(IFNULL(NULLIF(TRIM(p_grupos), ''), 'pilates,fisioterapia,mobilidade,forca')),
            ' ',
            ''
        ),
        ','
    );
    SET v_guard = 0;
    WHILE CHAR_LENGTH(v_rest) > 0 AND v_guard < 20 DO
        SET v_token = SUBSTRING_INDEX(v_rest, ',', 1);
        SET v_rest = SUBSTRING(v_rest, CHAR_LENGTH(v_token) + 2);
        IF v_token IN ('pilates', 'fisioterapia', 'mobilidade', 'forca')
           AND FIND_IN_SET(v_token, v_grupos) = 0 THEN
            SET v_grupos = IF(v_grupos = '', v_token, CONCAT(v_grupos, ',', v_token));
        END IF;
        SET v_guard = v_guard + 1;
    END WHILE;
    IF v_grupos = '' THEN
        SET v_grupos = 'pilates,fisioterapia,mobilidade,forca';
    END IF;

    SET v_limite = IFNULL(p_limite, 5);
    IF v_limite < 1 THEN
        SET v_limite = 5;
    END IF;
    IF v_limite > 10 THEN
        SET v_limite = 10;
    END IF;

    IF p_idade IS NULL THEN
        SET v_idade_sql = '1 = 1';
    ELSE
        SET v_idade_sql = CONCAT(
            '((e.minimum_age_years IS NULL OR e.minimum_age_years <= ',
            p_idade,
            ') AND (e.maximum_age_years IS NULL OR e.maximum_age_years >= ',
            p_idade,
            '))'
        );
    END IF;

    SET @sql_busca = CONCAT(
        'SELECT
            e.brief_title AS titulo,
            CASE
                WHEN COALESCE(ref.resumo, e.brief_summary) IS NULL THEN NULL
                WHEN CHAR_LENGTH(COALESCE(ref.resumo, e.brief_summary)) <= 800
                    THEN COALESCE(ref.resumo, e.brief_summary)
                ELSE CONCAT(LEFT(COALESCE(ref.resumo, e.brief_summary), 800), ''...'')
            END AS resumo,
            CASE
                WHEN ref.pmid IS NOT NULL AND ref.pmid <> ''''
                    THEN CONCAT(''https://pubmed.ncbi.nlm.nih.gov/'', ref.pmid, ''/'')
                ELSE e.url
            END AS link
         FROM estudo e
         LEFT JOIN (
            SELECT nct_id, pmid, resumo
            FROM (
                SELECT
                    nct_id,
                    pmid,
                    resumo,
                    ROW_NUMBER() OVER (
                        PARTITION BY nct_id
                        ORDER BY (reference_type = ''RESULT'') DESC, ano DESC
                    ) AS rn
                FROM referencia
                WHERE busca_status = ''ok''
                  AND resumo IS NOT NULL
                  AND CHAR_LENGTH(resumo) > 0
            ) escolhida
            WHERE rn = 1
         ) ref ON ref.nct_id = e.nct_id
         WHERE e.overall_status = ''COMPLETED''
           AND MATCH(e.texto_busca) AGAINST (''',
        v_tema,
        ''' IN NATURAL LANGUAGE MODE)
           AND EXISTS (
                SELECT 1
                  FROM estudo_grupo g
                 WHERE g.nct_id = e.nct_id
                   AND FIND_IN_SET(g.grupo, ''',
        v_grupos,
        ''')
           )
           AND ',
        v_idade_sql,
        '
         ORDER BY MATCH(e.texto_busca) AGAINST (''',
        v_tema,
        ''' IN NATURAL LANGUAGE MODE) DESC,
            (ref.resumo IS NOT NULL) DESC,
            e.completion_date DESC
         LIMIT ',
        v_limite
    );
    PREPARE stmt_busca FROM @sql_busca;
    EXECUTE stmt_busca;
    DEALLOCATE PREPARE stmt_busca;
END$$

DELIMITER ;
