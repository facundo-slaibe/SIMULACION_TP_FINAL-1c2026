# Simulación de una planta de soldadura automotriz

Trabajo práctico de simulación de eventos discretos para estudiar la producción de una planta de soldadura automotriz. El modelo permite comparar configuraciones de pedestales y operarios, medir el cumplimiento de la demanda, detectar colas y analizar la ociosidad de los recursos.

## Objetivo

La planta recibe pedidos de piezas que deben procesarse en pedestales productivos. El objetivo del modelo es evaluar cómo cambia el desempeño cuando se modifican:

- la cantidad de pedestales instalados (`CP`);
- la cantidad de operarios activos en cada turno (`CO_T1`, `CO_T2` y `CO_T3`);
- el horizonte y la semilla de la simulación.

La simulación busca identificar configuraciones capaces de absorber la demanda sin generar colas excesivas y evitando capacidad u operarios innecesariamente ociosos.

## Estructura del repositorio

| Archivo | Descripción |
| --- | --- |
| `simulacion_soldadura.py` | Motor de simulación, escenarios, métricas, salida por consola e historial de corridas. |
| `FDPs.py` | Lectura del Excel y ajuste de las funciones de distribución de probabilidad. |
| `Dataset.xlsx` | Fuente principal de datos reales, organizada en una hoja por pedestal. |
| `Dataset - Consolidado.csv` | Consolidación auxiliar del dataset. No es consumida actualmente por los scripts. |
| `resultados_simulacion.txt` | Historial acumulativo de las ejecuciones realizadas. |
| `Propuesta - Estudio...pdf` | Propuesta, problemática y análisis previo del trabajo práctico. |

## Dataset

El archivo `Dataset.xlsx` contiene registros reales de producción:

- 16 hojas, cada una correspondiente a un pedestal;
- 49.678 registros productivos;
- período comprendido entre el 2 de marzo y el 30 de junio de 2026;
- tres turnos: T1 con 18.659 registros, T2 con 17.186 y T3 con 13.833;
- 11 columnas: `FECHA`, `PEDESTAL`, `TURNO`, `HORA_INI`, `HORA_FIN`, `DURACION`, `EVENTO`, `DESCRIPCION`, `PZ1`, `PZR` y `USUARIO`;
- duración media aproximada de 14,52 minutos por registro;
- 1.677.113 piezas `PZ1` y 8.666 piezas rechazadas;
- tasa de rechazo observada de aproximadamente 0,517%.

El CSV consolidado contiene siete filas adicionales porque los registros de `PEDESTAL 12` están duplicados. Por ese motivo, el Excel es la fuente utilizada por `FDPs.py`.

## Variables del modelo

### Variables exógenas de datos

- `IAP`: intervalo de arribo de pedidos, en minutos.
- `TPROD`: tiempo de producción de un pedido, en minutos.
- `PS`: cantidad de piezas solicitadas por pedido.
- `PR`: cantidad de piezas rechazadas.

### Variables de control

- `CP`: cantidad de pedestales productivos instalados.
- `CO_T1`: operarios activos en el turno 1.
- `CO_T2`: operarios activos en el turno 2.
- `CO_T3`: operarios activos en el turno 3.

### Supuestos operativos

- Cada día se divide en tres turnos consecutivos de ocho horas.
- Cada pedestal ocupado requiere un único operario.
- La capacidad de un turno es `min(CP, operarios_del_turno)`.
- Los pedidos esperan en una cola FIFO cuando no hay capacidad disponible.
- La cola no tiene límite y los pedidos no se pierden ni abandonan el sistema.
- Un trabajo iniciado antes de un cambio de turno finaliza normalmente. Si la dotación disminuye, no comienza otro trabajo hasta respetar la nueva capacidad.
- La llegada de pedidos es independiente de la cantidad de pedestales y operarios.
- La simulación comienza con todos los pedestales libres y la cola vacía; actualmente no se aplica un período de calentamiento.

## Funciones de distribución

Las distribuciones fueron ajustadas con `FDPs.py` mediante la biblioteca `fitter`. Los parámetros seleccionados se encuentran copiados en `simulacion_soldadura.py`.

| Variable | Distribución | Parámetros utilizados |
| --- | --- | --- |
| IAP | Weibull mínima | `c=0.7464458702`, `loc=0.0166666667`, `scale=1.7327691344` |
| TPROD | Weibull mínima | `c=0.9056651700`, `loc=0.0166666667`, `scale=13.5160540792` |
| PS | Gamma | `a=0.3591010017`, `loc=0`, `scale=86.9232099980` |
| Rechazo | Binomial por pedido | `p=0.00517` |

El IAP se fuerza a un mínimo de 0,01 minutos, TPROD a 0,1 minutos y PS se redondea a un entero mínimo de una pieza.

Para el ajuste se consideran varias distribuciones candidatas: exponencial, gamma, lognormal, Weibull mínima, beta, chi-cuadrado, triangular y Cauchy envuelta. Los IAP iguales o superiores a 60 minutos y los TPROD iguales o superiores a 120 minutos se excluyen del ajuste.

## Funcionamiento de la simulación

El reloj avanza directamente al próximo evento. En cada iteración se selecciona el menor tiempo entre:

1. la próxima llegada;
2. la próxima finalización de un trabajo;
3. el próximo cambio de turno;
4. el final del horizonte.

Cuando llega un pedido se generan su cantidad de piezas, rechazos y duración. Si hay capacidad, se asigna al primer pedestal libre; en caso contrario queda en la cola. Cuando termina un trabajo, el pedestal se libera y puede recibir el siguiente pedido pendiente.

## Comparación justa entre escenarios

Todos los escenarios de una ejecución usan la misma semilla y reinician el generador aleatorio. Por lo tanto, reciben exactamente la misma secuencia de arribos, cantidades solicitadas, duraciones y rechazos.

Esto permite que las diferencias se deban solamente a la configuración de pedestales y operarios. Para estudiar la variabilidad aleatoria se recomienda ejecutar varias semillas, usando cada semilla en todos los escenarios antes de comparar promedios.

## Escenarios configurados

Los escenarios actuales son:

| Escenario | CP | T1 | T2 | T3 |
| --- | ---: | ---: | ---: | ---: |
| CP5-A | 5 | 5 | 5 | 5 |
| CP5-B | 5 | 4 | 4 | 4 |
| CP5-C | 5 | 5 | 4 | 4 |
| CP6 | 6 | 6 | 6 | 6 |
| CP7-A | 7 | 7 | 7 | 7 |
| CP7-B | 7 | 8 | 8 | 8 |
| CP7-C | 7 | 6 | 7 | 6 |
| CP7-D | 7 | 7 | 6 | 7 |
| CP8-A | 8 | 8 | 8 | 8 |
| CP8-B | 8 | 9 | 9 | 9 |
| CP8-C | 8 | 7 | 8 | 7 |
| CP8-D | 8 | 8 | 7 | 8 |
| CP10 | 10 | 10 | 9 | 10 |
| CP12-A | 12 | 12 | 11 | 10 |
| CP12-B | 12 | 8 | 8 | 8 |

Los escenarios pueden modificarse o ampliarse editando la lista `ESCENARIOS` de `simulacion_soldadura.py`.

## Métricas de salida

La tabla de resultados presenta:

| Columna | Significado |
| --- | --- |
| `ESC` | Nombre del escenario. |
| `CP` | Pedestales instalados. |
| `CO_T1`, `CO_T2`, `CO_T3` | Operarios programados por turno. |
| `CUMPLIMIENTO_%` | Piezas de pedidos completados respecto de las piezas solicitadas. |
| `PTO_%` | Porcentaje de tiempo ocioso de la capacidad de pedestales habilitada. |
| `PTO_O_%` | Porcentaje del tiempo total de operarios que no estuvo asociado a un pedestal ocupado. Incluye operarios excedentes. |
| `TR_%` | Piezas rechazadas sobre las piezas correspondientes a pedidos completados. |
| `PROD_H` | Promedio de piezas correspondientes a pedidos completados por hora simulada. |
| `COLA_FINAL` | Pedidos que permanecen en cola al terminar el horizonte. |

El resultado interno de `simular()` también conserva la cantidad de pedidos llegados, completados y en proceso, además de la cola máxima observada.

## Instalación

Se recomienda Python 3.10 o superior y un entorno virtual.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install numpy scipy openpyxl fitter pandas matplotlib
```

`numpy` y `scipy` son necesarios para ejecutar la simulación. `openpyxl` y `fitter`, junto con sus dependencias, se utilizan para volver a ajustar las distribuciones.

## Ejecución

### Ejecutar todos los escenarios

```powershell
python simulacion_soldadura.py
```

El horizonte predeterminado es de 8.640 horas, equivalente a 360 días, y la semilla predeterminada es `0`.

Para elegir otro horizonte o semilla:

```powershell
python simulacion_soldadura.py --horas 720
```

### Ejecutar un escenario manual

Los cuatro controles son obligatorios cuando se ejecuta un escenario manual:

```powershell
python simulacion_soldadura.py --cp 4 --co-t1 4 --co-t2 3 --co-t3 4
```

También pueden combinarse con `--horas` y `--seed`:

```powershell
python simulacion_soldadura.py --cp 8 --co-t1 8 --co-t2 7 --co-t3 8 --horas 2160 --seed 10
```

Los valores inválidos producen un error: CP y horas deben ser mayores que cero, y las cantidades de operarios no pueden ser negativas.

## Historial de resultados

Cada ejecución muestra los resultados en la consola y también agrega un bloque a `resultados_simulacion.txt`. El archivo se abre en modo append, por lo que nunca se sobrescriben las corridas anteriores.

Cada bloque registra:

- fecha, hora y zona horaria;
- tipo de corrida;
- horizonte simulado;
- semilla utilizada;
- tabla de resultados.

## Volver a ajustar las FDP

Para ejecutar el ajuste sobre `Dataset.xlsx`:

```powershell
python FDPs.py
```

También se puede indicar otro Excel:

```powershell
python FDPs.py ruta\al\dataset.xlsx
```

El script imprime los cinco mejores ajustes de cada variable, el mejor según el error cuadrático acumulado, la tasa de rechazo real y la cantidad de pedestales productivos encontrados. Los parámetros obtenidos deben trasladarse manualmente a `simulacion_soldadura.py`.

## Consideraciones del modelo

- IAP se obtiene ordenando los horarios de inicio de producción registrados; estos horarios se utilizan como aproximación de los arribos reales.
- TPROD y PS se generan actualmente como variables independientes.
- Las piezas rechazadas son un subconjunto de las piezas procesadas por los pedidos completados.
- Una única corrida no representa toda la variabilidad del sistema. Para conclusiones estadísticas deben realizarse múltiples réplicas con semillas diferentes y comparar promedios e intervalos de confianza.
- Los parámetros de las distribuciones no se actualizan automáticamente cuando cambia el dataset.

## Integrantes

- Facundo Slaibe
- Luciano Zunino
- Lucas Augusto Martin
- Melisa Perez
