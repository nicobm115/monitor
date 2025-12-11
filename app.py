import streamlit as st
import requests
import math
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor Ría de Vigo", page_icon="🌬️", layout="wide")

# --- LÓGICA ---
API_URL = "https://servizos.meteogalicia.gal/mgrss/observacion/ultimos10minEstacionsMeteo.action"
DISPLAY_STATIONS = [{"id": "10125", "name": "CÍES"}, {"id": "10906", "name": "CANGAS (Puerto)"}]
REF_TIERRA_ID = "10154" # O Viso

def mps_to_knots(mps): return float(mps) * 1.94384 if mps else 0.0

def calc_theta_v(t, hr, p):
    if t is None or hr is None or p is None: return None
    Tk = t + 273.15
    es = 6.112 * math.exp((17.67 * t) / (t + 243.5))
    e = (hr / 100.0) * es
    r = 0.622 * e / (p - e)
    Tv = Tk * (1 + 0.61 * r)
    return Tv * (1000.0 / p) ** 0.286

def get_wind_stream_color(knots):
    """Devuelve el nombre del color aceptado por Streamlit según la intensidad"""
    k = float(knots)
    if k < 4:   return "gray"    # Calma
    if k < 10:  return "blue"    # Suave
    if k < 16:  return "green"   # Fresquito (Ideal vela ligera)
    if k < 21:  return "yellow"  # Alegre
    if k < 27:  return "orange"  # Duro
    if k < 34:  return "red"     # Muy duro
    return "violet"              # Temporal

def get_cardinal(deg):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((deg + 11.25)/22.5)
    return dirs[ix % 16]

@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        ids = [s['id'] for s in DISPLAY_STATIONS] + [REF_TIERRA_ID]
        r = requests.get(API_URL, params={'idEst': ",".join(ids)}, timeout=5)
        r.raise_for_status()
        data = r.json()
        
        parsed_data = {}
        last_update = "N/D"
        
        if 'listUltimos10min' in data:
            for est in data['listUltimos10min']:
                sid = str(est['idEstacion'])
                last_update = est.get('instanteLecturaUTC', 'N/D')
                d = {'w_spd': 0, 'w_dir': 0, 'g_spd': 0, 'g_dir': 0, 'temp': 0, 'hr': 0, 'pres': 1013.25, 'std': 0}
                
                for m in est['listaMedidas']:
                    c = m['codigoParametro']; v = m['valor']
                    if c == 'VV_AVG_10m': d['w_spd'] = v
                    elif c == 'DV_AVG_10m': d['w_dir'] = v
                    elif c == 'VV_RACHA_10m': d['g_spd'] = v
                    elif c == 'DV_RACHA_10m': d['g_dir'] = v
                    elif 'TA_AVG_1.5m' in c: d['temp'] = v
                    elif 'HR_AVG_1.5m' in c: d['hr'] = v
                    elif 'PR_AVG_1.5m' in c: d['pres'] = v
                    elif 'DV_SD_10m' in c: d['std'] = v 
                
                if d['g_dir'] == 0 and d['w_dir'] != 0: d['g_dir'] = d['w_dir']
                parsed_data[sid] = d
                
        return parsed_data, last_update
    except:
        return None, None

# --- UI ---
st.title("🌬️ Monitor Ría de Vigo")
st.caption("Datos MeteoGalicia | @nicobm115")

if st.button("↻ Recargar datos", type="primary"):
    st.cache_data.clear()

data, timestamp = fetch_all_data()

if data:
    try:
        dt_utc = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        dt_local = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        st.markdown(f"🕒 **Última lectura:** `{dt_local.strftime('%H:%M')} Local`")
    except: pass

    st.divider()

    for st_conf in DISPLAY_STATIONS:
        sid = st_conf['id']
        d = data.get(sid)
        
        if d:
            st.subheader(f"📍 {st_conf['name']}")
            
            # Columnas para los datos
            c1, c2, c3, c4 = st.columns(4)
            
            # --- VIENTO MEDIO ---
            k_w = mps_to_knots(d['w_spd'])
            color_w = get_wind_stream_color(k_w)
            card_w = get_cardinal(d['w_dir'])
            
            with c1:
                st.markdown(f"**VIENTO MEDIO**")
                # Sintaxis nativa de Streamlit para fondo de color
                st.markdown(f"### :{color_w}-background[ &nbsp; {k_w:.1f} kn &nbsp; ]")
                st.caption(f"Dirección: **{d['w_dir']:.0f}° ({card_w})**")

            # --- RACHA ---
            k_g = mps_to_knots(d['g_spd'])
            color_g = get_wind_stream_color(k_g)
            card_g = get_cardinal(d['g_dir'])
            
            with c2:
                st.markdown(f"**RACHA MÁX**")
                # Sintaxis nativa de Streamlit para fondo de color
                st.markdown(f"### :{color_g}-background[ &nbsp; {k_g:.1f} kn &nbsp; ]")
                st.caption(f"Dirección: **{d['g_dir']:.0f}° ({card_g})**")

            # --- TURBULENCIA ---
            with c3:
                st.metric(label="Turbulencia (σ)", value=f"±{d['std']:.0f}°")

            # --- METEO ---
            with c4:
                st.metric(label="Temperatura", value=f"{d['temp']} °C", delta=f"{d['hr']}% HR")
                st.caption(f"Presión: {d['pres']:.0f} hPa")
            
            st.divider()

    # --- ANÁLISIS ---
    with st.expander("📊 ANÁLISIS TÉRMICO (Virazón vs Terral)", expanded=True):
        mar = data.get("10125")
        tierra = data.get("10154")
        
        if mar and tierra:
            th_mar = calc_theta_v(mar['temp'], mar['hr'], mar['pres'])
            th_tierra = calc_theta_v(tierra['temp'], tierra['hr'], tierra['pres'])
            
            if th_mar and th_tierra:
                diff = th_tierra - th_mar
                ac1, ac2, ac3 = st.columns(3)
                ac1.metric("Densidad Mar (θv)", f"{th_mar:.1f} K")
                ac2.metric("Densidad Tierra (θv)", f"{th_tierra:.1f} K")
                ac3.metric("Diferencia (Δ)", f"{diff:+.2f} K", delta_color="inverse")
                
                st.markdown("---")
                if diff > 1.5:
                    st.markdown(":green-background[**POSIBLE VIRAZÓN**] Tierra mucho más ligera. El aire frío del mar entrará acelerando.")
                elif diff < -1.5:
                    st.markdown(":orange-background[**POSIBLE BOCANA/TERRAL**] Tierra fría y densa.")
                else:
                    st.markdown(":gray-background[**ESTABILIDAD**] No hay gradiente térmico significativo.")
            else:
                st.error("Faltan datos de Presión/Humedad.")
        else:
            st.error("Datos de referencia no disponibles.")

else:
    st.error("Error conectando con MeteoGalicia.")
