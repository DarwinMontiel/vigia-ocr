"""Portal público ficticio (FastAPI) donde el estado del proceso se publica como imagen.

Rutas:

- ``GET /``: formulario de consulta por radicado.
- ``GET /consulta?radicado=...``: ficha del proceso con el estado como ``<img>``.
- ``GET /imagen-estado?radicado=...``: PNG con ruido nuevo en cada solicitud.
- ``POST /_simulacion/caida?activa=true|false``: simula que el portal se cae (HTTP 503).
- ``GET /salud``: verificación de vida.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from html import escape
from threading import Lock

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from vigia_ocr.portal_ficticio import catalogo
from vigia_ocr.sintetico.generador import ParametrosRuido, renderizar

_ESTILOS = """
:root{--tinta:#1f2a37;--suave:#5b6675;--marca:#7a3e9d;--fondo:#f6f4ef;--borde:#ded9cf}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,Segoe UI,Roboto,sans-serif;
color:var(--tinta);background:var(--fondo)}
.aviso{background:#fff3c4;color:#5c4400;text-align:center;padding:6px 16px;font-size:14px}
header{background:var(--marca);color:#fff;padding:18px 16px}header h1{margin:0;font-size:20px}
header p{margin:4px 0 0;opacity:.85;font-size:14px}
main{max-width:720px;margin:24px auto;padding:0 16px}
.tarjeta{background:#fff;border:1px solid var(--borde);border-radius:10px;padding:20px;
margin-bottom:16px}
label{display:block;font-weight:600;margin-bottom:6px}
input{width:100%;padding:10px;border:1px solid var(--borde);border-radius:6px;font:inherit}
button{margin-top:12px;background:var(--marca);color:#fff;border:0;border-radius:6px;
padding:10px 18px;font:inherit;cursor:pointer}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:0}
dt{color:var(--suave)}dd{margin:0}
.estado{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.estado img{border:1px solid var(--borde);border-radius:4px}
.error{color:#9b1c1c;font-weight:600}
footer{color:var(--suave);font-size:13px;text-align:center;margin:32px 16px}
a{color:var(--marca)}
"""


def _pagina(titulo: str, cuerpo: str) -> str:
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)} · Puerto Candela</title><style>{_ESTILOS}</style></head>
<body>
<div class="aviso">
Sitio ficticio para demostración. Ningún dato corresponde a personas reales.</div>
<header><h1>Consulta de procesos · {escape(catalogo.JUZGADO)}</h1>
<p>Ventanilla virtual para ciudadanos y apoderados</p></header>
<main>{cuerpo}</main>
<footer>Puerto Candela no existe. Este portal acompaña al proyecto Vigía OCR.</footer>
</body></html>"""


_FORMULARIO = """
<section class="tarjeta">
  <form action="/consulta" method="get">
    <label for="radicado">Número de radicado</label>
    <input id="radicado" name="radicado" placeholder="PCA-2026-00017" autocomplete="off" required>
    <button id="boton-consultar" type="submit">Consultar</button>
  </form>
</section>
<section class="tarjeta">
  <p>Por seguridad, el estado del proceso se publica como imagen.</p>
</section>
"""


@dataclass
class EstadoPortal:
    """Estado mutable del portal (simulación de caídas y generador de semillas)."""

    semilla: int | None = None
    tasa_fallos: float = 0.0
    caido: bool = False
    parametros: ParametrosRuido = field(default_factory=ParametrosRuido)
    imagenes_servidas: int = 0
    _rng: random.Random = field(init=False)
    _candado: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.semilla)

    def nueva_semilla(self) -> int:
        with self._candado:
            self.imagenes_servidas += 1
            return self._rng.getrandbits(48)

    def debe_fallar(self) -> bool:
        with self._candado:
            return self.caido or (self.tasa_fallos > 0 and self._rng.random() < self.tasa_fallos)


class _SimuladorCaidas(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        estado: EstadoPortal = request.app.state.portal
        ruta = request.url.path
        if not ruta.startswith(("/_simulacion", "/salud")) and estado.debe_fallar():
            return HTMLResponse(
                _pagina(
                    "Servicio no disponible",
                    '<section class="tarjeta" id="fuera-de-servicio"><p class="error">'
                    "El servicio no está disponible. Intente más tarde.</p></section>",
                ),
                status_code=503,
            )
        return await call_next(request)


def crear_app(
    *,
    semilla: int | None = None,
    tasa_fallos: float = 0.0,
    parametros: ParametrosRuido | None = None,
) -> FastAPI:
    app = FastAPI(title="Portal ficticio de Puerto Candela", docs_url=None, redoc_url=None)
    app.state.portal = EstadoPortal(
        semilla=semilla, tasa_fallos=tasa_fallos, parametros=parametros or ParametrosRuido()
    )
    app.add_middleware(_SimuladorCaidas)

    @app.get("/", response_class=HTMLResponse)
    def inicio() -> str:
        return _pagina("Inicio", _FORMULARIO)

    @app.get("/consulta", response_class=HTMLResponse)
    def consulta(radicado: str = Query(max_length=40)) -> HTMLResponse:
        radicado = radicado.strip().upper()
        expediente = catalogo.POR_RADICADO.get(radicado)
        if expediente is None:
            cuerpo = (
                f'{_FORMULARIO}<section class="tarjeta"><p id="mensaje-error" class="error">'
                f"No existe un proceso con el radicado {escape(radicado)}.</p></section>"
            )
            return HTMLResponse(_pagina("Sin resultados", cuerpo), status_code=404)
        nonce = app.state.portal.nueva_semilla()
        cuerpo = f"""
<section class="tarjeta" id="ficha">
  <dl>
    <dt>Radicado</dt><dd id="ficha-radicado">{escape(expediente.radicado)}</dd>
    <dt>Despacho</dt><dd>{escape(catalogo.JUZGADO)}</dd>
    <dt>Demandante</dt><dd>{escape(catalogo.ACREEDOR)}</dd>
    <dt>Demandado</dt><dd>{escape(expediente.demandado_enmascarado)}</dd>
    <dt>Última actuación</dt><dd>{escape(expediente.ultima_actuacion)}</dd>
  </dl>
</section>
<section class="tarjeta estado">
  <strong>Código de estado:</strong>
  <img id="imagen-estado" alt="Código de estado del proceso" width="240" height="72"
       src="/imagen-estado?radicado={escape(expediente.radicado)}&amp;n={nonce}">
</section>
<p><a href="/">Nueva consulta</a></p>"""
        return HTMLResponse(_pagina(f"Proceso {expediente.radicado}", cuerpo))

    @app.get("/imagen-estado")
    def imagen_estado(radicado: str = Query(max_length=40)) -> Response:
        expediente = catalogo.POR_RADICADO.get(radicado.strip().upper())
        if expediente is None:
            return Response(status_code=404)
        portal: EstadoPortal = app.state.portal
        imagen = renderizar(expediente.codigo, portal.nueva_semilla(), portal.parametros)
        bufer = io.BytesIO()
        imagen.save(bufer, format="PNG")
        return Response(
            bufer.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/_simulacion/caida")
    def simular_caida(activa: bool) -> dict[str, bool]:
        app.state.portal.caido = activa
        return {"caido": activa}

    @app.get("/salud")
    def salud() -> JSONResponse:
        return JSONResponse({"estado": "ok", "expedientes": len(catalogo.EXPEDIENTES)})

    return app
