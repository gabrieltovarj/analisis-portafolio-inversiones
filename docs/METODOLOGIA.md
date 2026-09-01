# Metodología

Este documento describe, paso a paso y con su fundamento en la literatura
financiera, cómo la herramienta calcula el retorno de un portafolio. Se usa
como hilo conductor el **caso de demostración**: el ejercicio de la tarea del
curso *Mercado de Capitales* (MBA, Universidad Viña del Mar), planteado como
demostración del uso de Python para el análisis de inversiones.

---

## 1. Datos de entrada

### 1.1 Fuente

Los precios provienen de **Yahoo Finance**, obtenidos con la librería de código
abierto [`yfinance`](https://github.com/ranaroussi/yfinance) (Aroussi, 2024).
Es la misma fuente y el mismo proveedor de datos que indican las instrucciones
del ejercicio.

### 1.2 Instrumentos

| Ticker (Yahoo) | Empresa | Bolsa | Sector |
|----------------|---------|-------|--------|
| `CMPC.SN` | Empresas CMPC S.A. | Santiago (Chile) | Celulosa y papel |
| `COPEC.SN` | Empresas Copec S.A. | Santiago (Chile) | Energía / forestal |
| `CENCOSUD.SN` | Cencosud S.A. | Santiago (Chile) | Retail |

El sufijo `.SN` identifica a la Bolsa de Comercio de Santiago dentro de la
nomenclatura de Yahoo Finance. Los precios están expresados en **pesos
chilenos (CLP)**; como el análisis es de **retornos porcentuales**, la moneda
no afecta el resultado siempre que las tres series estén en la misma moneda
(lo están).

### 1.3 Frecuencia y ventana temporal

* **Frecuencia:** mensual (`interval = "1mo"`), tal como pide el ejercicio.
* **Ventana:** se descarga desde **diciembre de 2021** hasta **diciembre de
  2022**. El precio de cierre de diciembre de 2021 es el **precio base**
  necesario para calcular el retorno del primer mes de 2022. Resultan
  **13 observaciones de precio** y **12 retornos mensuales** (enero–diciembre
  de 2022).

> **Nota sobre las fechas del enunciado.** Los enlaces de Yahoo Finance del
> enunciado usan un rango aproximado 22-nov-2021 a 22-nov-2022
> (`period1`/`period2` en formato *epoch*). La pregunta, sin embargo, es por
> **"el año 2022"**, por lo que aquí se usa el **año calendario completo**
> (dic-2021 como base → dic-2022). La herramienta permite cambiar la ventana
> con `--inicio` y `--fin` si se desea replicar exactamente el rango de los
> enlaces.

### 1.4 Precio de cierre ajustado vs. precio de cierre

Se utiliza el **precio de cierre ajustado** (`Adj Close`). El cierre ajustado
corrige el precio por **dividendos** y **splits**, de modo que la variación
del precio ajustado refleja el **retorno total** que obtiene el accionista, no
solo la ganancia de capital (Bacon, 2008; Bodie, Kane & Marcus, 2014). Usar el
cierre simple (`Close`) subestima el retorno en los meses con reparto de
dividendos. La herramienta acepta `--precio Close` para comparar.

En este conjunto de datos la diferencia es material: con cierre ajustado el
portafolio rinde **+1,41 %** y con cierre simple **−2,27 %** en 2022. La
diferencia corresponde, esencialmente, a los dividendos repartidos por las
tres compañías durante el año.

---

## 2. Cálculo de retornos de cada activo

### 2.1 Retorno simple mensual

Para el activo $i$ en el mes $t$:

$$
R_{i,t} \;=\; \frac{P_{i,t}}{P_{i,t-1}} - 1
$$

donde $P_{i,t}$ es el cierre ajustado de fin de mes.

### 2.2 Retorno anual del activo (comprar y mantener)

El retorno de todo el período 2022 para el activo $i$ se obtiene componiendo
los 12 retornos mensuales, lo que equivale a comparar el precio final con el
inicial:

$$
R_i^{2022} \;=\; \prod_{t=1}^{12}\bigl(1 + R_{i,t}\bigr) - 1
\;=\; \frac{P_{i,\text{dic-2022}}}{P_{i,\text{dic-2021}}} - 1
$$

Resultado con los datos descargados:

| Activo | $P$ dic-2021 | $P$ dic-2022 | $R_i^{2022}$ |
|--------|-------------:|-------------:|------------:|
| CMPC.SN | 1 415,44 | 1 403,63 | **−0,83 %** |
| COPEC.SN | 6 465,57 | 6 213,69 | **−3,90 %** |
| CENCOSUD.SN | 1 186,46 | 1 270,42 | **+7,08 %** |

*(Los valores de Yahoo Finance pueden variar en decimales con el tiempo, porque
el proveedor recalcula el factor de ajuste cada vez que hay un nuevo
dividendo. El orden de magnitud y la conclusión no cambian.)*

---

## 3. Retorno del portafolio

Los pesos objetivo del ejercicio son:

$$
w_{\text{CMPC}} = 0{,}30 \qquad
w_{\text{COPEC}} = 0{,}30 \qquad
w_{\text{CENCOSUD}} = 0{,}40
\qquad \sum_i w_i = 1
$$

La herramienta reporta **dos convenciones**, ambas estándar en la medición de
desempeño de carteras (Bacon, 2008). Cuál es "la correcta" depende de qué
supuesto de gestión se asuma.

### 3.1 Comprar y mantener (*buy & hold*) — respuesta principal

Se invierte **una sola vez** a fines de 2021 con los pesos objetivo y no se
vuelve a operar en el año. El retorno del período es el **promedio ponderado
de los retornos anuales** de cada activo, usando los **pesos iniciales**:

$$
R_p^{2022} \;=\; \sum_{i} w_i \, R_i^{2022}
$$

$$
R_p^{2022} = 0{,}30(-0{,}83\%) + 0{,}30(-3{,}90\%) + 0{,}40(+7{,}08\%)
= \mathbf{+1{,}41\,\%}
$$

Contribución de cada posición al retorno del portafolio
($w_i \cdot R_i^{2022}$):

| Activo | Contribución |
|--------|-------------:|
| CMPC.SN | −0,25 pp |
| COPEC.SN | −1,17 pp |
| CENCOSUD.SN | +2,83 pp |
| **Portafolio** | **+1,41 pp** |

> Estrictamente, en una estrategia de comprar y mantener los pesos se
> desvían de 30/30/40 a lo largo del año a medida que cada acción se mueve.
> La fórmula $\sum_i w_i R_i$ con pesos iniciales es la definición contable
> habitual del retorno *buy & hold* del período y es la que se espera como
> respuesta en el ejercicio.

### 3.2 Rebalanceo mensual

Al inicio de cada mes la cartera se lleva de vuelta a 30/30/40. El retorno del
portafolio en el mes $t$ es:

$$
R_{p,t} \;=\; \sum_i w_i \, R_{i,t}
$$

y el retorno del año se obtiene componiendo esos 12 retornos:

$$
R_p^{2022} \;=\; \prod_{t=1}^{12}\bigl(1 + R_{p,t}\bigr) - 1 \;=\; \mathbf{+2{,}73\,\%}
$$

El rebalanceo mensual rinde algo más aquí porque obliga a "vender caro y
comprar barato" mes a mes (efecto de *diversification return* / *volatility
pumping*); no es un resultado general.

### 3.3 Verificación con retornos logarítmicos

Como control, se calculan también los retornos logarítmicos
$r_{i,t} = \ln(P_{i,t}/P_{i,t-1})$. Los retornos log **no** son aditivos entre
activos, pero sí en el tiempo, por lo que sirven para verificar la
composición temporal (Meucci, 2010). La conversión del retorno log acumulado
del portafolio a retorno simple da **≈ +1,3 %**, coherente con el resultado
*buy & hold*.

---

## 4. Métricas de riesgo

Aunque el ejercicio solo pide el retorno, la herramienta reporta el riesgo
porque es la otra mitad del marco media–varianza de Markowitz (1952): una
cartera se juzga por su **par (retorno, riesgo)**, no por el retorno solo.

* **Volatilidad mensual del portafolio** (desviación estándar de $R_{p,t}$,
  con $n-1$ grados de libertad): **≈ 5,4 %**.
* **Volatilidad anualizada:** $\sigma_{\text{mensual}} \times \sqrt{12}
  \approx$ **18,8 %**.
* **Matriz de correlaciones** de los retornos mensuales:

  | | CMPC | COPEC | CENCOSUD |
  |--|--:|--:|--:|
  | **CMPC** | 1,00 | 0,75 | 0,05 |
  | **COPEC** | 0,75 | 1,00 | 0,24 |
  | **CENCOSUD** | 0,05 | 0,24 | 1,00 |

  CMPC y Copec (ambas forestales/celulosa) están fuertemente correlacionadas
  (0,75); Cencosud (retail) apenas se correlaciona con ellas, de modo que
  aporta la mayor parte del beneficio de diversificación de la cartera
  (Markowitz, 1952; DeMiguel, Garlappi & Uppal, 2009).

---

## 5. Respuesta del ejercicio

> **¿Cuál fue el retorno del portafolio durante el año 2022?**
>
> Con precios de cierre **ajustados** de Yahoo Finance y los pesos 30 % CMPC /
> 30 % Copec / 40 % Cencosud:
>
> * **Comprar y mantener: ≈ +1,4 % en 2022.**
> * Rebalanceo mensual: ≈ +2,7 % en 2022.
>
> El resultado positivo se explica íntegramente por Cencosud (+7,1 %), que
> compensó las caídas de CMPC (−0,8 %) y Copec (−3,9 %). Medido con el cierre
> **sin ajustar** (solo ganancia de capital, sin dividendos) el portafolio
> habría rendido ≈ −2,3 %.

---

## 6. Limitaciones

1. **Datos de un único proveedor.** No se contrastan con una segunda fuente
   (p. ej. la Bolsa de Santiago). Yahoo Finance ajusta retroactivamente sus
   series.
2. **Sin costos ni impuestos.** No se descuentan comisiones de corretaje,
   *spread* ni impuesto a los dividendos o a las ganancias de capital.
3. **Sin tipo de cambio.** El análisis es en CLP; un inversionista en otra
   moneda debe añadir el retorno cambiario.
4. **Rendimiento pasado.** El ejercicio es descriptivo (*ex post*); no es una
   proyección ni una recomendación de inversión.
5. **Frecuencia mensual.** 12 observaciones son pocas para estimar con
   precisión la volatilidad y las correlaciones; úsense como orden de
   magnitud.

---

## 7. Referencias

Las referencias completas, en formato BibTeX, están en
[`referencias.bib`](referencias.bib).

* Markowitz, H. M. (1952). *Portfolio Selection.* The Journal of Finance, 7(1), 77–91.
* Sharpe, W. F. (1964). *Capital Asset Prices.* The Journal of Finance, 19(3), 425–442.
* Lintner, J. (1965). *The Valuation of Risk Assets…* The Review of Economics and Statistics, 47(1), 13–37.
* Jensen, M. C. (1968). *The Performance of Mutual Funds in the Period 1945–1964.* The Journal of Finance, 23(2), 389–416.
* Brinson, G. P., Hood, L. R., & Beebower, G. L. (1986). *Determinants of Portfolio Performance.* Financial Analysts Journal, 42(4), 39–44.
* Fama, E. F., & French, K. R. (1993). *Common risk factors in the returns on stocks and bonds.* Journal of Financial Economics, 33(1), 3–56.
* Fama, E. F., & French, K. R. (2004). *The Capital Asset Pricing Model: Theory and Evidence.* Journal of Economic Perspectives, 18(3), 25–46.
* DeMiguel, V., Garlappi, L., & Uppal, R. (2009). *Optimal Versus Naive Diversification.* The Review of Financial Studies, 22(5), 1915–1953.
* Meucci, A. (2010). *Linear vs. Compounded Returns – Common Pitfalls in Portfolio Management.* GARP Risk Professional, April 2010, 49–51.
* Bacon, C. R. (2008). *Practical Portfolio Performance Measurement and Attribution* (2nd ed.). Wiley.
* Bodie, Z., Kane, A., & Marcus, A. J. (2014). *Investments* (10th ed.). McGraw-Hill.
* McKinney, W. (2010). *Data Structures for Statistical Computing in Python.* Proc. 9th Python in Science Conf., 56–61.
* Harris, C. R., et al. (2020). *Array programming with NumPy.* Nature, 585, 357–362.
* Hunter, J. D. (2007). *Matplotlib: A 2D Graphics Environment.* Computing in Science & Engineering, 9(3), 90–95.
