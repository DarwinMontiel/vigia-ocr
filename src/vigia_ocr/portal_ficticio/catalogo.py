"""Expedientes del Juzgado Promiscuo Ficticio de Puerto Candela.

Todo es inventado: Puerto Candela no existe, las personas tampoco y los documentos usan el
prefijo 99.999, que no corresponde a cédulas reales. Apellidos como "Ficticio", "Prueba" o
"Demo" están ahí para que nadie lo confunda con datos reales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from vigia_ocr.dominio.codigo import EstadoObligacion, construir_codigo

JUZGADO: Final = "Juzgado Promiscuo Ficticio de Puerto Candela"
ACREEDOR: Final = "Cooperativa La Alcancía de Puerto Candela (ficticia)"


@dataclass(frozen=True, slots=True)
class Expediente:
    radicado: str
    demandado: str
    documento: str
    estado: EstadoObligacion
    serie: str
    ultima_actuacion: str
    nota: str

    @property
    def codigo(self) -> str:
        return construir_codigo(self.estado, self.serie)

    @property
    def demandado_enmascarado(self) -> str:
        """Como lo muestran los portales públicos: solo la inicial de los apellidos."""
        nombre, *apellidos = self.demandado.split()
        return " ".join([nombre, *(f"{a[0]}***" for a in apellidos)])


_E = EstadoObligacion

EXPEDIENTES: Final[tuple[Expediente, ...]] = (
    Expediente("PCA-2026-00017", "Eustaquio Bocanegra Ficticio", "99.999.001", _E.ACUERDO_DE_PAGO,
               "48213", "2026-10-28", "Prometió pagar después de la feria del mango. Cumplió."),
    Expediente("PCA-2026-00023", "Rosalba Peñaranda Prueba", "99.999.002", _E.EMBARGO,
               "10974", "2026-10-30", "Embargo de la volqueta con la que repartía arepas."),
    Expediente("PCA-2026-00031", "Teodomiro Cañaveral Inventado", "99.999.003", _E.ACTIVA,
               "77120", "2026-11-02", "No contesta: dice que el celular se le cayó al río."),
    Expediente("PCA-2026-00042", "Brígida Montenegro Demo", "99.999.004", _E.TERMINADA,
               "30568", "2026-09-15", "Pagó todo en monedas de 500. El juzgado aún las cuenta."),
    Expediente("PCA-2026-00056", "Anacleto Rentería Simulado", "99.999.005", _E.SUSPENDIDA,
               "65031", "2026-10-11", "Proceso suspendido mientras se aclara quién es el gemelo."),
    Expediente("PCA-2026-00068", "Clemencia Arboleda Ficticia", "99.999.006", _E.ACUERDO_DE_PAGO,
               "21459", "2026-11-05", "Acuerdo a 12 cuotas, firmado en papel de la panadería."),
    Expediente("PCA-2026-00075", "Policarpo Quintana Inventado", "99.999.007", _E.EMBARGO,
               "58806", "2026-10-21", "Se embargó un gallo de pelea que resultó ser gallina."),
    Expediente("PCA-2026-00089", "Herminia Sarmiento Ejemplo", "99.999.008", _E.ACTIVA,
               "93317", "2026-11-06", "Pide paz y salvo de una deuda que sigue debiendo."),
    Expediente("PCA-2026-00094", "Gumersindo Lozada Ficticio", "99.999.009", _E.TERMINADA,
               "04482", "2026-08-30", "Pagó con la cosecha de café. Buen año."),
    Expediente("PCA-2026-00102", "Leocadia Benavides Prueba", "99.999.010", _E.ACTIVA,
               "36690", "2026-11-04", "Dirección registrada: 'la casa azul después del palo'."),
    Expediente("PCA-2026-00115", "Saturnino Ospina Inventado", "99.999.011", _E.SUSPENDIDA,
               "71245", "2026-10-02", "Suspendido por inundación del archivo del juzgado."),
    Expediente("PCA-2026-00127", "Filomena Castañeda Demo", "99.999.012", _E.ACUERDO_DE_PAGO,
               "88013", "2026-11-07", "Paga puntual cada quincena; el bot solo confirma."),
)  # fmt: skip

POR_RADICADO: Final[dict[str, Expediente]] = {e.radicado: e for e in EXPEDIENTES}
