# Arquitectura

Vigía OCR sigue una **arquitectura hexagonal** ([ADR-0001](adr/0001-arquitectura-hexagonal.md)):
el núcleo no sabe que existen Selenium, SQL Server ni los motores OCR; solo conoce
contratos (puertos). Los adaptadores implementan esos contratos.

## Vista general

```mermaid
flowchart LR
    subgraph Entrada["Adaptadores de entrada"]
        CLI["CLI typer<br/>vigia consultar · evaluar · leer"]
    end

    subgraph Nucleo["Núcleo (sin infraestructura)"]
        direction TB
        subgraph App["aplicacion/"]
            SC["ServicioConsulta"]
            LC["LectorConsenso"]
            CB["CircuitBreaker"]
        end
        subgraph Dom["dominio/"]
            COD["codigo · Luhn"]
            NOR["normalizacion"]
            VOT["votacion"]
            MOD["modelos"]
        end
        subgraph Puertos["puertos/ (Protocol)"]
            P1(["PortalConsultas"])
            P2(["MotorOCR"])
            P3(["Preprocesador"])
            P4(["RepositorioResultados"])
            P5(["Reloj"])
        end
    end

    subgraph Salida["Adaptadores de salida"]
        SEL["PortalSelenium<br/>Chrome + recorte"]
        OCR["ddddocr · Tesseract · EasyOCR"]
        PRE["Variantes Pillow/OpenCV"]
        SQL["RepositorioSQL<br/>SQL Server · SQLite"]
        MEM["RepositorioEnMemoria"]
        REL["RelojSistema"]
    end

    CLI --> SC
    SC --> LC --> VOT
    SC --> CB
    LC --> NOR & COD
    SC -.-> P1 & P4 & P5
    LC -.-> P2 & P3
    P1 -.implementa.- SEL
    P2 -.implementa.- OCR
    P3 -.implementa.- PRE
    P4 -.implementa.- SQL & MEM
    P5 -.implementa.- REL
    SEL --> PORTAL[("Portal público<br/>(ficticio)")]
    SQL --> BD[("SQL Server")]
```

La raíz de composición (`contenedor.py`) es el único módulo que importa a la vez núcleo y
adaptadores. `tests/unitarias/test_arquitectura.py` verifica estas fronteras en cada
ejecución de pruebas.

## Flujo de un radicado

```mermaid
sequenceDiagram
    autonumber
    participant S as ServicioConsulta
    participant R as Repositorio
    participant B as CircuitBreaker
    participant P as PortalSelenium
    participant L as LectorConsenso

    S->>R: obtener(radicado, fecha_corte)
    alt ya existe
        R-->>S: resultado previo
        Note over S: omitido_ya_existia (no toca el portal)
    else no existe
        loop hasta max_imagenes
            S->>B: llamar(obtener_imagen_estado)
            B->>P: navegar, consultar, capturar, recortar
            P-->>S: imagen (ruido nuevo en cada solicitud)
            S->>L: leer(imagen)
            L->>L: variantes × motores → normalizar → validar DV → votar
            L-->>S: veredicto
            break veredicto aceptado
                S->>R: guardar(resultado)
                S->>R: obtener(...) en sesión nueva
                Note over S,R: verificación tras guardar
            end
        end
    end
```

## Cadena de lectura

```mermaid
flowchart LR
    IMG["Imagen recortada"] --> V1["otsu_x2_apertura"] & V2["otsu_x2"] & V3["canal_minimo"] & V4["mediana"] & V5["original"]
    V1 & V2 & V3 & V4 & V5 --> M{"ddddocr → tesseract → easyocr<br/>(del más rápido al más lento)"}
    M --> N["Normalización posicional<br/>O→0, 5→S, B→8 …"]
    N --> D["Patrón + dígito Luhn"]
    D --> VOTO{"Votación"}
    VOTO -- "≥ 2 lecturas válidas coinciden" --> OK["Código aceptado"]
    VOTO -- "conflicto o sin mayoría" --> CAR["Votación por carácter<br/>+ DV como árbitro"]
    CAR -- "DV cuadra" --> OK
    CAR -- "DV no cuadra" --> NUEVA["Pedir otra imagen"]
```

## Puertos y adaptadores

| Puerto | Contrato | Adaptadores |
|---|---|---|
| `PortalConsultas` | `obtener_imagen_estado(radicado) -> Image` · lanza `RadicadoInexistente` o `PortalNoDisponible` | `PortalSelenium` (producción), `PortalGuion` (pruebas) |
| `MotorOCR` | `nombre`, `leer(imagen) -> str` | `MotorDdddocr`, `MotorTesseract`, `MotorEasyOCR`, dobles de prueba |
| `Preprocesador` | `nombre`, `aplicar(imagen) -> Image` | `Variante` (cadena de pasos OpenCV) |
| `RepositorioResultados` | `obtener(radicado, corte)`, `guardar(resultado) -> bool` | `RepositorioSQL` (SQL Server / SQLite), `RepositorioEnMemoria` |
| `Reloj` | `ahora()`, `monotonico()` | `RelojSistema`, `RelojFalso` (pruebas) |

## Errores

| Tipo | Ejemplos | Qué hace el caso de uso |
|---|---|---|
| `ErrorDeNegocio` | `RadicadoInexistente` | Registra el desenlace y sigue; no se reintenta. No abre el circuito. |
| `ErrorDeSistema` | `PortalNoDisponible`, `CircuitoAbierto` | El radicado queda pendiente; cuenta para el circuit breaker. |
| `ErrorVerificacion` | Lo guardado no coincide con lo leído | Detiene el lote: la base de datos no es confiable. |
| `MotorNoDisponible` | Falta el binario de Tesseract | Al arrancar: se omite el motor (configurable). Durante la lectura: se propaga. |

## Modelo de datos

```mermaid
erDiagram
    vigia_resultados ||--o{ vigia_lecturas : "audita"
    vigia_resultados {
        int id PK
        nvarchar radicado "UNIQUE con fecha_corte"
        date fecha_corte
        char codigo "8: EE + serie + DV"
        char estado "AC AP EM SU TE"
        float confianza "0..1"
        nvarchar metodo "unanime mayoria por_caracter"
        int imagenes_consultadas
        datetime2 consultado_en
    }
    vigia_lecturas {
        int id PK
        int resultado_id FK
        nvarchar motor
        nvarchar variante
        nvarchar texto_crudo
        nvarchar texto_normalizado
        bit valido
        float peso
    }
```

El DDL para SQL Server está en [`sql/001_esquema.sql`](../sql/001_esquema.sql) (idempotente,
con `CHECK` y una vista `vigia_ultimo_estado`). Una prueba unitaria compara sus tablas y
columnas con el modelo del ORM para que no diverjan.
