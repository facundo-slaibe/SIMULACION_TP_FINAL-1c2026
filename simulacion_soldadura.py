"""
Simulación de eventos discretos de una planta de soldadura automotriz.

Variables de control:
- CP: cantidad de pedestales productivos instalados.
- CO_T1, CO_T2 y CO_T3: operarios activos en cada turno de 8 horas.

Cada pedestal necesita un operario para producir. Por eso, la
cantidad de pedestales habilitados en un turno es::

    min(CP, operarios_del_turno // OPERARIOS_POR_PEDESTAL)

Los pedidos que llegan cuando no hay capacidad quedan en una cola FIFO. Un
trabajo iniciado antes de un cambio de turno termina normalmente; si baja la
dotación, no se inicia otro hasta respetar la nueva capacidad.

Las FDP de IAP, TPROD y PS se ajustaron con ``FDPs.py`` sobre los datos reales.

Uso:
    python simulacion_soldadura.py
    python simulacion_soldadura.py --cp 4 --co-t1 4 --co-t2 3 --co-t3 4
"""

import argparse
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import stats


HV = float("inf")
MINUTOS_POR_TURNO = 8 * 60
MINUTOS_POR_DIA = 24 * 60
OPERARIOS_POR_PEDESTAL = 1
ARCHIVO_RESULTADOS = Path(__file__).with_name("resultados_simulacion.txt")
HORAS_SIMULACION = 720  # 1 año

# FDP ajustadas con Fitter sobre los datos reales (ver FDPs.py).
IAP_PARAMS = dict(
    c=0.7464458701575334,
    loc=0.016666666666666663,
    scale=1.73276913442976,
)
TPROD_PARAMS = dict(
    c=0.9056651700327778,
    loc=0.016666666666666663,
    scale=13.516054079221052,
)
PS_PARAMS = dict(a=0.35910100165214315, loc=0.0, scale=86.92320999802118)


# Veintidós escenarios iniciales para pruebas con un operario por pedestal.
# Se mantienen explícitos para que sea sencillo modificarlos arbitrariamente.
ESCENARIOS = [
    {"nombre": "CP5-A", "cp": 5, "co_t1": 5, "co_t2": 5, "co_t3": 5},
    {"nombre": "CP5-B", "cp": 5, "co_t1": 4, "co_t2": 4, "co_t3": 4},
    {"nombre": "CP5-C", "cp": 5, "co_t1": 5, "co_t2": 4, "co_t3": 4},
    {"nombre": "CP6", "cp": 6, "co_t1": 6, "co_t2": 6, "co_t3": 6},
    {"nombre": "CP7-A", "cp": 7, "co_t1": 7, "co_t2": 7, "co_t3": 7},
    {"nombre": "CP7-B", "cp": 7, "co_t1": 8, "co_t2": 8, "co_t3": 8},
    {"nombre": "CP7-C", "cp": 7, "co_t1": 6, "co_t2": 7, "co_t3": 6},
    {"nombre": "CP7-D", "cp": 7, "co_t1": 7, "co_t2": 6, "co_t3": 7},
    {"nombre": "CP8-A", "cp": 8, "co_t1": 8, "co_t2": 8, "co_t3": 8},
    {"nombre": "CP8-B", "cp": 8, "co_t1": 9, "co_t2": 9, "co_t3": 9},
    {"nombre": "CP8-C", "cp": 8, "co_t1": 7, "co_t2": 8, "co_t3": 7},
    {"nombre": "CP8-D", "cp": 8, "co_t1": 8, "co_t2": 7, "co_t3": 8},
    {"nombre": "CP10", "cp": 10, "co_t1": 10, "co_t2": 9, "co_t3": 10},
    {"nombre": "CP12-A", "cp": 12, "co_t1": 12, "co_t2": 11, "co_t3": 10},
    {"nombre": "CP12-B", "cp": 12, "co_t1": 8, "co_t2": 8, "co_t3": 8},
]


def tiempo_entre_pedidos(rng):
    raw = stats.weibull_min.rvs(**IAP_PARAMS, random_state=rng)
    return max(0.01, raw)


def tiempo_produccion(rng):
    raw = stats.weibull_min.rvs(**TPROD_PARAMS, random_state=rng)
    return max(0.1, raw)


def piezas_solicitadas(rng):
    raw = stats.gamma.rvs(**PS_PARAMS, random_state=rng)
    return max(1, int(round(raw)))


def numero_turno(tiempo):
    """Devuelve 0, 1 o 2 para los turnos diarios T1, T2 y T3."""
    return int((tiempo % MINUTOS_POR_DIA) // MINUTOS_POR_TURNO)


def capacidad_turno(cp, operarios_por_turno, tiempo):
    operarios = operarios_por_turno[numero_turno(tiempo)]
    return min(cp, operarios // OPERARIOS_POR_PEDESTAL)


def proximo_cambio_turno(tiempo):
    return (int(tiempo // MINUTOS_POR_TURNO) + 1) * MINUTOS_POR_TURNO


def validar_controles(cp, co_t1, co_t2, co_t3, horas):
    if cp <= 0:
        raise ValueError("CP debe ser mayor que cero")
    if min(co_t1, co_t2, co_t3) < 0:
        raise ValueError("Las cantidades de operarios no pueden ser negativas")
    if horas <= 0:
        raise ValueError("El horizonte de simulación debe ser mayor que cero")

TASA_RECHAZO = 0.00517

def simular(cp, co_t1, co_t2, co_t3, horas, seed=0, nombre="Manual"):
    validar_controles(cp, co_t1, co_t2, co_t3, horas)

    rng = np.random.default_rng(seed)
    tf = horas * 60
    operarios_por_turno = (co_t1, co_t2, co_t3)

    tiempo = 0.0
    proxima_llegada = tiempo_entre_pedidos(rng)
    proximo_turno = proximo_cambio_turno(tiempo)

    # Cada posición representa un pedestal. HV significa que está libre.
    fin_pedestales = [HV] * cp
    trabajos_en_curso = [None] * cp
    cola = deque()

    pedidos_llegados = 0
    pedidos_completados = 0
    demanda_piezas = 0
    piezas_producidas = 0
    piezas_rechazadas = 0
    minutos_capacidad = 0.0
    minutos_ociosos = 0.0
    minutos_operarios = 0.0
    minutos_operarios_ociosos = 0.0
    cola_maxima = 0

    while tiempo < tf:
        proxima_finalizacion = min(fin_pedestales)
        siguiente = min(proxima_llegada, proxima_finalizacion, proximo_turno, tf)

        capacidad = capacidad_turno(cp, operarios_por_turno, tiempo)
        operarios = operarios_por_turno[numero_turno(tiempo)]
        ocupados = sum(fin != HV for fin in fin_pedestales)
        intervalo = siguiente - tiempo
        minutos_capacidad += capacidad * intervalo
        minutos_ociosos += max(0, capacidad - ocupados) * intervalo
        minutos_operarios += operarios * intervalo
        # Un pedestal ocupado utiliza un operario. Los operarios que exceden
        # los trabajos en curso permanecen ociosos, incluso si sobran pedestales.
        minutos_operarios_ociosos += max(0, operarios - ocupados) * intervalo
        tiempo = siguiente

        if tiempo >= tf:
            break

        # Primero se liberan todos los trabajos que terminan en este instante.
        for i, fin in enumerate(fin_pedestales):
            if fin <= tiempo:
                pedido = trabajos_en_curso[i]
                piezas_producidas += pedido["piezas"]
                piezas_rechazadas += pedido["rechazos"]
                pedidos_completados += 1
                fin_pedestales[i] = HV
                trabajos_en_curso[i] = None

        if tiempo == proxima_llegada:
            piezas = piezas_solicitadas(rng)
            cola.append(
                {
                    "piezas": piezas,
                    "rechazos": rng.binomial(piezas, TASA_RECHAZO),
                    "duracion": tiempo_produccion(rng),
                }
            )
            pedidos_llegados += 1
            demanda_piezas += piezas
            proxima_llegada = tiempo + tiempo_entre_pedidos(rng)

        if tiempo == proximo_turno:
            proximo_turno = proximo_cambio_turno(tiempo)

        # Despacho FIFO hasta alcanzar la capacidad permitida en este turno.
        capacidad = capacidad_turno(cp, operarios_por_turno, tiempo)
        ocupados = sum(fin != HV for fin in fin_pedestales)
        libres = [i for i, fin in enumerate(fin_pedestales) if fin == HV]
        while cola and ocupados < capacidad and libres:
            i = libres.pop(0)
            pedido = cola.popleft()
            trabajos_en_curso[i] = pedido
            fin_pedestales[i] = tiempo + pedido["duracion"]
            ocupados += 1

        cola_maxima = max(cola_maxima, len(cola))

    pedidos_en_proceso = sum(fin != HV for fin in fin_pedestales)
    cumplimiento = 100 * piezas_producidas / demanda_piezas if demanda_piezas else 0.0
    pto = 100 * minutos_ociosos / minutos_capacidad if minutos_capacidad else 0.0
    pto_operarios = (
        100 * minutos_operarios_ociosos / minutos_operarios
        if minutos_operarios
        else 0.0
    )
    tr = 100 * piezas_rechazadas / piezas_producidas if piezas_producidas else 0.0

    return {
        "ESC": nombre,
        "CP": cp,
        "CO_T1": co_t1,
        "CO_T2": co_t2,
        "CO_T3": co_t3,
        "PED_LLEGADOS": pedidos_llegados,
        "PED_COMPLETADOS": pedidos_completados,
        "PED_EN_PROCESO": pedidos_en_proceso,
        "COLA_FINAL": len(cola),
        "COLA_MAX": cola_maxima,
        "CUMPLIMIENTO_%": round(cumplimiento, 2),
        "PTO_%": round(pto, 2),
        "PTO_O_%": round(pto_operarios, 2),
        "TR_%": round(tr, 3),
        "PROD_H": round(piezas_producidas / horas, 1),
    }


def ejecutar_escenarios(horas, seed):
    return [
        simular(
            escenario["cp"],
            escenario["co_t1"],
            escenario["co_t2"],
            escenario["co_t3"],
            horas,
            seed + indice,
            escenario["nombre"],
        )
        for indice, escenario in enumerate(ESCENARIOS)
    ]


COLUMNAS_RESULTADOS = [
    "ESC",
    "CP",
    "CO_T1",
    "CO_T2",
    "CO_T3",
    "CUMPLIMIENTO_%",
    "PTO_%",
    "PTO_O_%",
    "TR_%",
    "PROD_H",
    "COLA_FINAL",
]


def formatear_tabla(resultados):
    anchos = {
        columna: max(len(columna), *(len(str(fila[columna])) for fila in resultados))
        for columna in COLUMNAS_RESULTADOS
    }
    lineas = [
        "  ".join(
            columna.ljust(anchos[columna]) for columna in COLUMNAS_RESULTADOS
        ),
        "  ".join("-" * anchos[columna] for columna in COLUMNAS_RESULTADOS),
    ]
    for fila in resultados:
        lineas.append(
            "  ".join(
                str(fila[columna]).ljust(anchos[columna])
                for columna in COLUMNAS_RESULTADOS
            )
        )
    return "\n".join(lineas)


def imprimir_tabla(resultados):
    print(formatear_tabla(resultados))


def guardar_resultados(resultados, descripcion):
    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    with ARCHIVO_RESULTADOS.open("a", encoding="utf-8") as archivo:
        archivo.write(f"=== {fecha} ===\n")
        archivo.write(f"{descripcion}\n")
        archivo.write(formatear_tabla(resultados))
        archivo.write("\n\n")


def main():
    parser = argparse.ArgumentParser(description="Simulación de planta de soldadura")
    parser.add_argument("--cp", type=int, help="Cantidad de pedestales productivos")
    parser.add_argument("--co-t1", type=int, help="Operarios activos en el turno 1")
    parser.add_argument("--co-t2", type=int, help="Operarios activos en el turno 2")
    parser.add_argument("--co-t3", type=int, help="Operarios activos en el turno 3")
    parser.add_argument("--horas", type=float, default=HORAS_SIMULACION, help="Horas a simular.")
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Semilla del escenario manual o semilla inicial de los escenarios configurados.",
    )
    args = parser.parse_args()

    controles = (args.cp, args.co_t1, args.co_t2, args.co_t3)
    if all(valor is None for valor in controles):
        titulo = f"Resultados de los {len(ESCENARIOS)} escenarios configurados"
        resultados = ejecutar_escenarios(args.horas, args.seed)
        print(f"{titulo}:")
        imprimir_tabla(resultados)
        guardar_resultados(
            resultados,
            f"{titulo} | horas={args.horas} | seed_inicial={args.seed}",
        )
        return

    if any(valor is None for valor in controles):
        parser.error("para un escenario manual debe indicar --cp, --co-t1, --co-t2 y --co-t3")

    resultado = simular(
        args.cp,
        args.co_t1,
        args.co_t2,
        args.co_t3,
        args.horas,
        args.seed,
    )
    print("Resultado del escenario manual:")
    for clave, valor in resultado.items():
        print(f"{clave}: {valor}")
    guardar_resultados(
        [resultado],
        f"Escenario manual | horas={args.horas} | seed={args.seed}",
    )


if __name__ == "__main__":
    main()
