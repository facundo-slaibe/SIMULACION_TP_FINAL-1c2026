"""
Simulación de eventos discretos (EaE con Tiempo Comprometido) de la planta
de soldadura automotriz. 

Esquema:
- Reloj de simulación avanza evento a evento.
- Un único evento propio: Llegada de pedido de pieza (EFNC = si mismo).
- Cada pedestal productivo es un "recurso" con su propio tiempo comprometido
  (TCP) y acumulador de tiempo ocioso (STOP).
- Las FDPs de IAP y TPROD se ajustaron con `FDPs.py` (Fitter)
  sobre los datos reales del dataset.

NOTA IMPORTANTE (transparencia): la variable de control CO_T (operarios
activos por turno) todavía no está calibrada con datos reales -- el dataset
solo tiene el campo USUARIO, que identifica personas distintas a lo largo de
4 meses, no operarios simultáneos por turno. Hasta que el compañero confirme
cómo estimarla, este script solo varía CP (cantidad de pedestales
productivos) como variable de control.

Uso:
    python simulacion_soldadura.py --cp 12 --horas 720
"""
import argparse
import math
import numpy as np
from scipy import stats

HV = float("inf")

# --------------------------------------------------------------------------- #
# FDPs ajustadas con Fitter sobre los datos reales (ver FDPs.py)
# --------------------------------------------------------------------------- #
IAP_PARAMS = dict(c=0.7464458701575334, loc=0.016666666666666663, scale=1.73276913442976)      # weibull_min, minutos
TPROD_PARAMS = dict(c=0.9056651700327778, loc=0.016666666666666663, scale=13.516054079221052)  # weibull_min, minutos
TASA_RECHAZO = 0.00517          # PZR / PZ1 real del dataset
PS_MEDIA, PS_DESVIO = 33.76, 25  # piezas solicitadas por pedido (aprox. empírico)


def tiempo_entre_pedidos(rng):
    raw = stats.weibull_min.rvs(**IAP_PARAMS, random_state=rng)
    return max(0.01, raw)


def tiempo_produccion(rng):
    raw = stats.weibull_min.rvs(**TPROD_PARAMS, random_state=rng)
    return max(0.1, raw)


def min_tc_max_sto(TC, STO):
    """Selecciona el pedestal libre antes (o el de mayor ocio si hay empate),
    igual que la función homónima del script de drones."""
    min_val = HV
    pos = 0
    for i, v in enumerate(TC):
        if v < min_val:
            min_val = v
            pos = i
        elif v == min_val and STO[i] > STO[pos]:
            pos = i
    return pos


def simular(cp, horas, seed=0):
    rng = np.random.default_rng(seed)
    TF = horas * 60  # horizonte de simulación en minutos

    T = 0.0
    TPP = 0.0  # tiempo próximo pedido de pieza (TPPP)
    TCP = [0.0] * cp
    STOP = [0.0] * cp

    piezas_producidas = 0
    piezas_rechazadas = 0
    pedidos_atendidos = 0

    while T <= TF:
        T = TPP
        TPP = T + tiempo_entre_pedidos(rng)

        tprod = tiempo_produccion(rng)
        ps = max(1, int(rng.normal(PS_MEDIA, PS_DESVIO)))
        pr = rng.binomial(ps, TASA_RECHAZO)

        i = min_tc_max_sto(TCP, STOP)
        if T >= TCP[i]:
            STOP[i] += T - TCP[i]
            TCP[i] = T + tprod
        else:
            # el pedestal sigue ocupado: el pedido se encola en el mismo
            # pedestal elegido (FIFO simple), sin generar tiempo ocioso
            TCP[i] = TCP[i] + tprod

        piezas_producidas += ps
        piezas_rechazadas += pr
        pedidos_atendidos += 1

    pto_promedio = 100 * np.mean([s / TF for s in STOP])
    tr = 100 * piezas_rechazadas / piezas_producidas if piezas_producidas else 0
    prod_h = piezas_producidas / horas

    return {
        "CP": cp,
        "pedidos_atendidos": pedidos_atendidos,
        "PTO_promedio_%": round(pto_promedio, 2),
        "TR_%": round(tr, 3),
        "PROD_H": round(prod_h, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Simulación planta de soldadura")
    parser.add_argument("--cp", type=int, default=16, help="Cantidad de pedestales productivos")
    parser.add_argument("--horas", type=int, default=720, help="Horizonte de simulación en horas")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    resultado = simular(args.cp, args.horas, args.seed)
    print("\nResultados de la simulación:")
    for k, v in resultado.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
