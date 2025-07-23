import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import io

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

def load_json_file(uploaded_file):
    """Carica e valida un file JSON"""
    try:
        content = json.loads(uploaded_file.getvalue().decode("utf-8"))
        return content, None
    except json.JSONDecodeError as e:
        return None, f"Errore nel parsing JSON: {str(e)}"
    except Exception as e:
        return None, f"Errore generico: {str(e)}"

def extract_date_from_filename(filename):
    """Estrae la data dal nome del file o usa data corrente"""
    try:
        # Prova a estrarre data dal filename (formato: YYYY-MM-DD)
        import re
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        match = re.search(date_pattern, filename)
        if match:
            return datetime.strptime(match.group(1), '%Y-%m-%d').date()
        else:
            return datetime.now().date()
    except:
        return datetime.now().date()

def flatten_json(data, parent_key='', sep='_'):
    """Appiattisce un JSON annidato"""
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_json(v, new_key, sep=sep).items())
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                # Gestisce liste di oggetti
                for i, item in enumerate(v):
                    items.extend(flatten_json(item, f"{new_key}_{i}", sep=sep).items())
            else:
                items.append((new_key, v))
    return dict(items)

def calculate_improvement(value1, value2, parameter_name):
    """Calcola il miglioramento tra due valori"""
    if value1 is None or value2 is None:
        return None, "N/A"
    
    try:
        val1, val2 = float(value1), float(value2)
        diff = val2 - val1
        perc_change = (diff / val1 * 100) if val1 != 0 else 0
        
        # Determina se l'aumento è positivo o negativo in base al parametro
        negative_parameters = ['tempo', 'time', 'durata', 'duration', 'fatica', 'fatigue', 'dolore', 'pain']
        is_negative_param = any(neg_param in parameter_name.lower() for neg_param in negative_parameters)
        
        if is_negative_param:
            improvement = -perc_change  # Per parametri "negativi", diminuzione = miglioramento
        else:
            improvement = perc_change   # Per parametri "positivi", aumento = miglioramento
            
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
                    name=param,
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        
        fig.update_layout(
            title="Andamento Parametri nel Tempo",
            xaxis_title="Data",
            yaxis_title="Valore",
            hovermode='x unified',
            height=500
        )
        
    elif chart_type == "bar":
        fig = make_subplots(
            rows=len(parameters), cols=1,
            subplot_titles=parameters,
            vertical_spacing=0.1
        )
        
        for i, param in enumerate(parameters, 1):
            if param in df.columns:
                fig.add_trace(
                    go.Bar(
                        x=df['data'],
                        y=df[param],
                        name=param,
                        showlegend=False
                    ),
                    row=i, col=1
                )
        
        fig.update_layout(height=300*len(parameters))
    
    elif chart_type == "radar":
        if len(df) >= 2:
            # Prende le prime due sessioni per il confronto radar
            categories = parameters
            
            fig = go.Figure()
            
            for idx, row in df.head(2).iterrows():
                values = [row.get(param, 0) for param in categories]
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
            file_date = extract_date_from_filename(uploaded_file.name)
            
            data, error = load_json_file(uploaded_file)
            if error:
                st.error(f"Errore nel file {uploaded_file.name}: {error}")
            else:
                # Appiattisce i dati JSON
                flattened_data = flatten_json(data)
                st.session_state.training_data[file_date] = {
                    'filename': uploaded_file.name,
                    'data': flattened_data,
                    'raw_data': data
                }
                st.success(f"✅ Caricato: {uploaded_file.name}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Selezione sessioni per confronto
    if st.session_state.training_data:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.header("📊 Selezione Sessioni")
        
        available_dates = sorted(st.session_state.training_data.keys())
        selected_dates = st.multiselect(
            "Seleziona date da confrontare",
            available_dates,
            default=available_dates[-2:] if len(available_dates) >= 2 else available_dates,
            help="Seleziona almeno 2 sessioni per il confronto"
        )
        
        st.session_state.selected_sessions = selected_dates
        st.markdown('</div>', unsafe_allow_html=True)

# Area principale
if not st.session_state.training_data:
    st.info("👆 Carica i file JSON degli allenamenti dalla sidebar per iniziare l'analisi")
    
    # Esempio di struttura dati
    with st.expander("📋 Esempio struttura file JSON"):
        example_data = {
            "sessione": {
                "data": "2024-01-15",
                "tipo": "corsa",
                "durata_minuti": 45
            },
            "parametri_fisici": {
                "frequenza_cardiaca_max": 185,
                "frequenza_cardiaca_media": 150,
                "calorie": 450
            },
            "performance": {
                "distanza_km": 8.5,
                "velocita_media": 11.3,
                "passo_medio": "5:18"
            },
            "sensazioni": {
                "fatica": 7,
                "motivazione": 8,
                "dolori": 2
            }
        }
        st.json(example_data)

else:
    # Tab per diverse analisi
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Confronto Sessioni", "📊 Analisi Parametri", "🎯 Progressi", "📋 Dati Dettagliati"])
    
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
            df_comparison = pd.DataFrame(comparison_data).sort_values('data')
            
            # Selezione parametri per il confronto
            col1, col2 = st.columns([1, 1])
            with col1:
                selected_params = st.multiselect(
                    "Parametri da confrontare",
                    sorted(all_parameters),
                    default=list(sorted(all_parameters))[:5],
                    help="Seleziona i parametri che vuoi visualizzare nel confronto"
                )
            
            with col2:
                chart_type = st.selectbox(
                    "Tipo di grafico",
                    ["line", "bar", "radar"],
                    format_func=lambda x: {"line": "Linea", "bar": "Barre", "radar": "Radar"}[x]
                )
            
            if selected_params:
                # Crea e mostra il grafico
                fig = create_comparison_chart(df_comparison, selected_params, chart_type)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Tabella di confronto dettagliata
                st.subheader("Tabella di Confronto")
                display_df = df_comparison[['data'] + selected_params].round(2)
                st.dataframe(display_df, use_container_width=True)
    
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
                        numeric_columns
                    )
                    
                    if selected_param:
                        # Box plot del parametro selezionato
                        fig_box = px.box(
                            df_analysis, 
                            y=selected_param,
                            title=f"Distribuzione di {selected_param}"
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
                        title="Correlazione tra Parametri"
                    )
                    st.plotly_chart(fig_corr, use_container_width=True)
    
    with tab3:
        st.subheader("Analisi dei Progressi")
        
        if len(st.session_state.selected_sessions) >= 2:
            # Confronta prima e ultima sessione
            sessions_sorted = sorted(st.session_state.selected_sessions)
            first_session = st.session_state.training_data[sessions_sorted[0]]['data']
            last_session = st.session_state.training_data[sessions_sorted[-1]]['data']
            
            st.write(f"**Confronto: {sessions_sorted[0]} → {sessions_sorted[-1]}**")
            
            # Calcola miglioramenti
            improvements = []
            all_params = set(first_session.keys()) | set(last_session.keys())
            
            for param in sorted(all_params):
                if param in first_session and param in last_session:
                    improvement, change_str = calculate_improvement(
                        first_session.get(param), 
                        last_session.get(param), 
                        param
                    )
                    
                    if improvement is not None:
                        improvements.append({
                            'Parametro': param,
                            'Valore Iniziale': first_session.get(param),
                            'Valore Finale': last_session.get(param),
                            'Cambiamento': change_str,
                            'Miglioramento %': round(improvement, 1)
                        })
            
            if improvements:
                improvements_df = pd.DataFrame(improvements)
                improvements_df = improvements_df.sort_values('Miglioramento %', ascending=False)
                
                # Visualizza miglioramenti principali
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
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write("**Dati Appiattiti (per analisi)**")
                    flattened_df = pd.DataFrame([session_info['data']]).T
                    flattened_df.columns = ['Valore']
                    st.dataframe(flattened_df)
                
                with col2:
                    st.write("**Dati Originali (JSON)**")
                    st.json(session_info['raw_data'])
                
                # Opzione per scaricare i dati
                if st.button("💾 Scarica dati CSV"):
                    csv_data = pd.DataFrame([session_info['data']])
                    csv_buffer = io.StringIO()
                    csv_data.to_csv(csv_buffer, index=False)
                    
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv_buffer.getvalue(),
                        file_name=f"training_data_{selected_session}.csv",
                        mime="text/csv"
                    )

# Footer con informazioni
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>🏃‍♂️ <strong>Analisi Dati Allenamento</strong> - Monitora i tuoi progressi sportivi</p>
    <p><small>Carica i file JSON dei tuoi allenamenti per visualizzare analisi dettagliate e confronti nel tempo</small></p>
</div>
""", unsafe_allow_html=True)
