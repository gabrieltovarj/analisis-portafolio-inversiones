"""
analisis_portafolio.py
======================

Herramienta reproducible para descargar precios históricos desde Yahoo Finance
(vía la librería `yfinance`) y calcular el **retorno de un portafolio** de
acciones con pesos definidos por el inversionista.

El script está diseñado como una **demostración reutilizable** del uso de
Python para el análisis de inversiones:

1. **Herramienta** — cualquier persona puede cambiar los tickers, los pesos y
   las fechas por línea de comandos y obtener el mismo análisis para su propia
   cartera.
2. **Caso de demostración** (valores por defecto) — retorno durante 2022 de un
   portafolio 30% CMPC / 30% Copec / 40% Cencosud (bolsa de Santiago, sufijo
   ``.SN``). Es el ejercicio de la tarea del curso *Mercado de Capitales*
   (MBA, Universidad Viña del Mar), planteado como demostración del flujo de
   trabajo, no como un fin en sí mismo.

Metodología resumida
--------------------
* Se usa el **precio de cierre ajustado** (``Adj Close``), que incorpora
  dividendos y splits y es el insumo correcto para medir el retorno total
  del accionista (Bacon, 2008; Meucci, 2010).
* El **retorno simple** mensual del activo *i* en el mes *t* es
  ``R_{i,t} = P_{i,t} / P_{i,t-1} - 1``.
* Se reportan dos convenciones de retorno del portafolio, ambas estándar en
  la literatura de *performance measurement* (Bacon, 2008):

  - **Comprar y mantener (buy & hold):** se invierte una sola vez al
    inicio del período con los pesos objetivo y no se vuelve a operar. El
    retorno del período es el promedio ponderado de los retornos totales
    de cada activo usando los pesos **iniciales**:
    ``R_p = Σ w_i · R_i``.
  - **Rebalanceo mensual:** al comienzo de cada mes la cartera se lleva de
    vuelta a los pesos objetivo; el retorno del período es la
    capitalización (producto) de los retornos mensuales del portafolio
    ``R_{p,t} = Σ w_i · R_{i,t}``.

* Como métricas de riesgo se reportan la volatilidad (desviación estándar)
  mensual y anualizada, y la matriz de correlaciones — los ingredientes del
  marco media-varianza de Markowitz (1952).

Uso
---
Reproducir el caso de demostración (valores por defecto)::

    python src/analisis_portafolio.py

Analizar otra cartera::

    python src/analisis_portafolio.py \
        --tickers AAPL MSFT NVDA \
        --pesos 0.4 0.4 0.2 \
        --inicio 2023-01-01 --fin 2023-12-31 --intervalo 1mo

Referencias
-----------
Ver ``docs/METODOLOGIA.md`` y ``docs/referencias.bib``.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# En la consola de Windows (cp1252) forzamos UTF-8 para que los acentos y el
# signo de la tabla se impriman correctamente.
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream is not None and (_stream.encoding or "").lower() not in ("utf-8", "utf8"):
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        pass

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    sys.exit(
        "Falta la dependencia 'yfinance'. Instala los requisitos con:\n"
        "    pip install -r requirements.txt"
    )


# --------------------------------------------------------------------------- #
# Parámetros del caso de demostración (valores por defecto)                   #
# --------------------------------------------------------------------------- #
TICKERS_EJERCICIO = ["CMPC.SN", "COPEC.SN", "CENCOSUD.SN"]
PESOS_EJERCICIO = [0.30, 0.30, 0.40]
# Se descarga desde diciembre de 2021 para tener el precio base con el que se
# calcula el primer retorno mensual de 2022.
INICIO_EJERCICIO = "2021-12-01"
FIN_EJERCICIO = "2022-12-31"
INTERVALO_EJERCICIO = "1mo"


@dataclass
class ResultadoPortafolio:
    """Contenedor de resultados del análisis."""

    precios: pd.DataFrame
    retornos_activos: pd.DataFrame
    retornos_portafolio_mensual: pd.Series
    pesos: pd.Series
    retorno_anual_por_activo: pd.Series
    retorno_buy_and_hold: float
    retorno_rebalanceo: float
    volatilidad_mensual: float
    volatilidad_anualizada: float
    correlaciones: pd.DataFrame
    periodo: tuple[str, str]
    metadatos: dict = field(default_factory=dict)

    # ---- serialización -------------------------------------------------- #
    def resumen(self) -> dict:
        return {
            "periodo": {"inicio": self.periodo[0], "fin": self.periodo[1]},
            "pesos": self.pesos.round(4).to_dict(),
            "retorno_anual_por_activo_pct": (self.retorno_anual_por_activo * 100)
            .round(2)
            .to_dict(),
            "retorno_portafolio_buy_and_hold_pct": round(self.retorno_buy_and_hold * 100, 2),
            "retorno_portafolio_rebalanceo_mensual_pct": round(self.retorno_rebalanceo * 100, 2),
            "volatilidad_mensual_pct": round(self.volatilidad_mensual * 100, 2),
            "volatilidad_anualizada_pct": round(self.volatilidad_anualizada * 100, 2),
            "correlaciones": self.correlaciones.round(3).to_dict(),
            **self.metadatos,
        }


# --------------------------------------------------------------------------- #
# Descarga de datos                                                            #
# --------------------------------------------------------------------------- #
def descargar_precios(
    tickers: list[str],
    inicio: str,
    fin: str,
    intervalo: str = "1mo",
    columna_precio: str = "Adj Close",
) -> pd.DataFrame:
    """Descarga precios históricos desde Yahoo Finance.

    Parameters
    ----------
    tickers:
        Símbolos de Yahoo Finance. Para la bolsa de Santiago se usa el
        sufijo ``.SN`` (p. ej. ``CMPC.SN``).
    inicio, fin:
        Fechas ``YYYY-MM-DD``. ``fin`` es exclusivo en la API de Yahoo, por
        lo que internamente se suma un día para incluir el último mes.
    intervalo:
        ``1d``, ``1wk`` o ``1mo``.
    columna_precio:
        ``"Adj Close"`` (recomendado) o ``"Close"``.

    Returns
    -------
    pandas.DataFrame
        Índice = fechas; columnas = tickers (en el orden solicitado).
    """
    fin_incl = (pd.Timestamp(fin) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    crudo = yf.download(
        tickers,
        start=inicio,
        end=fin_incl,
        interval=intervalo,
        auto_adjust=False,
        progress=False,
        group_by="column",
    )
    if crudo.empty:
        raise RuntimeError(
            "Yahoo Finance no devolvió datos. Revisa los tickers, el rango "
            "de fechas y tu conexión a internet."
        )

    if isinstance(crudo.columns, pd.MultiIndex):
        if columna_precio not in crudo.columns.get_level_values(0):
            raise KeyError(f"La columna '{columna_precio}' no está disponible.")
        precios = crudo[columna_precio].copy()
    else:  # un solo ticker: columnas planas
        precios = crudo[[columna_precio]].copy()
        precios.columns = tickers

    # Reordenar/filtrar a los tickers pedidos y recortar al período exacto.
    precios = precios.reindex(columns=[t for t in tickers if t in precios.columns])
    precios = precios.loc[(precios.index >= inicio) & (precios.index <= fin)]
    precios = precios.dropna(how="all").dropna()
    precios.index.name = "Fecha"
    return precios


# --------------------------------------------------------------------------- #
# Cálculos de retorno                                                          #
# --------------------------------------------------------------------------- #
def retornos_simples(precios: pd.DataFrame) -> pd.DataFrame:
    """Retornos simples período a período: ``P_t / P_{t-1} - 1``."""
    return precios.pct_change().dropna(how="all")


def retornos_log(precios: pd.DataFrame) -> pd.DataFrame:
    """Retornos logarítmicos: ``ln(P_t / P_{t-1})`` (útil para verificación)."""
    return np.log(precios / precios.shift(1)).dropna(how="all")


def normalizar_pesos(pesos: list[float], tickers: list[str]) -> pd.Series:
    s = pd.Series(dict(zip(tickers, pesos)), dtype="float64")
    total = s.sum()
    if not np.isclose(total, 1.0):
        print(
            f"[aviso] Los pesos suman {total:.4f}; se normalizan para que sumen 1.",
            file=sys.stderr,
        )
        s = s / total
    return s


def retorno_buy_and_hold(retorno_total_activo: pd.Series, pesos: pd.Series) -> float:
    """Retorno del portafolio comprar-y-mantener: ``Σ w_i · R_i``."""
    pesos = pesos.reindex(retorno_total_activo.index)
    return float((pesos * retorno_total_activo).sum())


def retorno_rebalanceo(retornos_activos: pd.DataFrame, pesos: pd.Series) -> tuple[float, pd.Series]:
    """Retorno con rebalanceo a los pesos objetivo al inicio de cada período.

    Returns
    -------
    (retorno_periodo, serie_de_retornos_del_portafolio)
    """
    pesos = pesos.reindex(retornos_activos.columns)
    retorno_port_periodo = (retornos_activos * pesos).sum(axis=1)
    retorno_acumulado = float((1.0 + retorno_port_periodo).prod() - 1.0)
    return retorno_acumulado, retorno_port_periodo


# --------------------------------------------------------------------------- #
# Orquestación                                                                 #
# --------------------------------------------------------------------------- #
def analizar_portafolio(
    tickers: list[str],
    pesos: list[float],
    inicio: str,
    fin: str,
    intervalo: str = "1mo",
    columna_precio: str = "Adj Close",
    periodos_por_anio: int = 12,
) -> ResultadoPortafolio:
    """Ejecuta el análisis completo y devuelve un :class:`ResultadoPortafolio`."""
    precios = descargar_precios(tickers, inicio, fin, intervalo, columna_precio)
    tickers_ok = list(precios.columns)
    if len(tickers_ok) < len(tickers):
        faltan = set(tickers) - set(tickers_ok)
        print(f"[aviso] Sin datos para: {', '.join(sorted(faltan))}", file=sys.stderr)

    pesos_s = normalizar_pesos(pesos, tickers)
    pesos_s = pesos_s.reindex(tickers_ok)
    pesos_s = pesos_s / pesos_s.sum()  # renormaliza si se cayó algún ticker

    rets = retornos_simples(precios)
    retorno_anual_activo = precios.iloc[-1] / precios.iloc[0] - 1.0

    bh = retorno_buy_and_hold(retorno_anual_activo, pesos_s)
    reb, port_mensual = retorno_rebalanceo(rets, pesos_s)

    vol_m = float(port_mensual.std(ddof=1))
    vol_a = vol_m * np.sqrt(periodos_por_anio)

    return ResultadoPortafolio(
        precios=precios,
        retornos_activos=rets,
        retornos_portafolio_mensual=port_mensual,
        pesos=pesos_s,
        retorno_anual_por_activo=retorno_anual_activo,
        retorno_buy_and_hold=bh,
        retorno_rebalanceo=reb,
        volatilidad_mensual=vol_m,
        volatilidad_anualizada=vol_a,
        correlaciones=rets.corr(),
        periodo=(str(precios.index[0].date()), str(precios.index[-1].date())),
        metadatos={
            "tickers": tickers_ok,
            "columna_precio": columna_precio,
            "intervalo": intervalo,
            "n_observaciones_precio": int(len(precios)),
            "n_retornos": int(len(rets)),
        },
    )


# --------------------------------------------------------------------------- #
# Salidas: consola, archivos, gráfico                                          #
# --------------------------------------------------------------------------- #
def imprimir_reporte(res: ResultadoPortafolio) -> None:
    ini, fin = res.periodo
    print("=" * 70)
    print("ANÁLISIS DE RETORNO DEL PORTAFOLIO")
    print("=" * 70)
    print(f"Período analizado : {ini}  ->  {fin}")
    print(f"Precio utilizado  : {res.metadatos['columna_precio']} "
          f"(intervalo {res.metadatos['intervalo']})")
    print(f"Observaciones     : {res.metadatos['n_observaciones_precio']} precios, "
          f"{res.metadatos['n_retornos']} retornos\n")

    tabla = pd.DataFrame(
        {
            "Peso": res.pesos,
            "Retorno período (%)": (res.retorno_anual_por_activo * 100).round(2),
            "Contribución (%)": (res.pesos * res.retorno_anual_por_activo * 100).round(2),
        }
    )
    print("Por activo (comprar y mantener):")
    print(tabla.to_string())
    print("-" * 70)
    print(f"{'RETORNO DEL PORTAFOLIO — comprar y mantener':50s}: "
          f"{res.retorno_buy_and_hold * 100:7.2f} %")
    print(f"{'RETORNO DEL PORTAFOLIO — rebalanceo mensual':50s}: "
          f"{res.retorno_rebalanceo * 100:7.2f} %")
    print("-" * 70)
    print(f"{'Volatilidad mensual del portafolio':50s}: "
          f"{res.volatilidad_mensual * 100:7.2f} %")
    print(f"{'Volatilidad anualizada del portafolio':50s}: "
          f"{res.volatilidad_anualizada * 100:7.2f} %")
    print("\nMatriz de correlaciones (retornos mensuales):")
    print(res.correlaciones.round(3).to_string())
    print("=" * 70)


def guardar_resultados(res: ResultadoPortafolio, dir_datos: Path, dir_resultados: Path) -> None:
    dir_datos.mkdir(parents=True, exist_ok=True)
    dir_resultados.mkdir(parents=True, exist_ok=True)

    res.precios.to_csv(dir_datos / "precios_historicos.csv")
    (res.retornos_activos * 100).round(4).to_csv(dir_datos / "retornos_mensuales_activos.csv")

    resumen_port = pd.DataFrame(
        {
            "retorno_portafolio_mensual_%": (res.retornos_portafolio_mensual * 100).round(4),
        }
    )
    resumen_port.to_csv(dir_resultados / "retornos_mensuales_portafolio.csv")

    with open(dir_resultados / "resumen.json", "w", encoding="utf-8") as fh:
        json.dump(res.resumen(), fh, indent=2, ensure_ascii=False)

    print(f"\nArchivos escritos en '{dir_datos}/' y '{dir_resultados}/'.")


def graficar(res: ResultadoPortafolio, ruta_png: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[aviso] matplotlib no está instalado; se omite el gráfico.", file=sys.stderr)
        return

    ruta_png.parent.mkdir(parents=True, exist_ok=True)

    # Valor de $100 invertidos, base = primer precio.
    base = res.precios.iloc[0]
    valor_activos = res.precios / base * 100.0
    valor_port = (1.0 + res.retornos_portafolio_mensual).cumprod() * 100.0
    valor_port.loc[res.precios.index[0]] = 100.0
    valor_port = valor_port.sort_index()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9))

    for col in valor_activos.columns:
        ax1.plot(valor_activos.index, valor_activos[col], marker="o", ms=3, label=col)
    ax1.plot(valor_port.index, valor_port.values, color="black", lw=2.5,
             label="Portafolio (rebalanceo mensual)")
    ax1.axhline(100, color="grey", ls="--", lw=1)
    ax1.set_title("Evolución de $100 invertidos")
    ax1.set_ylabel("Valor (base 100)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    colores = ["#2a9d8f" if v >= 0 else "#e76f51"
               for v in res.retornos_portafolio_mensual.values]
    ax2.bar(range(len(res.retornos_portafolio_mensual)),
            res.retornos_portafolio_mensual.values * 100, color=colores)
    ax2.set_xticks(range(len(res.retornos_portafolio_mensual)))
    ax2.set_xticklabels([d.strftime("%Y-%m") for d in res.retornos_portafolio_mensual.index],
                        rotation=45, ha="right")
    ax2.axhline(0, color="black", lw=1)
    ax2.set_title("Retorno mensual del portafolio")
    ax2.set_ylabel("%")
    ax2.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(ruta_png, dpi=120)
    plt.close(fig)
    print(f"Gráfico guardado en '{ruta_png}'.")


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Analiza el retorno de un portafolio de acciones con datos de Yahoo Finance.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--tickers", nargs="+", default=TICKERS_EJERCICIO,
                   help="Símbolos de Yahoo Finance.")
    p.add_argument("--pesos", nargs="+", type=float, default=PESOS_EJERCICIO,
                   help="Pesos del portafolio (mismo orden que --tickers; se normalizan a 1).")
    p.add_argument("--inicio", default=INICIO_EJERCICIO, help="Fecha inicial YYYY-MM-DD.")
    p.add_argument("--fin", default=FIN_EJERCICIO, help="Fecha final YYYY-MM-DD (inclusive).")
    p.add_argument("--intervalo", default=INTERVALO_EJERCICIO, choices=["1d", "1wk", "1mo"],
                   help="Frecuencia de los datos.")
    p.add_argument("--precio", default="Adj Close", choices=["Adj Close", "Close"],
                   help="Columna de precio a utilizar.")
    p.add_argument("--periodos-anio", type=int, default=12,
                   help="Períodos por año para anualizar la volatilidad (12 mensual, 252 diario).")
    p.add_argument("--dir-datos", default="data", help="Carpeta para los CSV de datos.")
    p.add_argument("--dir-resultados", default="results", help="Carpeta para resultados y gráfico.")
    p.add_argument("--sin-grafico", action="store_true", help="No generar el gráfico PNG.")
    p.add_argument("--sin-archivos", action="store_true", help="Solo imprimir en consola.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if len(args.pesos) != len(args.tickers):
        print("Error: --pesos y --tickers deben tener la misma longitud.", file=sys.stderr)
        return 2

    res = analizar_portafolio(
        tickers=args.tickers,
        pesos=args.pesos,
        inicio=args.inicio,
        fin=args.fin,
        intervalo=args.intervalo,
        columna_precio=args.precio,
        periodos_por_anio=args.periodos_anio,
    )

    imprimir_reporte(res)

    if not args.sin_archivos:
        guardar_resultados(res, Path(args.dir_datos), Path(args.dir_resultados))
    if not args.sin_grafico:
        graficar(res, Path(args.dir_resultados) / "portafolio.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
