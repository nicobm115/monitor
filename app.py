import streamlit as st
import requests
import math
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor Ría de Vigo", page_icon="🌬️", layout="centered")
# --- CSS INYECTADO (Estilos y Animaciones) ---
st.markdown("""
<style>
    .metric-card {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .big-text { font-size: 26px; font-weight: 800; margin: 0; }
    .label-text { font-size: 12px; text-transform: uppercase; font-weight: 600; opacity: 0.8; }
    .arrow-icon { 
        display: inline-block; 
        font-size: 30px; 
        line-height: 30px; 
        margin-top: 5px;
        transition: transform 0.5s ease-out; /* Animación suave si cambia */
    }
    .dir-text { font-size: 14px; opacity: 0.9; margin-top: -5px; }
</style>
""", unsafe_allow_html=True)

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

def get_wind_style(knots):
    """Devuelve (ColorFondo, ColorTexto) según intensidad"""
    k = float(knots)
    if k < 4:   return "#F5F5F5", "#000000" # Calma (Gris claro)
    if k < 12:  return "#1ba0cc", "#000000" # Azul suave
    if k < 16:  return "#1bcc62", "#000000" # Verde (Ideal)
    if k < 21:  return "#c9cc1b", "#000000" # Amarillo (Alegre)
    if k < 27:  return "#cc7c1b", "#000000" # Naranja (Duro)
    if k < 34:  return "#cc201b", "#000000" # Rojo (Muy duro)
    return "#cc1b76", "#000000"             # Violeta (Temporal)

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
                d = {'w_spd': 0, 'w_dir': 0, 'g_spd': 0, 'g_dir': 0, 'temp': 0, 'hr': 0, 'std': 0}
                
                for m in est['listaMedidas']:
                    c = m['codigoParametro']; v = m['valor']
                    if c == 'VV_AVG_10m': d['w_spd'] = v
                    elif c == 'DV_AVG_10m': d['w_dir'] = v
                    elif c == 'VV_RACHA_10m': d['g_spd'] = v
                    elif c == 'DV_RACHA_10m': d['g_dir'] = v
                    elif 'TA_AVG_1.5m' in c: d['temp'] = v
                    elif 'HR_AVG_1.5m' in c: d['hr'] = v
                    elif 'DV_SD_10m' in c: d['std'] = v 
                
                if d['g_dir'] == 0 and d['w_dir'] != 0: d['g_dir'] = d['w_dir']
                parsed_data[sid] = d
                
        return parsed_data, last_update
    except:
        return None, None

def render_wind_card(title, speed, deg):
    bg, txt = get_wind_style(speed)
    cardinal = get_cardinal(deg)
    
    # LÓGICA DE ROTACIÓN:
    # Usamos la flecha '⬇' (Unicode). 
    # A 0 grados (rotación por defecto), apunta abajo. 
    # Esto cumple tu regla: "0º N flecha hacia abajo".
    # CSS transform rotate gira en sentido horario.
    
    html = f"""
    <div class="metric-card" style="background-color: {bg}; color: {txt};">
        <div class="label-text">{title}</div>
        <div class="big-text">{speed:.1f} kn</div>
        <div class="arrow-icon" style="transform: rotate({deg}deg);">⬇</div>
        <div class="dir-text">{deg:.0f}° {cardinal}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- UI ---
st.title("🌬️ Monitor Ría de Vigo")
st.caption("@nicobm115-Datos MeteoGalicia")

if st.button("↻ Recargar datos"):
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
            
            c1, c2, c3, c4 = st.columns(4)
            
            # --- VIENTO MEDIO ---
            with c1:
                render_wind_card("Viento Medio", mps_to_knots(d['w_spd']), d['w_dir'])

            # --- RACHA ---
            with c2:
                render_wind_card("Racha Máx", mps_to_knots(d['g_spd']), d['g_dir'])

            # --- TURBULENCIA ---
            with c3:
                # Si es 0 (imposible) o None, mostramos "--"
                if d['std'] and d['std'] > 0:
                    val_turb = f"±{d['std']:.0f}°"
                    sub_txt = "Desviación σ"
                    color_txt = "#FFF" # Blanco brillante
                else:
                    val_turb = "--"
                    sub_txt = "No disponible"
                    color_txt = "#666" # Gris apagado
                    # Lógica opcional para Cangas si std es 0

                if d['std'] == 0 and d['w_spd'] > 0:
                    # Gust Factor simple: (Racha - Media)
                    # Si hay 5 nudos de media y 15 de racha, es muy racheado/turbulento
                    diff_racha = mps_to_knots(d['g_spd'] - d['w_spd'])
                    val_turb = f"Δ {diff_racha:.1f} kn" 
                    sub_txt = "Racha vs Media"

                st.markdown(f"""
                <div class="metric-card" style="background-color: #262730; color: {color_txt}; border: 1px solid #444;">
                    <div class="label-text" style="color: #AAA;">Turbulencia</div>
                    <div class="big-text">{val_turb}</div>
                    <div class="dir-text" style="margin-top:5px; color: #AAA;">{sub_txt}</div>
                </div>
                """, unsafe_allow_html=True)

            # --- METEO ---
            with c4:
                st.metric(label="Temperatura", value=f"{d['temp']} °C", delta=f"{d['hr']}% HR")
                
            
            st.divider()

    # --- ANÁLISIS ---
    with st.expander("📊 ANÁLISIS TÉRMICO ", expanded=False):
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
                    st.success("**POSIBLE VIRAZÓN:** Tierra mucho más ligera. El aire frío del mar entrará acelerando.")
                elif diff < -1.5:
                    st.warning("**POSIBLE BOCANA/TERRAL:** Tierra fría y densa.")
                else:
                    st.info("**⚖️ESTABILIDAD:** No hay gradiente térmico significativo.")
            else:
                st.error("Faltan datos de Presión/Humedad.")
        else:
            st.error("Datos de referencia no disponibles.")

else:
    st.error("Error conectando con MeteoGalicia.")








