import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import io
import re

# Configurazione pagina
st.set_page_config(
    page_title="Analisi Dati Allenamento",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stili CSS personalizzati
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .improvement-positive {
        color: #28a745;
        font-weight: bold;
    }
    .improvement-negative {
        color: #dc3545;
        font-weight: bold;
    }
    .sidebar-section {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Inizializzazione session state
if 'training_data' not in st.session_state:
    st.session_state.training_data = {}
if 'selected_sessions' not in st.session_state:
    st.session_state.selected_sessions = []

def parse_duration(duration_str):
    """Converte una durata ISO 8601 in secondi"""
    try:
        # Rimuove 'PT' e 'S' dalla stringa
        duration_str = duration_str.replace('PT', '').replace('S', '')
        return float(duration_str)
    except:
        return None

def parse_datetime(datetime_str):
    """Converte una stringa datetime ISO in oggetto datetime"""
    try:
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except:
        return None

def load_json_file(uploaded_file):
    """Carica e valida un file JSON specifico per i dati di allenamento"""
    try:
        content = json.loads(uploaded_file.getvalue().decode("utf-8"))
        return content, None
    except json.JSONDecodeError as e:
        return None, f"Errore nel parsing JSON: {str(e)}"
    except Exception as e:
        return None, f"Errore generico: {str(e)}"

def extract_date_from_json(data):
    """Estrae la data di inizio dell'allenamento dal JSON"""
    try:
        if 'exercises' in data and len(data['exercises']) > 0:
            start_time = data['exercises'][0].get('startTime')
            if start_time:
                dt = parse_datetime(start_time)
                if dt:
                    return dt.date()
        return datetime.now().date()
    except:
        return datetime.now().date()

def process_exercise_data(exercise):
    """Processa i dati di un singolo esercizio"""
    processed = {}
    
    # Dati base
    processed['sport'] = exercise.get('sport', 'N/A')
    processed['durata_secondi'] = parse_duration(exercise.get('duration', '0'))
    processed['durata_minuti'] = processed['durata_secondi'] / 60 if processed['durata_secondi'] else None
    processed['distanza_metri'] = exercise.get('distance', 0)
    processed['distanza_km'] = processed['distanza_metri'] / 1000 if processed['distanza_metri'] else None
    processed['calorie'] = exercise.get('kiloCalories', 0)
    processed['ascent'] = exercise.get('ascent', 0)
    processed['descent'] = exercise.get('descent', 0)
    
    # Dati di altitudine
    if 'altitude' in exercise:
        alt = exercise['altitude']
        processed['altitudine_min'] = alt.get('min', 0)
        processed['altitudine_avg'] = alt.get('avg', 0)
        processed['altitudine_max'] = alt.get('max', 0)
    
    # Dati frequenza cardiaca
    if 'heartRate' in exercise:
        hr = exercise['heartRate']
        processed['fc_min'] = hr.get('min', 0)
        processed['fc_avg'] = hr.get('avg', 0)
        processed['fc_max'] = hr.get('max', 0)
    
    # Dati velocità
    if 'speed' in exercise:
        speed = exercise['speed']
        processed['velocita_avg_ms'] = speed.get('avg', 0)
        processed['velocita_max_ms'] = speed.get('max', 0)
        processed['velocita_avg_kmh'] = processed['velocita_avg_ms'] * 3.6 if processed['velocita_avg_ms'] else None
        processed['velocita_max_kmh'] = processed['velocita_max_ms'] * 3.6 if processed['velocita_max_ms'] else None
        
        # Calcola passo medio (min/km)
        if processed['velocita_avg_kmh'] and processed['velocita_avg_kmh'] > 0:
            passo_minuti = 60 / processed['velocita_avg_kmh']
            processed['passo_medio_min_km'] = passo_minuti
    
    # Calcola metriche derivate
    if processed['distanza_km'] and processed['durata_minuti']:
        processed['velocita_media_calc'] = processed['distanza_km'] / (processed['durata_minuti'] / 60)
    
    # Zone di velocità (prende solo la prima zona se presente)
    if 'zones' in exercise and 'speed' in exercise['zones']:
        speed_zones = exercise['zones']['speed']
        if speed_zones and len(speed_zones) > 0:
            main_zone = speed_zones[0]
            processed['zona_vel_min'] = main_zone.get('lowerLimit', 0)
            processed['zona_vel_max'] = main_zone.get('higherLimit', 0)
            processed['tempo_in_zona'] = parse_duration(main_zone.get('inZone', '0'))
            processed['distanza_in_zona'] = main_zone.get('distance', 0)
    
    # Calcola intensità dell'allenamento
    if processed.get('fc_avg') and processed.get('fc_max'):
        processed['intensita_fc'] = (processed['fc_avg'] / processed['fc_max']) * 100
    
    return processed

def calculate_improvement(value1, value2, parameter_name):
    """Calcola il miglioramento tra due valori"""
    if value1 is None or value2 is None or value1 == 0:
        return None, "N/A"
    
    try:
        val1, val2 = float(value1), float(value2)
        diff = val2 - val1
        perc_change = (diff / val1 * 100) if val1 != 0 else 0
        
        # Determina se l'aumento è positivo o negativo in base al parametro
        negative_parameters = ['durata', 'tempo', 'passo', 'fc_min']
        positive_parameters = ['distanza', 'velocita', 'calorie', 'fc_max', 'fc_avg']
        
        is_negative_param = any(neg_param in parameter_name.lower() for neg_param in negative_parameters)
        is_positive_param = any(pos_param in parameter_name.lower() for pos_param in positive_parameters)
        
        if is_negative_param:
            improvement = -perc_change  # Per parametri "negativi", diminuzione = miglioramento
        elif is_positive_param:
            improvement = perc_change   # Per parametri "positivi", aumento = miglioramento
        else:
            improvement = perc_change   # Default: aumento = miglioramento
            
        return improvement, f"{diff:+.2f} ({perc_change:+.1f}%)"
    except (ValueError, TypeError):
        return None, "N/A"

def create_comparison_chart(df, parameters, chart_type="line"):
    """Crea grafici di confronto"""
    if df.empty or not parameters:
        return None
    
    if chart_type == "line":
        fig = go.Figure()
        for param in parameters:
            if param in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['data'],
                    y=df[param],
                    mode='lines+markers',
                    name=param.replace('_', ' ').title(),
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        
        fig.update_layout(
            title="Andamento Parametri nel Tempo",
            xaxis_title="Data",
            yaxis_title="Valore",
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
    elif chart_type == "bar":
        fig = make_subplots(
            rows=len(parameters), cols=1,
            subplot_titles=[param.replace('_', ' ').title() for param in parameters],
            vertical_spacing=0.1
        )
        
        for i, param in enumerate(parameters, 1):
            if param in df.columns:
                fig.add_trace(
                    go.Bar(
                        x=df['data'],
                        y=df[param],
                        name=param.replace('_', ' ').title(),
                        showlegend=False
                    ),
                    row=i, col=1
                )
        
        fig.update_layout(height=300*len(parameters))
    
    elif chart_type == "radar":
        if len(df) >= 2:
            # Normalizza i valori per il radar chart
            categories = [param.replace('_', ' ').title() for param in parameters]
            
            fig = go.Figure()
            
            for idx, row in df.head(2).iterrows():
                values = []
                for param in parameters:
                    val = row.get(param, 0)
                    if val is not None:
                        values.append(float(val))
                    else:
                        values.append(0)
                
                fig.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    name=f"Sessione {row['data']}"
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True)
                ),
                title="Confronto Radar tra Sessioni"
            )
    
    return fig

def format_duration(seconds):
    """Formatta la durata in ore:minuti:secondi"""
    if seconds is None:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    else:
        return f"{minutes}m {secs}s"

def format_pace(minutes_per_km):
    """Formatta il passo in mm:ss per km"""
    if minutes_per_km is None:
        return "N/A"
    minutes = int(minutes_per_km)
    seconds = int((minutes_per_km - minutes) * 60)
    return f"{minutes}:{seconds:02d} /km"

# Header principale
st.markdown('<h1 class="main-header">🏃‍♂️ Analisi Dati Allenamento</h1>', unsafe_allow_html=True)

# Sidebar per caricamento file
with st.sidebar:
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.header("📁 Caricamento Dati")
    
    uploaded_files = st.file_uploader(
        "Carica file JSON di allenamento",
        type=['json'],
        accept_multiple_files=True,
        help="Carica uno o più file JSON contenenti i dati degli allenamenti"
    )
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            data, error = load_json_file(uploaded_file)
            if error:
                st.error(f"Errore nel file {uploaded_file.name}: {error}")
            else:
                # Estrae la data dal JSON
                file_date = extract_date_from_json(data)
                
                # Processa gli esercizi
                processed_exercises = []
                if 'exercises' in data:
                    for exercise in data['exercises']:
                        processed_data = process_exercise_data(exercise)
                        processed_exercises.append(processed_data)
                
                # Salva i dati processati
                st.session_state.training_data[file_date] = {
                    'filename': uploaded_file.name,
                    'data': processed_exercises[0] if processed_exercises else {},  # Prende il primo esercizio
                    'raw_data': data,
                    'all_exercises': processed_exercises
                }
                st.success(f"✅ Caricato: {uploaded_file.name}")
                st.info(f"📅 Data: {file_date}")
                if processed_exercises:
                    st.info(f"🏃 Sport: {processed_exercises[0].get('sport', 'N/A')}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Selezione sessioni per confronto
    if st.session_state.training_data:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.header("📊 Selezione Sessioni")
        
        available_dates = sorted(st.session_state.training_data.keys(), reverse=True)
        selected_dates = st.multiselect(
            "Seleziona date da confrontare",
            available_dates,
            default=available_dates[:2] if len(available_dates) >= 2 else available_dates,
            help="Seleziona almeno 2 sessioni per il confronto"
        )
        
        st.session_state.selected_sessions = selected_dates
        st.markdown('</div>', unsafe_allow_html=True)

# Area principale
if not st.session_state.training_data:
    st.info("👆 Carica i file JSON degli allenamenti dalla sidebar per iniziare l'analisi")
    
    # Esempio di struttura dati
    with st.expander("📋 Struttura dati supportata"):
        st.markdown("""
        Il sistema supporta file JSON con la seguente struttura:
        ```json
        {
          "exercises": [
            {
              "startTime": "2025-07-21T04:53:40.000",
              "duration": "PT4819.500S",
              "distance": 7545.60009765625,
              "sport": "OTHER_OUTDOOR",
              "kiloCalories": 722,
              "heartRate": {
                "min": 62, "avg": 110, "max": 138
              },
              "speed": {
                "avg": 5.636302471160889,
                "max": 9.399999618530273
              },
              "altitude": {
                "min": 5.63, "avg": 21.24, "max": 39.31
              }
            }
          ]
        }
        ```
        """)

else:
    # Tab per diverse analisi
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Confronto Sessioni", "📊 Analisi Parametri", "🎯 Progressi", "📋 Dati Dettagliati", "🏃 Riepilogo Sessioni"])
    
    with tab1:
        if len(st.session_state.selected_sessions) < 2:
            st.warning("⚠️ Seleziona almeno 2 sessioni dalla sidebar per visualizzare i confronti")
        else:
            st.subheader("Confronto tra Sessioni Selezionate")
            
            # Crea DataFrame per il confronto
            comparison_data = []
            all_parameters = set()
            
            for date in st.session_state.selected_sessions:
                session_data = st.session_state.training_data[date]['data'].copy()
                session_data['data'] = date
                comparison_data.append(session_data)
                all_parameters.update(session_data.keys())
            
            all_parameters.discard('data')
            all_parameters.discard('sport')  # Rimuove parametri non numerici
            
            # Filtra solo parametri numerici
            numeric_params = []
            if comparison_data:
                for param in all_parameters:
                    try:
                        # Controlla se tutti i valori sono numerici
                        values = [data.get(param) for data in comparison_data]
                        if all(isinstance(v, (int, float)) and v is not None for v in values):
                            numeric_params.append(param)
                    except:
                        continue
            
            df_comparison = pd.DataFrame(comparison_data).sort_values('data')
            
            # Selezione parametri per il confronto
            col1, col2 = st.columns([1, 1])
            with col1:
                # Parametri suggeriti più comuni
                suggested_params = ['distanza_km', 'durata_minuti', 'velocita_avg_kmh', 'fc_avg', 'calorie']
                default_params = [p for p in suggested_params if p in numeric_params][:5]
                
                selected_params = st.multiselect(
                    "Parametri da confrontare",
                    sorted(numeric_params),
                    default=default_params,
                    help="Seleziona i parametri che vuoi visualizzare nel confronto"
                )
            
            with col2:
                chart_type = st.selectbox(
                    "Tipo di grafico",
                    ["line", "bar", "radar"],
                    format_func=lambda x: {"line": "📈 Linea", "bar": "📊 Barre", "radar": "🎯 Radar"}[x]
                )
            
            if selected_params:
                # Crea e mostra il grafico
                fig = create_comparison_chart(df_comparison, selected_params, chart_type)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Tabella di confronto dettagliata
                st.subheader("Tabella di Confronto")
                display_columns = ['data'] + selected_params
                display_df = df_comparison[display_columns].round(2)
                
                # Formatta alcune colonne specifiche
                formatted_df = display_df.copy()
                for col in display_df.columns:
                    if 'durata' in col and col != 'data':
                        if col in formatted_df.columns:
                            formatted_df[col] = formatted_df[col].apply(lambda x: format_duration(x*60) if pd.notna(x) else "N/A")
                    elif 'passo' in col and col != 'data':
                        if col in formatted_df.columns:
                            formatted_df[col] = formatted_df[col].apply(lambda x: format_pace(x) if pd.notna(x) else "N/A")
                
                st.dataframe(formatted_df, use_container_width=True)
    
    with tab2:
        st.subheader("Analisi Dettagliata Parametri")
        
        if st.session_state.selected_sessions:
            # Analisi statistica dei parametri
            all_data = []
            for date in st.session_state.selected_sessions:
                session_data = st.session_state.training_data[date]['data'].copy()
                session_data['data'] = date
                all_data.append(session_data)
            
            df_analysis = pd.DataFrame(all_data)
            
            # Filtra solo colonne numeriche
            numeric_columns = df_analysis.select_dtypes(include=[np.number]).columns.tolist()
            
            if numeric_columns:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write("**Statistiche Descrittive**")
                    stats_df = df_analysis[numeric_columns].describe().round(2)
                    st.dataframe(stats_df)
                
                with col2:
                    selected_param = st.selectbox(
                        "Seleziona parametro per analisi dettagliata",
                        numeric_columns,
                        format_func=lambda x: x.replace('_', ' ').title()
                    )
                    
                    if selected_param:
                        # Box plot del parametro selezionato
                        fig_box = px.box(
                            df_analysis, 
                            y=selected_param,
                            title=f"Distribuzione di {selected_param.replace('_', ' ').title()}"
                        )
                        st.plotly_chart(fig_box, use_container_width=True)
                
                # Correlazione tra parametri
                if len(numeric_columns) > 1:
                    st.subheader("Matrice di Correlazione")
                    corr_matrix = df_analysis[numeric_columns].corr()
                    fig_corr = px.imshow(
                        corr_matrix,
                        text_auto=True,
                        aspect="auto",
                        title="Correlazione tra Parametri",
                        labels=dict(color="Correlazione")
                    )
                    fig_corr.update_layout(height=600)
                    st.plotly_chart(fig_corr, use_container_width=True)
    
    with tab3:
        st.subheader("Analisi dei Progressi")
        
        if len(st.session_state.selected_sessions) >= 2:
            # Confronta prima e ultima sessione
            sessions_sorted = sorted(st.session_state.selected_sessions)
            first_session = st.session_state.training_data[sessions_sorted[0]]['data']
            last_session = st.session_state.training_data[sessions_sorted[-1]]['data']
            
            st.write(f"**Confronto: {sessions_sorted[0]} → {sessions_sorted[-1]}**")
            
            # Metriche principali in evidenza
            col1, col2, col3, col4 = st.columns(4)
            
            # Distanza
            dist_first = first_session.get('distanza_km', 0)
            dist_last = last_session.get('distanza_km', 0)
            dist_diff = dist_last - dist_first if dist_first and dist_last else 0
            col1.metric("Distanza (km)", f"{dist_last:.2f}", f"{dist_diff:+.2f}")
            
            # Durata
            dur_first = first_session.get('durata_minuti', 0)
            dur_last = last_session.get('durata_minuti', 0)
            dur_diff = dur_last - dur_first if dur_first and dur_last else 0
            col2.metric("Durata", format_duration(dur_last*60) if dur_last else "N/A", 
                       f"{dur_diff:+.1f} min" if dur_diff != 0 else "0 min")
            
            # Velocità media
            vel_first = first_session.get('velocita_avg_kmh', 0)
            vel_last = last_session.get('velocita_avg_kmh', 0)
            vel_diff = vel_last - vel_first if vel_first and vel_last else 0
            col3.metric("Velocità Media (km/h)", f"{vel_last:.2f}", f"{vel_diff:+.2f}")
            
            # Frequenza cardiaca media
            fc_first = first_session.get('fc_avg', 0)
            fc_last = last_session.get('fc_avg', 0)
            fc_diff = fc_last - fc_first if fc_first and fc_last else 0
            col4.metric("FC Media (bpm)", f"{fc_last:.0f}", f"{fc_diff:+.0f}")
            
            # Calcola miglioramenti dettagliati
            st.subheader("Analisi Miglioramenti Dettagliata")
            improvements = []
            all_params = set(first_session.keys()) | set(last_session.keys())
            
            for param in sorted(all_params):
                if param in first_session and param in last_session:
                    val_first = first_session.get(param)
                    val_last = last_session.get(param)
                    
                    if isinstance(val_first, (int, float)) and isinstance(val_last, (int, float)):
                        improvement, change_str = calculate_improvement(val_first, val_last, param)
                        
                        if improvement is not None:
                            improvements.append({
                                'Parametro': param.replace('_', ' ').title(),
                                'Valore Iniziale': round(val_first, 2),
                                'Valore Finale': round(val_last, 2),
                                'Cambiamento': change_str,
                                'Miglioramento %': round(improvement, 1)
                            })
            
            if improvements:
                improvements_df = pd.DataFrame(improvements)
                improvements_df = improvements_df.sort_values('Miglioramento %', ascending=False)
                
                # Metriche di riepilogo
                col1, col2, col3 = st.columns(3)
                
                if len(improvements_df) > 0:
                    best_improvement = improvements_df.iloc[0]
                    col1.metric(
                        "Miglior Progresso",
                        best_improvement['Parametro'],
                        f"{best_improvement['Miglioramento %']}%"
                    )
                
                if len(improvements_df) > 1:
                    avg_improvement = improvements_df['Miglioramento %'].mean()
                    col2.metric(
                        "Miglioramento Medio",
                        f"{avg_improvement:.1f}%",
                        "Tutti i parametri"
                    )
                
                positive_improvements = len(improvements_df[improvements_df['Miglioramento %'] > 0])
                col3.metric(
                    "Parametri Migliorati",
                    f"{positive_improvements}/{len(improvements_df)}",
                    f"{positive_improvements/len(improvements_df)*100:.0f}%"
                )
                
                # Tabella dettagliata miglioramenti
                st.subheader("Dettaglio Miglioramenti")
                
                # Applica styling alla tabella
                def style_improvements(val):
                    if pd.isna(val):
                        return ''
                    try:
                        num_val = float(val)
                        if num_val > 0:
                            return 'background-color: #d4edda; color: #155724'
                        elif num_val < 0:
                            return 'background-color: #f8d7da; color: #721c24'
                        else:
                            return ''
                    except:
                        return ''
                
                styled_df = improvements_df.style.applymap(
                    style_improvements, 
                    subset=['Miglioramento %']
                )
                st.dataframe(styled_df, use_container_width=True)
                
                # Grafico dei miglioramenti
                fig_improvements = px.bar(
                    improvements_df.head(10),
                    x='Miglioramento %',
                    y='Parametro',
                    orientation='h',
                    title="Top 10 Miglioramenti",
                    color='Miglioramento %',
                    color_continuous_scale=['red', 'yellow', 'green']
                )
                fig_improvements.update_layout(height=500)
                st.plotly_chart(fig_improvements, use_container_width=True)
        else:
            st.info("Seleziona almeno 2 sessioni per visualizzare i progressi")
    
    with tab4:
        st.subheader("Dati Dettagliati delle Sessioni")
        
        if st.session_state.selected_sessions:
            selected_session = st.selectbox(
                "Seleziona sessione da visualizzare",
                st.session_state.selected_sessions,
                format_func=lambda x: f"{x} - {st.session_state.training_data[x]['filename']}"
            )
            
            if selected_session:
                session_info = st.session_state.training_data[selected_session]
                
                # Informazioni principali della sessione
                st.subheader(f"📊 Sessione del {selected_session}")
                
                data = session_info['data']
                
                # Metriche principali
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Sport", data.get('sport', 'N/A'))
                col2.metric("Distanza", f"{data.get('distanza_km', 0):.2f} km")
                col3.metric("Durata", format_duration(data.get('durata_secondi', 0)))
                col4.metric("Calorie", f"{data.get('calorie', 0):.0f} kcal")
                col5.metric("Dislivello", f"{data.get('ascent', 0):.0f} m")
                
                # Dettagli frequenza cardiaca e velocità
                st.subheader("💓 Frequenza Cardiaca e Velocità")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("FC Media", f"{data.get('fc_avg', 0):.0f} bpm")
                col2.metric("FC Max", f"{data.get('fc_max', 0):.0f} bpm")
                col3.metric("Velocità Media", f"{data.get('velocita_avg_kmh', 0):.2f} km/h")
                col4.metric("Passo Medio", format_pace(data.get('passo_medio_min_km', 0)))
                
                # Tabs per visualizzazioni dettagliate
