"""Caso de uso principal: consultar el estado de un lote de radicados y guardarlo.

Por cada radicado:

1. **Idempotencia**: si ya hay resultado para (radicado, fecha de corte), se omite.
2. **Portal tras circuit breaker**: se pide la imagen; si el portal está caído, el circuito
   se abre y el resto del lote se marca pendiente sin seguir golpeando el portal.
3. **Lectura por consenso**: si la votación no es confiable, se pide otra imagen (el portal
   genera ruido nuevo en cada solicitud), hasta ``max_imagenes``.
4. **Guardar y verificar**: se guarda y se vuelve a leer de la base de datos para confirmar
   que lo persistido es exactamente lo que se leyó.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import structlog

from vigia_ocr.aplicacion.circuit_breaker import CircuitBreaker
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.dominio.errores import (
    CircuitoAbierto,
    ErrorVerificacion,
    PortalNoDisponible,
    RadicadoInexistente,
)
from vigia_ocr.dominio.modelos import (
    Desenlace,
    Radicado,
    ResultadoConsulta,
    ResultadoRadicado,
    ResumenLote,
    Veredicto,
)
from vigia_ocr.puertos import PortalConsultas, Reloj, RepositorioResultados

log = structlog.get_logger(__name__)


class ServicioConsulta:
    def __init__(
        self,
        portal: PortalConsultas,
        lector: LectorConsenso,
        repositorio: RepositorioResultados,
        breaker: CircuitBreaker,
        reloj: Reloj,
        *,
        max_imagenes: int = 3,
        confianza_minima: float = 0.0,
    ) -> None:
        if max_imagenes < 1:
            raise ValueError("max_imagenes debe ser al menos 1")
        self._portal = portal
        self._lector = lector
        self._repositorio = repositorio
        self._breaker = breaker
        self._reloj = reloj
        self._max_imagenes = max_imagenes
        self._confianza_minima = confianza_minima

    def procesar_lote(self, radicados: Iterable[Radicado], fecha_corte: date) -> ResumenLote:
        resumen = ResumenLote()
        for radicado in radicados:
            resultado = self.procesar(radicado, fecha_corte)
            resumen.resultados.append(resultado)
        log.info(
            "Lote terminado",
            total=resumen.total,
            exitosos=resumen.exitosos,
            pendientes=len(resumen.pendientes),
            **{d.value: resumen.contar(d) for d in Desenlace},
        )
        return resumen

    def procesar(self, radicado: Radicado, fecha_corte: date) -> ResultadoRadicado:
        bitacora = log.bind(radicado=radicado.valor, fecha_corte=fecha_corte.isoformat())

        existente = self._repositorio.obtener(radicado, fecha_corte)
        if existente is not None:
            bitacora.info("Radicado ya consultado para esta fecha de corte; se omite")
            return ResultadoRadicado(
                radicado, Desenlace.OMITIDO_YA_EXISTIA, existente.codigo, existente
            )

        ultimo: Veredicto | None = None
        for intento in range(1, self._max_imagenes + 1):
            try:
                imagen = self._breaker.llamar(lambda: self._portal.obtener_imagen_estado(radicado))
            except RadicadoInexistente as error:
                bitacora.warning("El portal no reconoce el radicado", detalle=str(error))
                return ResultadoRadicado(radicado, Desenlace.RADICADO_INEXISTENTE, str(error))
            except CircuitoAbierto as error:
                bitacora.warning("Circuito abierto; el radicado queda pendiente")
                return ResultadoRadicado(radicado, Desenlace.CIRCUITO_ABIERTO, str(error))
            except PortalNoDisponible as error:
                bitacora.error("Portal no disponible", intento=intento, detalle=str(error))
                return ResultadoRadicado(radicado, Desenlace.PORTAL_NO_DISPONIBLE, str(error))

            ultimo = self._lector.leer(imagen)
            bitacora.debug(
                "Imagen leída",
                intento=intento,
                codigo=ultimo.codigo,
                metodo=ultimo.metodo.value,
                confianza=ultimo.confianza,
                lecturas=[f"{x.motor}/{x.variante}={x.texto_crudo!r}" for x in ultimo.lecturas],
            )
            if ultimo.aceptado and ultimo.confianza >= self._confianza_minima:
                return self._guardar_y_verificar(radicado, fecha_corte, ultimo, intento)
            bitacora.info("Lectura no confiable; se pide una imagen nueva", intento=intento)

        detalle = f"Sin consenso tras {self._max_imagenes} imágenes"
        bitacora.warning("No se logró una lectura confiable", detalle=detalle)
        return ResultadoRadicado(radicado, Desenlace.SIN_LECTURA_CONFIABLE, detalle)

    def _guardar_y_verificar(
        self, radicado: Radicado, fecha_corte: date, veredicto: Veredicto, intentos: int
    ) -> ResultadoRadicado:
        if veredicto.codigo is None or veredicto.estado is None:
            raise ValueError("Solo se guardan veredictos aceptados")
        resultado = ResultadoConsulta(
            radicado=radicado,
            fecha_corte=fecha_corte,
            codigo=veredicto.codigo,
            estado=veredicto.estado,
            confianza=veredicto.confianza,
            metodo=veredicto.metodo,
            imagenes_consultadas=intentos,
            consultado_en=self._reloj.ahora(),
            lecturas=veredicto.lecturas,
        )
        insertado = self._repositorio.guardar(resultado)
        persistido = self._repositorio.obtener(radicado, fecha_corte)
        if persistido is None:
            raise ErrorVerificacion(
                f"Verificación tras guardar falló para {radicado}: el registro no aparece"
            )
        if not insertado:
            # Otra ejecución lo guardó entre nuestra consulta y nuestro INSERT: gana la primera.
            log.info("Otro proceso guardó el radicado primero", radicado=radicado.valor)
            return ResultadoRadicado(
                radicado, Desenlace.OMITIDO_YA_EXISTIA, persistido.codigo, persistido
            )
        if (persistido.codigo, persistido.estado) != (resultado.codigo, resultado.estado):
            raise ErrorVerificacion(
                f"Verificación tras guardar falló para {radicado}: se guardó "
                f"{resultado.codigo!r} y se leyó {persistido.codigo!r}"
            )
        log.info(
            "Estado guardado y verificado",
            radicado=radicado.valor,
            codigo=resultado.codigo,
            estado=resultado.estado.descripcion,
            confianza=resultado.confianza,
            metodo=resultado.metodo.value,
            imagenes=intentos,
        )
        return ResultadoRadicado(radicado, Desenlace.GUARDADO, resultado.codigo, resultado)
