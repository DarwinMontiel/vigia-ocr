/*
  Vigía OCR · Esquema para SQL Server (2019 o superior)
  -----------------------------------------------------
  Script idempotente: se puede ejecutar varias veces sin error.
  Debe mantenerse alineado con src/vigia_ocr/adaptadores/persistencia/sql.py; la prueba
  tests/unitarias/test_repositorios.py verifica que tablas y columnas coincidan.

  Ejecución:
    sqlcmd -S localhost -U sa -P "$CLAVE" -d vigia -i sql/001_esquema.sql
*/

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.vigia_resultados', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.vigia_resultados (
        id                    INT IDENTITY(1,1) NOT NULL,
        radicado              NVARCHAR(20)      NOT NULL,
        fecha_corte           DATE              NOT NULL,
        codigo                CHAR(8)           NOT NULL,
        estado                CHAR(2)           NOT NULL,
        confianza             FLOAT             NOT NULL,
        metodo                NVARCHAR(20)      NOT NULL,
        imagenes_consultadas  INT               NOT NULL,
        consultado_en         DATETIME2(3)      NOT NULL,
        CONSTRAINT pk_vigia_resultados PRIMARY KEY CLUSTERED (id),
        -- Idempotencia garantizada por la base de datos: un radicado por fecha de corte.
        CONSTRAINT uq_vigia_resultados_radicado_corte UNIQUE (radicado, fecha_corte),
        CONSTRAINT ck_vigia_resultados_estado CHECK (estado IN ('AC', 'AP', 'EM', 'SU', 'TE')),
        CONSTRAINT ck_vigia_resultados_confianza CHECK (confianza BETWEEN 0 AND 1),
        CONSTRAINT ck_vigia_resultados_imagenes CHECK (imagenes_consultadas >= 1)
    );
END;

IF OBJECT_ID(N'dbo.vigia_lecturas', N'U') IS NULL
BEGIN
    -- Auditoría: qué leyó cada motor en cada variante. Explica cualquier resultado.
    CREATE TABLE dbo.vigia_lecturas (
        id                 INT IDENTITY(1,1) NOT NULL,
        resultado_id       INT               NOT NULL,
        motor              NVARCHAR(20)      NOT NULL,
        variante           NVARCHAR(30)      NOT NULL,
        texto_crudo        NVARCHAR(64)      NOT NULL,
        texto_normalizado  NVARCHAR(64)      NOT NULL,
        valido             BIT               NOT NULL,
        peso               FLOAT             NOT NULL,
        CONSTRAINT pk_vigia_lecturas PRIMARY KEY CLUSTERED (id),
        CONSTRAINT fk_vigia_lecturas_resultado FOREIGN KEY (resultado_id)
            REFERENCES dbo.vigia_resultados (id) ON DELETE CASCADE
    );
    CREATE INDEX ix_vigia_lecturas_resultado ON dbo.vigia_lecturas (resultado_id);
END;

COMMIT TRANSACTION;

-- Vista para operación: último estado conocido de cada radicado.
GO
CREATE OR ALTER VIEW dbo.vigia_ultimo_estado AS
SELECT r.radicado, r.fecha_corte, r.codigo, r.estado, r.confianza, r.metodo, r.consultado_en
FROM dbo.vigia_resultados AS r
WHERE r.fecha_corte = (
    SELECT MAX(r2.fecha_corte) FROM dbo.vigia_resultados AS r2 WHERE r2.radicado = r.radicado
);
GO
