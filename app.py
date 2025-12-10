import streamlit as st
import requests
import math
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor Ría de Vigo", page_icon="🌬️", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .metric-card {
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: scale(1.02); }
    .big-font { font-size: 24px; font-weight: bold; margin: 5px 0; }
    .small-font { font-size: 12px; font-weight: bold; text-transform: uppercase; opacity: 0.9; }
    .dir-font { font-size: 14px; opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

# --- LÓGICA ---
API_URL = "https://servizos.meteogalicia.gal/mgrss/observacion/ultimos10minEstacionsMeteo.action"
DISPLAY_STATIONS = [{"id": "10125", "name": "CÍES "}, {"id": "10906", "name": "CANGAS (Puerto)"}]
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

def get_wind_color(knots):
    """Devuelve (Fondo, Texto)"""
    k = float(knots)
    if k < 3:   return "#FFFFFF", "#000000" # Calma
    if k < 6:   return "#E1F5FE", "#000000"
    if k < 9:   return "#81D4FA", "#000000"
    if k < 12:  return "#00FFBF", "#000000" # Azul intenso
    if k < 16:  return "#76FF03", "#000000" # Verde Lima
    if k < 20:  return "#FFEA00", "#000000" # Amarillo
    if k < 25:  return "#FF9100", "#000000" # Naranja
    if k < 30:  return "#D50000", "#FFFFFF" # Rojo (Texto Blanco)
    return "#4A148C", "#FFFFFF"             # Morado (Texto Blanco)

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
st.caption("@nicobm115-Datos MeteoGalicia")

if st.button("↻ Actualizar Datos"):
    st.cache_data.clear()

data, timestamp = fetch_all_data()

if data:
    try:
        dt_utc = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        dt_local = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        st.markdown(f"**Última lectura:** `{dt_local.strftime('%H:%M')} Local`")
    except: pass

    for st_conf in DISPLAY_STATIONS:
        sid = st_conf['id']
        d = data.get(sid)
        
        if d:
            st.markdown(f"### 📍 {st_conf['name']}")
            c1, c2, c3, c4 = st.columns([1.2, 1.2, 0.8, 1])
            
            # --- VIENTO MEDIO (CORREGIDO) ---
            k_w = mps_to_knots(d['w_spd'])
            # 1. Desempaquetamos la tupla en DOS variables
            bg_w, txt_w = get_wind_color(k_w) 
            rot_w = d['w_dir'] 
            
            with c1:
                # 2. Inyectamos bg_w en background-color y txt_w en color
                st.markdown(f"""
                <div class="metric-card" style="background-color: {bg_w} !important; color: {txt_w} !important;">
                    <div class="small-font" style="color: {txt_w} !important;">VIENTO MEDIO</div>
                    <div class="big-font" style="color: {txt_w} !important;">{k_w:.1f} kn</div>
                    <div style="transform: rotate({rot_w}deg); font-size: 35px; line-height: 35px; color: {txt_w} !important;">⬇</div>
                    <div class="dir-font" style="color: {txt_w} !important;">{d['w_dir']:.0f}°</div>
                </div>
                """, unsafe_allow_html=True)

            # --- RACHA (CORREGIDO) ---
            k_g = mps_to_knots(d['g_spd'])
            # 1. Desempaquetamos la tupla
            bg_g, txt_g = get_wind_color(k_g)
            rot_g = d['g_dir']
            
            with c2:
                # 2. Inyectamos los colores
                st.markdown(f"""
                <div class="metric-card" style="background-color: {bg_g} !important; color: {txt_g} !important;">
                    <div class="small-font" style="color: {txt_g} !important;">RACHA MÁX</div>
                    <div class="big-font" style="color: {txt_g} !important;">{k_g:.1f} kn</div>
                    <div style="transform: rotate({rot_g}deg); font-size: 35px; line-height: 35px; color: {txt_g} !important;">⬇</div>
                    <div class="dir-font" style="color: {txt_g} !important;">{d['g_dir']:.0f}°</div>
                </div>
                """, unsafe_allow_html=True)

            # --- TURBULENCIA ---
            with c3:
                st.markdown(f"""
                <div class="metric-card" style="background-color: #37474F; color: #B0BEC5;">
                    <div class="small-font" style="color: #90A4AE;">Turbulencia</div>
                    <div class="big-font" style="color: #ECEFF1;">±{d['std']:.0f}°</div>
                    <div class="dir-font" style="margin-top:15px">Desviación σ</div>
                </div>
                """, unsafe_allow_html=True)

            # --- METEO ---
            with c4:
                st.markdown(f"""
                <div class="metric-card" style="background-color: #263238; border: 1px solid #37474F;">
                    <div class="small-font" style="color: #90A4AE;">Atmósfera</div>
                    <div style="font-size: 26px; font-weight:bold; color: #FDD835; margin: 5px 0;">{d['temp']} °C</div>
                    <div style="color: #80CBC4; font-weight:bold;">HR: {d['hr']}%</div>
                    <div style="color: #AAA; font-size: 11px; margin-top:5px;">{d['pres']:.0f} hPa</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()

    # --- ANÁLISIS ---
    with st.expander("📊 ANÁLISIS DE GRADIENTE TÉRMICO (Cíes vs Redondela)", expanded=False):
        mar = data.get("10125")
        tierra = data.get("10154")
        
        if mar and tierra:
            th_mar = calc_theta_v(mar['temp'], mar['hr'], mar['pres'])
            th_tierra = calc_theta_v(tierra['temp'], tierra['hr'], tierra['pres'])
            
            if th_mar and th_tierra:
                diff = th_tierra - th_mar
                c1, c2, c3 = st.columns(3)
                c1.metric("Densidad Mar (θv)", f"{th_mar:.1f} K")
                c2.metric("Densidad Tierra (θv)", f"{th_tierra:.1f} K")
                c3.metric("Diferencia (Δ)", f"{diff:+.2f} K")
                
                if diff > 1.5:
                    st.success(" **POSIBLE VIRAZÓN:** Tierra mucho más ligera. El aire frío del mar entrará acelerando.")
                elif diff < -1.5:
                    st.warning(" **POSIBLE BOCANA/TERRAL:** Tierra fría y densa.")
                else:
                    st.info("⚖️ **ESTABILIDAD:** No hay gradiente térmico suficiente.")
            else:
                st.error("Faltan datos de Presión/Humedad.")
        else:
            st.error("Datos de referencia no disponibles.")

else:
    st.error("Error conectando con MeteoGalicia.")

