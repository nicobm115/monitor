import streamlit as st
import requests
import math
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor Ría de Vigo", page_icon="🌬️", layout="wide")

# --- CSS PARA FLECHAS ROTATORIAS ---
st.markdown("""
<style>
    .metric-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
    }
    .big-font { font-size: 24px; font-weight: bold; }
    .small-font { font-size: 12px; color: #aaa; }
</style>
""", unsafe_allow_html=True)

# --- LÓGICA DE NEGOCIO ---
API_URL = "https://servizos.meteogalicia.gal/mgrss/observacion/ultimos10minEstacionsMeteo.action"
DISPLAY_STATIONS = [{"id": "10125", "name": "CÍES (Mar)"}, {"id": "10906", "name": "CANGAS (Costa)"}]
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
    k = float(knots)
    if k < 3:   return "#FFFFFF", "#000000"
    if k < 6:   return "#E1F5FE", "#000000"
    if k < 9:   return "#81D4FA", "#000000"
    if k < 12:  return "#00FFBF", "#000000" 
    if k < 16:  return "#76FF03", "#000000" 
    if k < 20:  return "#FFEA00", "#000000"
    if k < 25:  return "#FF9100", "#000000"
    if k < 30:  return "#D50000", "#000000"
    return "#4A148C", "#FFFFFF"  
    
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
                    elif c == 'VV_RACHA_10m': d['g_spd'] = v # Corregido código racha según PDF
                    elif c == 'DV_RACHA_10m': d['g_dir'] = v # Corregido código dir racha
                    elif 'TA_AVG_1.5m' in c: d['temp'] = v
                    elif 'HR_AVG_1.5m' in c: d['hr'] = v
                    elif 'PR_AVG_1.5m' in c: d['pres'] = v # Corregido código presión
                    elif 'DV_SD_10m' in c: d['std'] = v 
                
                if d['g_dir'] == 0 and d['w_dir'] != 0: d['g_dir'] = d['w_dir']
                parsed_data[sid] = d
                
        return parsed_data, last_update
    except:
        return None, None

# --- INTERFAZ WEB ---
st.title("🌬️ Monitor Ría de Vigo")
st.caption("@nicobm115 - Datos de MeteoGalicia")

if st.button("↻ Actualizar Datos"):
    st.cache_data.clear()

data, timestamp = fetch_all_data()

if data:
    try:
        # 1. Decirle a Python que el dato original es UTC
        dt_utc = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        
        # 2. Convertir a hora de Vigo (Madrid)
        dt_local = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        
        # 3. Mostrar
        st.write(f"**Última lectura:** {dt_local.strftime('%H:%M')} (Local)")
    except: pass

    for st_conf in DISPLAY_STATIONS:
        sid = st_conf['id']
        d = data.get(sid)
        
        if d:
            with st.container():
                st.subheader(f"📍 {st_conf['name']}")
                c1, c2, c3, c4 = st.columns(4)
                
                # Viento
                k_w = mps_to_knots(d['w_spd'])
                col_w = get_wind_color(k_w)
                # CORRECCIÓN AQUÍ: Eliminado el +180.
                # Como el icono base ⬇ ya apunta abajo, 0º (Norte) lo mantiene abajo.
                rot_w = d['w_dir'] 
                
                c1.markdown(f"""
                <div class="metric-card">
                    <div class="small-font">VIENTO MEDIO</div>
                    <div class="big-font" style="color:{col_w}">{k_w:.1f} kn</div>
                    <div style="transform: rotate({rot_w}deg); font-size: 30px; color:{col_w}">⬇</div>
                    <div class="small-font">{d['w_dir']:.0f}°</div>
                </div>
                """, unsafe_allow_html=True)

                # Racha
                k_g = mps_to_knots(d['g_spd'])
                col_g = get_wind_color(k_g)
                # CORRECCIÓN AQUÍ: Eliminado el +180
                rot_g = d['g_dir']
                
                c2.markdown(f"""
                <div class="metric-card">
                    <div class="small-font">RACHA MÁX</div>
                    <div class="big-font" style="color:{col_g}">{k_g:.1f} kn</div>
                    <div style="transform: rotate({rot_g}deg); font-size: 30px; color:{col_g}">⬇</div>
                    <div class="small-font">{d['g_dir']:.0f}°</div>
                </div>
                """, unsafe_allow_html=True)

                # Turbulencia / Desviación
                c3.metric("Turbulencia ", f"±{d['std']:.0f}°", help="Desviación típica")
                
                # Meteo
                c4.metric("Temp / HR", f"{d['temp']}°C", f"{d['hr']}% HR")
                
            st.divider()

    # --- ANÁLISIS TÉRMICO ---
    with st.expander("📊 ANÁLISIS DE GRADIENTE TÉRMICO (Cíes vs Redondela)", expanded=False):
        mar = data.get("10125")
        tierra = data.get("10154") 
        
        if mar and tierra:
            th_mar = calc_theta_v(mar['temp'], mar['hr'], mar['pres'])
            th_tierra = calc_theta_v(tierra['temp'], tierra['hr'], tierra['pres'])
            diff = th_tierra - th_mar
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Densidad Mar (θv)", f"{th_mar:.2f} K")
            col2.metric("Densidad Tierra (θv)", f"{th_tierra:.2f} K")
            col3.metric("Diferencia (Δ)", f"{diff:+.2f} K")
            
            if diff > 1.5:
                st.success(" **POSIBLE VIRAZÓN:** Tierra mucho más ligera. El aire frío del mar entrará acelerando.")
            elif diff < -1.5:
                st.warning(" **POSIBLE BOCANA/TERRAL:** Tierra fría y densa.")
            else:
                st.info("⚖️ **ESTABILIDAD:** No hay gradiente térmico suficiente.")
        else:
            st.error("Datos de referencia (Redondela) no disponibles.")

else:
    st.error("Error conectando con MeteoGalicia. Intenta refrescar.")
