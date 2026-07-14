"""
Simulación de eventos discretos de una planta de soldadura automotriz.

Variables de control:
- CP: cantidad de pedestales productivos instalados.
- CO_T1, CO_T2 y CO_T3: operarios activos en cada turno de 8 horas.

Cada pedestal necesita cinco operarios simultáneos para producir. Por eso, la
cantidad de pedestales habilitados en un turno es::

    min(CP, operarios_del_turno // OPERARIOS_POR_PEDESTAL)

Los pedidos que llegan cuando no hay capacidad quedan en una cola FIFO. Un
trabajo iniciado antes de un cambio de turno termina normalmente; si baja la
dotación, no se inicia otro hasta respetar la nueva capacidad.

Las FDP de IAP, TPROD y PS se ajustaron con ``FDPs.py`` sobre los datos reales.

Uso:
    python simulacion_soldadura.py
    python simulacion_soldadura.py --cp 4 --co-t1 16 --co-t2 14 --co-t3 15
"""

import argparse
from collections import deque

import numpy as np
from scipy import stats


HV = float("inf")
MINUTOS_POR_TURNO = 8 * 60
MINUTOS_POR_DIA = 24 * 60
OPERARIOS_POR_PEDESTAL = 5

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
TASA_RECHAZO = 0.00517


# Doce escenarios iniciales: cuatro dotaciones para cada valor de CP.
# Se mantienen explícitos para que sea sencillo modificarlos arbitrariamente.
ESCENARIOS = [
    {"nombre": "CP3-A", "cp": 3, "co_t1": 15, "co_t2": 15, "co_t3": 15},
    {"nombre": "CP3-B", "cp": 3, "co_t1": 14, "co_t2": 16, "co_t3": 15},
    {"nombre": "CP3-C", "cp": 3, "co_t1": 13, "co_t2": 15, "co_t3": 14},
    {"nombre": "CP3-D", "cp": 3, "co_t1": 16, "co_t2": 14, "co_t3": 15},
    {"nombre": "CP4-A", "cp": 4, "co_t1": 20, "co_t2": 20, "co_t3": 20},
    {"nombre": "CP4-B", "cp": 4, "co_t1": 19, "co_t2": 21, "co_t3": 20},
    {"nombre": "CP4-C", "cp": 4, "co_t1": 18, "co_t2": 20, "co_t3": 19},
    {"nombre": "CP4-D", "cp": 4, "co_t1": 16, "co_t2": 14, "co_t3": 15},
    {"nombre": "CP5-A", "cp": 5, "co_t1": 25, "co_t2": 25, "co_t3": 25},
    {"nombre": "CP5-B", "cp": 5, "co_t1": 24, "co_t2": 26, "co_t3": 25},
    {"nombre": "CP5-C", "cp": 5, "co_t1": 23, "co_t2": 25, "co_t3": 24},
    {"nombre": "CP5-D", "cp": 5, "co_t1": 26, "co_t2": 24, "co_t3": 25},
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
    cola_maxima = 0

    while tiempo < tf:
        proxima_finalizacion = min(fin_pedestales)
        siguiente = min(proxima_llegada, proxima_finalizacion, proximo_turno, tf)

        capacidad = capacidad_turno(cp, operarios_por_turno, tiempo)
        ocupados = sum(fin != HV for fin in fin_pedestales)
        intervalo = siguiente - tiempo
        minutos_capacidad += capacidad * intervalo
        minutos_ociosos += max(0, capacidad - ocupados) * intervalo
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
    tr = 100 * piezas_rechazadas / piezas_producidas if piezas_producidas else 0.0

    return {
        "ESC": nombre,
        "CP": cp,
        "CO_T1": co_t1,
        "CO_T2": co_t2,
        "CO_T3": co_t3,
        "CAP_T1": min(cp, co_t1 // OPERARIOS_POR_PEDESTAL),
        "CAP_T2": min(cp, co_t2 // OPERARIOS_POR_PEDESTAL),
        "CAP_T3": min(cp, co_t3 // OPERARIOS_POR_PEDESTAL),
        "PED_LLEGADOS": pedidos_llegados,
        "PED_COMPLETADOS": pedidos_completados,
        "PED_EN_PROCESO": pedidos_en_proceso,
        "COLA_FINAL": len(cola),
        "COLA_MAX": cola_maxima,
        "CUMPLIMIENTO_%": round(cumplimiento, 2),
        "PTO_%": round(pto, 2),
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
            seed,
            escenario["nombre"],
        )
        for escenario in ESCENARIOS
    ]


def imprimir_tabla(resultados):
    columnas = [
        "ESC",
        "CP",
        "CO_T1",
        "CO_T2",
        "CO_T3",
        "CAP_T1",
        "CAP_T2",
        "CAP_T3",
        "CUMPLIMIENTO_%",
        "PTO_%",
        "PROD_H",
        "COLA_FINAL",
    ]
    anchos = {
        columna: max(len(columna), *(len(str(fila[columna])) for fila in resultados))
        for columna in columnas
    }
    print("  ".join(columna.ljust(anchos[columna]) for columna in columnas))
    print("  ".join("-" * anchos[columna] for columna in columnas))
    for fila in resultados:
        print("  ".join(str(fila[columna]).ljust(anchos[columna]) for columna in columnas))


def main():
    parser = argparse.ArgumentParser(description="Simulación de planta de soldadura")
    parser.add_argument("--cp", type=int, help="Cantidad de pedestales productivos")
    parser.add_argument("--co-t1", type=int, help="Operarios activos en el turno 1")
    parser.add_argument("--co-t2", type=int, help="Operarios activos en el turno 2")
    parser.add_argument("--co-t3", type=int, help="Operarios activos en el turno 3")
    parser.add_argument("--horas", type=float, default=720, help="Horizonte en horas")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    controles = (args.cp, args.co_t1, args.co_t2, args.co_t3)
    if all(valor is None for valor in controles):
        print("Resultados de los 12 escenarios configurados:")
        imprimir_tabla(ejecutar_escenarios(args.horas, args.seed))
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


if __name__ == "__main__":
    main()
