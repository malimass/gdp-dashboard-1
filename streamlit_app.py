import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Dati degli allenamenti
data = {
    "Allenamento": [
        "1 (6 lug)", "2", "3", "4", "5", "6", "7", "8", 
        "9 (extra 20 lug)", "10", "11", "12", "13", "14"
    ],
    "Distanza (km)": [
        18.79, 7.18, 8.41, 20.04, 20.04, 18.39, 12.34, 22.69,
        22.69, 7.54, 16.37, 9.41, 0, 0
    ],
    "Durata (min)": [
        180, 82, 82, 251, 251, 204, 127, 257,
        257, 80, 188, 77, 0, 0
    ],
    "FC Media": [
        112, 112, 118, 112, 112, 90, 103, 112,
        112, 110, 91, 125, 0, 0
    ],
    "FC Max": [
        155, 126, 146, 159, 159, 124, 115, 159,
        159, 138, 99, 162, 0, 0
    ],
    "Vel Media (km/h)": [
        6.2, 5.2, 6.1, 4.7, 4.7, 5.4, 5.8, 4.6,
        4.6, 5.6, 5.2, 7.3, 0, 0
    ],
    "Vel Max (km/h)": [
        19.0, 7.5, 9.9, 12.5, 12.5, 12.7, 8.9, 12.5,
        12.5, 9.3, 11.8, 11.1, 0, 0
    ],
    "Calorie": [
        1686, 750, 814, 2320, 2320, 1552, 1016, 2320,
        2320, 722, 1377, 823, 0, 0
    ],
    "Dislivello (m)": [
        470, 215, 255, 300, 300, 385, 165, 536,
        536, 180, 255, 340, 0, 0
    ]
}

# DataFrame
df = pd.DataFrame(data)

# Titolo app
st.title("\U0001F4CA Analisi Allenamenti (da 6 a 23 luglio 2025)")

# Selezione metriche
metriche = st.multiselect(
    "Seleziona le metriche da confrontare:",
    df.columns[1:],
    default=["Distanza (km)", "Durata (min)", "Calorie"]
)

# Grafico a linee
st.subheader("\U0001F4C8 Grafico delle metriche selezionate")
fig, ax = plt.subplots()
for metrica in metriche:
    ax.plot(df["Allenamento"], df[metrica], marker='o', label=metrica)
    max_idx = df[metrica].idxmax()
    ax.annotate(f"{df[metrica][max_idx]}", 
                (df["Allenamento"][max_idx], df[metrica][max_idx]),
                textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, color='red')

ax.set_xlabel("Allenamento")
ax.set_ylabel("Valore")
ax.set_title("Andamento Allenamenti")
ax.legend()
plt.xticks(rotation=45)
st.pyplot(fig)

