# scripts/banxico_chart.py
import os, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # para CI sin display
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.animation import FuncAnimation, PillowWriter
from datetime import date
import banxicoapi

# ========= Config =========
TOKEN = os.environ["BANXICO_TOKEN"]  # defínelo como secret en el repo
SERIE_TASA = "SF282"     # CETES 28 días (promedio mensual, %)
SERIE_INFL = "SP30578"   # Inflación anual INPC (%)
FECHA_INI   = "1995-01-01"
FECHA_FIN   = date.today().isoformat()
OUT_GIF     = "assets/img/banxico/inflacion_vs_tasa.gif"

os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)

api = banxicoapi.BanxicoApi(TOKEN)

def fetch_series(serie_id, start, end):
    # api.get -> [{'idSerie','titulo','datos':[{'fecha':'dd/mm/aaaa','dato':'...'}, ...]}]
    res = api.get([serie_id], start_date=start, end_date=end)[0]
    rows = []
    for obs in res.get("datos", []):
        dato = str(obs.get("dato", "")).replace(",", "")
        if dato in ("N/E", "", None):
            continue
        try:
            v = float(dato)
        except ValueError:
            continue
        d = pd.to_datetime(obs["fecha"], dayfirst=True)
        rows.append((d, v))
    df = pd.DataFrame(rows, columns=["Date", serie_id]).sort_values("Date")
    # un punto por mes (fin de mes)
    df["M"] = df["Date"].dt.to_period("M")
    df = (df.groupby("M").tail(1)
            .assign(Date=lambda x: x["M"].dt.to_timestamp("M"))
            .drop(columns=["M"]))
    return df

# --- Datos y alineación ---
df_tasa = fetch_series(SERIE_TASA, FECHA_INI, FECHA_FIN)
df_infl = fetch_series(SERIE_INFL, FECHA_INI, FECHA_FIN)
df = pd.merge(df_infl, df_tasa, on="Date", how="inner").sort_values("Date").reset_index(drop=True)

# --- Animación GIF (30 s) ---
DURATION_S = 30
FPS = 20                    # 20 fps → 600 frames (tamaño razonable para GIF)
TOTAL_FRAMES = DURATION_S * FPS

n = len(df)
frame_idx = np.linspace(0, n - 1, num=TOTAL_FRAMES).astype(int)

fig, ax = plt.subplots(figsize=(10, 5))  # tamaño moderado para peso del GIF
ax.set_title("Inflación anual vs CETES 28 días (Banxico)")
ax.set_xlabel("Fecha")
ax.set_ylabel("Por ciento anual (%)")
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m'))
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_xlim(df["Date"].min(), df["Date"].max())
ymin = math.floor(min(df[SERIE_INFL].min(), df[SERIE_TASA].min()) - 1)
ymax = math.ceil(max(df[SERIE_INFL].max(), df[SERIE_TASA].max()) + 1)
ax.set_ylim(ymin, ymax)
line_infl, = ax.plot([], [], linewidth=2, label="Inflación anual (INPC)")
line_tasa, = ax.plot([], [], linewidth=2, label="CETES 28 días (prom. mensual)")
txt_infl = ax.text(0.02, 0.92, "", transform=ax.transAxes)
txt_tasa = ax.text(0.02, 0.86, "", transform=ax.transAxes)
ax.legend(loc="upper left")
fig.tight_layout()

def init():
    line_infl.set_data([], []); line_tasa.set_data([], [])
    txt_infl.set_text(""); txt_tasa.set_text("")
    return line_infl, line_tasa, txt_infl, txt_tasa

def animate(j):
    i = frame_idx[j]
    subset = df.iloc[: i + 1]
    line_infl.set_data(subset["Date"], subset[SERIE_INFL])
    line_tasa.set_data(subset["Date"], subset[SERIE_TASA])
    di = subset["Date"].iloc[-1].strftime("%Y-%m")
    txt_infl.set_text(f"{di}  Inflación: {subset[SERIE_INFL].iloc[-1]:.2f}%")
    txt_tasa.set_text(f"{di}  CETES 28d: {subset[SERIE_TASA].iloc[-1]:.2f}%")
    return line_infl, line_tasa, txt_infl, txt_tasa

anim = FuncAnimation(fig, animate, init_func=init, frames=TOTAL_FRAMES,
                     interval=1000 / FPS, blit=True)

# PillowWriter → no requiere ffmpeg
writer = PillowWriter(fps=FPS)
anim.save(OUT_GIF, writer=writer, dpi=110)
plt.close(fig)

print("Saved:", OUT_GIF)