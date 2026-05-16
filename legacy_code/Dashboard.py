import os
import sys

# Force the current directory into sys.path to ensure local modules are found
# This must be done before any local imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json, requests, base64, random
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from scipy.optimize import minimize

from sante.logic import load_sante, save_sante, calculate_daily_targets, optimize_nutrition, \
    calculate_plan_totals, update_sante_data
from habits.logic import (
    proprete_pct, vie_pct, needs_wash, is_worn_out, ports_avant_lavage,
    badge_html, disponible, colors_compat, style_score_func as style_score,
    get_color_category,
    load_history, save_history, get_purchase_recommendations,
    load_wardrobe, save_wardrobe, get_weather, get_weather_info, thermal_score,
    calculate_thermal_gap, score_rotation, suggest_outfit, asset_path, perso_path, to_b64,
    SLOTS, EMO_CAT, ACCENTS
)
from finance.logic import get_hist, get_portfolio
from agenda.logic import load_agenda

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Mission Control", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');
.stApp{background:#0A0D14;color:#E8EAF0;font-family:'Inter',sans-serif;}
h1,h2,h3{font-family:'Space Mono',monospace;}
.stButton>button{width:100%;background:#111827;border:1px solid #1e293b;color:#94a3b8;
  border-radius:8px;font-family:'Space Mono',monospace;font-size:0.75em;transition:all .2s;padding:6px 4px;}
.stButton>button:hover{border-color:#3b82f6;color:#60a5fa;background:#1a2235;}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#1d4ed8,#1e40af)!important;
  border-color:#3b82f6!important;color:#fff!important;font-weight:700!important;}
.stTabs [data-baseweb="tab-list"]{background:#0f172a;border-radius:8px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{background:transparent;border-radius:6px;color:#64748b;
  font-family:'Space Mono',monospace;font-size:.8em;}
.stTabs [aria-selected="true"]{background:#1e293b!important;color:#e2e8f0!important;}
.slot-card{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px 8px;
  text-align:center;min-height:95px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:3px;}
.item-card{background:#111827;border:1px solid #1e293b;border-radius:10px;
  padding:14px;text-align:center;transition:all .2s;}
.item-card:hover{border-color:#3b82f6;}
hr{border-color:#1e293b;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# NAVIGATION
# ─────────────────────────────────────────────
if 'page' not in st.session_state:
    st.session_state.page = "global"


def set_page(name):
    st.session_state.page = name


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
wardrobe = load_wardrobe()

if 'tenue' not in st.session_state:
    st.session_state.tenue = {s["id"]: None for s in SLOTS}
    st.session_state.suggested = False
    st.session_state.use_body = False
    st.session_state.t_outfit = 15.0
else:
    # Migration: ensure new slots are present in session state
    for s in SLOTS:
        if s["id"] not in st.session_state.tenue:
            st.session_state.tenue[s["id"]] = None

# ═════════════════════════════════════════════
# HEADER + NAV
# ═════════════════════════════════════════════
ch1, ch2 = st.columns([3, 1])
with ch1:
    st.markdown("<h1 style='font-family:Space Mono;color:#e2e8f0;margin-bottom:0;'>🛰 MISSION CONTROL</h1>",
                unsafe_allow_html=True)
with ch2:
    st.markdown(
        f"<p style='text-align:right;color:#64748b;font-size:.8em;margin-top:10px;'>"
        f"Germain De Sousa<br>"
        f"<span style='color:#3b82f6;'>{datetime.now().strftime('%H:%M')} · {datetime.now().strftime('%d %b %Y')}</span></p>",
        unsafe_allow_html=True)

nav = st.columns(6)
for i, (label, key) in enumerate([("🌐 Global", "global"), ("📈 Finance", "finance"),
                                  ("🧥 Habits", "habits"), ("🍎 Santé", "sante"), ("📅 Agenda", "agenda")]):
    if nav[i].button(label, key=f"nav_{key}"): set_page(key)
st.markdown("---")

# ═════════════════════════════════════════════
# PAGE : GLOBAL
# ═════════════════════════════════════════════
if st.session_state.page == "global":
    st.subheader("Vue d'ensemble")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        df_h = get_hist()
        if df_h is not None and len(df_h) >= 5:
            v, vp = df_h['Valeur'].iloc[-1], df_h['Valeur'].iloc[-5]
            st.metric("💰 Finance", f"{v:,.0f} €", f"{((v - vp) / vp) * 100:+.2f}%")
        else:
            st.metric("💰 Finance", "—", "—")
        st.button("Explorer →", key="g_fin", on_click=set_page, args=("finance",))
    with c2:
        a_laver = sum(1 for v in wardrobe if needs_wash(v))
        st.metric("🧥 Style", f"{len(wardrobe) - a_laver} items OK", f"{a_laver} à laver")
        st.button("Garde-Robe →", key="g_hab", on_click=set_page, args=("habits",))
    with c3:
        st.metric("🏃 Santé", "2,150 kcal", "85%")
        st.button("Analyse →", key="g_san", on_click=set_page, args=("sante",))
    with c4:
        st.metric("🎓 Agenda", "3.8 GPA", "2 Tâches")
        st.button("Planning →", key="g_age", on_click=set_page, args=("agenda",))
    df_h = get_hist()
    if df_h is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Valeur'], name='Valeur',
                                 fill='tozeroy', fillcolor='rgba(59,130,246,.08)',
                                 line=dict(color='#3b82f6', width=2)))
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Investit'], name='Investi',
                                 line=dict(color='#64748b', width=1.5, dash='dash')))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(t=10, b=10, l=0, r=0), height=200,
                          xaxis=dict(gridcolor="#1e293b", color="#64748b"),
                          yaxis=dict(gridcolor="#1e293b", color="#64748b"),
                          legend=dict(orientation="h", x=0, y=1.1, font=dict(color="#94a3b8")))
        st.plotly_chart(fig, width='stretch')

# ═════════════════════════════════════════════
# PAGE : FINANCE
# ═════════════════════════════════════════════
elif st.session_state.page == "finance":
    st.header("📈 Portefeuille")
    with st.spinner("Chargement des cours…"):
        bourse = get_portfolio()
    if bourse:
        cols = st.columns(min(len(bourse), 6))
        for i, a in enumerate(bourse[:6]):
            ticker = str(a.get('Ticker', 'N/A'))
            prix = a.get('Prix_EUR', 0.0)
            rendement = a.get('Rendement_EUR', 0.0)
            # Affichage en pourcentage (ex: 0.05 -> 5.00%)
            cols[i].metric(ticker, f"{prix:.2f} €", f"{rendement * 100:+.2f}%")
    else:
        st.info(
            "ℹ️ Aucun actif trouvé dans votre portefeuille. Assurez-vous que le fichier 'finance/Portefeuille.xlsx' est présent et contient des données.")
    st.markdown("---")
    cl, cr = st.columns([2, 1])
    with cl:
        df_h = get_hist()
        if df_h is not None:
            df_h['Profit'] = df_h['Valeur'] - df_h['Investit']
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Valeur'], name='Valeur Totale',
                                     fill='tozeroy', fillcolor='rgba(59,130,246,.08)',
                                     line=dict(color='#3b82f6', width=2)))
            fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Investit'], name='Capital Investi',
                                     line=dict(color='#64748b', width=1.5, dash='dash')))

            # Benchmark CW8
            try:
                cw8_ticker = yf.Ticker("CW8.PA")
                cw8_hist = cw8_ticker.history(start=df_h.index.min(), end=df_h.index.max())['Close'].dropna()
                if not cw8_hist.empty:
                    # Aligner CW8 sur l'index de l'historique du portefeuille
                    cw8_hist.index = pd.to_datetime(cw8_hist.index).normalize().tz_localize(None)
                    df_h.index = pd.to_datetime(df_h.index).normalize().tz_localize(None)

                    cw8_aligned = cw8_hist.reindex(df_h.index).ffill().bfill()

                    # Calcul du benchmark prenant en compte les injections de capital
                    # On simule l'achat de CW8 à chaque fois qu'on a investi de l'argent
                    invested = df_h['Investit']
                    injections = invested.diff().fillna(invested.iloc[0])

                    # Éviter la division par zéro
                    cw8_safe = cw8_aligned.replace(0, np.nan).ffill()
                    # Valeur du benchmark = CW8_t * Somme(Injection_k / CW8_k)
                    cw8_norm = cw8_safe * (injections / cw8_safe).cumsum()

                    fig.add_trace(go.Scatter(x=cw8_norm.index, y=cw8_norm, name='Benchmark CW8 (Normalisé)',
                                             line=dict(color='#e9c46a', width=1, dash='dot')))
            except Exception as e:
                print(f"Erreur benchmark : {e}")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=10, b=10, l=0, r=0), height=300,
                              xaxis=dict(gridcolor="#1e293b", color="#64748b"),
                              yaxis=dict(gridcolor="#1e293b", color="#64748b"),
                              legend=dict(orientation="h", font=dict(color="#94a3b8")))
            st.plotly_chart(fig, width='stretch')
            ca, cb, cc = st.columns(3)
            p = df_h['Profit'].iloc[-1];
            ti = df_h['Investit'].iloc[-1]
            ca.metric("Plus-value", f"{p:,.0f} €", f"{(p / ti) * 100:+.2f}%")
            cb.metric("Investi", f"{ti:,.0f} €")
            cc.metric("Valeur", f"{df_h['Valeur'].iloc[-1]:,.0f} €")

            # Diversification & Risque
            st.markdown("---")
            d1, d2, d3 = st.columns(3)

            # Calcul robuste des poids (normalisation à 100% si nécessaire)
            weights = [a.get('Pct_Float', 0.0) for a in bourse] if bourse else []
            total_weight = sum(weights)

            if weights and total_weight > 0:
                # Normalisation interne pour les calculs de score
                norm_weights = [w / total_weight for w in weights]

                # Calcul de l'indice HHI ajusté (prend en compte la diversification interne des ETFs)
                # Pour une action seule, N=1. Pour un ETF Monde, on estime N=1500.
                hhi_adj = 0
                for a, nw in zip(bourse, norm_weights):
                    secteur = str(a.get('Secteur 1', '')).upper()
                    nom = str(a.get('Nom', '')).upper()
                    ticker = str(a.get('Ticker', '')).upper()

                    # Estimation du nombre de sous-jacents (N)
                    n_internal = 1
                    if "ETF" in secteur or "ETF" in nom or "MSCI" in nom or "WORLD" in nom:
                        if "WORLD" in nom or "CW8" in ticker:
                            n_internal = 1500
                        elif "S&P" in nom or "500" in nom:
                            n_internal = 500
                        else:
                            n_internal = 100  # ETF sectoriel par défaut

                    # Contribution au HHI ajusté : (poids^2) / N
                    hhi_adj += (nw ** 2) / n_internal

                # Score de diversification : 100% = parfaitement diversifié, 0% = 1 seule action
                # On utilise une échelle logarithmique pour refléter la réalité du risque
                div_score = max(0, min(100, (1 - np.sqrt(hhi_adj)) * 100))

                d1.metric("Score Diversification", f"{div_score:.1f}%",
                          help="Ce score prend en compte que vos ETFs (comme CW8) sont déjà diversifiés en interne. Un score proche de 100% indique un risque de concentration très faible.")

                # Volatilité Portefeuille (Moyenne pondérée)
                # On s'assure que la volatilité est bien en % pour l'affichage
                avg_vol = sum(a.get('Volatility', 0.0) * nw for a, nw in zip(bourse, norm_weights) if
                              not np.isnan(a.get('Volatility', 0.0)))

                # Si la volatilité moyenne est trop basse (ex: < 1%), on affiche une valeur par défaut ou on prévient
                display_vol = avg_vol * 100
                d2.metric("Volatilité Moyenne", f"{display_vol:.1f}%",
                          help="Moyenne pondérée de la volatilité annualisée (basée sur l'historique 1 an).")
            else:
                d1.metric("Score Diversification", "—")
                d2.metric("Volatilité Moyenne", "—")

            # Max Drawdown (Historique)
            roll_max = df_h['Valeur'].cummax()
            drawdown = (df_h['Valeur'] - roll_max) / roll_max
            max_dd = drawdown.min() * 100
            d3.metric("Max Drawdown", f"{max_dd:.1f}%", help="La plus grosse baisse historique du portefeuille")
    with cr:
        if bourse:
            dp = pd.DataFrame(bourse)

            cp = next((p for p in [os.path.join(BASE_DIR, 'finance', 'ToutBroker.csv'),
                                   os.path.join(BASE_DIR, 'ToutBroker.csv')] if os.path.exists(p)), None)

            dm = dp.copy()
            if cp:
                try:
                    db = pd.read_csv(cp, sep=';', encoding='latin-1', on_bad_lines='skip')
                    if 'Ticker' in db.columns:
                        # Drop overlapping columns from db to avoid _x/_y suffixes and overwriting
                        # We keep only 'Ticker' and columns NOT in dp
                        cols_to_keep = ['Ticker'] + [c for c in db.columns if
                                                     c not in dp.columns and c != 'Ticker']
                        db_subset = db[cols_to_keep]
                        dm = pd.merge(dp, db_subset, left_on='Ticker', right_on='Ticker', how='left')
                except:
                    pass

            # Ensure required columns exist in dm
            if 'Pays' not in dm.columns: dm['Pays'] = 'Inconnu'
            dm['Pays'] = dm['Pays'].fillna('Inconnu')

            for s_col in ['Secteur 2', 'Secteur 3']:
                if s_col not in dm.columns: dm[s_col] = 'Autre'
                dm[s_col] = dm[s_col].fillna('Autre')

            if 'Devise' not in dm.columns: dm['Devise'] = 'EUR'
            dm['Devise'] = dm['Devise'].fillna('EUR')

            if 'Pct_Float' not in dm.columns: dm['Pct_Float'] = 0.0
            dm['Pct_Float'] = pd.to_numeric(dm['Pct_Float'], errors='coerce').fillna(0.0)

            if 'Rendement_EUR' not in dm.columns: dm['Rendement_EUR'] = 0.0
            dm['Rendement_EUR'] = pd.to_numeric(dm['Rendement_EUR'], errors='coerce').fillna(0.0) * 100

            if 'Volatility' not in dm.columns: dm['Volatility'] = 0.0
            dm['Volatility'] = pd.to_numeric(dm['Volatility'], errors='coerce').fillna(0.0) * 100

            # Mapping Continents
            CONTINENTS = {
                'United Kingdom': 'Europe',
                'United States': 'North America',
                'Cayman Islands': 'North America',
                'Mexico': 'North America',
                'Canada': 'North America',
                'China': 'Asia',
                'Japan': 'Asia',
                'Kazakhstan': 'Asia',
                'Australia': 'Oceania',
                'South Korea': 'Asia',
                'India': 'Asia',
                'Israel': 'Asia',
                'Taiwan': 'Asia',
                'South Africa': 'Africa',
                'France': 'Europe',
                'Denmark': 'Europe',
                'Sweden': 'Europe',
                'Greece': 'Europe',
                'Germany': 'Europe'
            }
            dm['Continent'] = dm['Pays'].map(CONTINENTS).fillna('Autre')

            vue = st.radio("Afficher :", ["Secteurs", "Pays", "Devises", "Risque"], horizontal=True,
                           label_visibility="collapsed")

            if dm['Pct_Float'].sum() == 0:
                st.warning("⚠️ Les poids du portefeuille sont à 0. Vérifiez la colonne 'Poids' dans votre fichier.")
            else:
                if vue == "Secteurs":
                    fig = px.treemap(dm, path=['Secteur 1', 'Secteur 2', 'Secteur 3', 'Secteur 4', 'Secteur 5', 'Nom'],
                                     values='Pct_Float', color='Rendement_EUR',
                                     color_continuous_scale='RdYlGn',
                                     color_continuous_midpoint=0,
                                     custom_data=['Rendement_EUR', 'Pct_Float'],
                                     labels={'Rendement_EUR': 'Rendement'})
                elif vue == "Pays":
                    fig = px.treemap(dm, path=['Continent', 'Pays', 'Nom'],
                                     values='Pct_Float', color='Rendement_EUR',
                                     color_continuous_scale='RdYlGn',
                                     color_continuous_midpoint=0,
                                     custom_data=['Rendement_EUR', 'Pct_Float'],
                                     labels={'Rendement_EUR': 'Rendement'})
                elif vue == "Risque":
                    fig = px.scatter(dm, x='Volatility', y='Rendement_EUR', size='Pct_Float',
                                     color='Continent', hover_name='Nom',
                                     labels={'Volatility': 'Volatilité (%)', 'Rendement_EUR': 'Rendement'},
                                     title="Risque vs Rendement (Taille = Poids)")
                    fig.update_traces(marker=dict(line=dict(width=1, color='white')))

                    if len(dm) > 1:
                        st.markdown("---")
                        st.markdown("##### 🔗 Matrice de Corrélation (6 mois)")
                        try:
                            tickers = dm['Ticker'].tolist()
                            data = yf.download(tickers, period="6mo")['Close'].dropna()
                            if not data.empty:
                                corr = data.pct_change().corr()
                                fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale='RdBu_r',
                                                     zmin=-1, zmax=1)
                                fig_corr.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                                st.plotly_chart(fig_corr, width='stretch')
                        except:
                            st.warning("Impossible de charger les données de corrélation.")
                else:
                    dev_counts = dm.groupby('Devise')['Pct_Float'].sum().reset_index()
                    fig = px.pie(dev_counts, names='Devise', values='Pct_Float', hole=.4,
                                 color_discrete_sequence=px.colors.qualitative.Set3)
                    fig.update_layout(showlegend=False)

                if vue != "Risque":
                    if vue != "Devises":
                        fig.update_traces(
                            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%<br>%{customdata[1]:.2f}%",
                            textposition="middle center",
                            hovertemplate='<b>%{label}</b><br>Poids: %{value:.2f}%<br>Rendement: %{customdata[0]:+.2f}%'
                        )
                    else:
                        fig.update_traces(
                            textinfo="label+percent",
                            hovertemplate='<b>%{label}</b><br>Poids: %{value:.2f}%'
                        )

                st.plotly_chart(fig, width='stretch')

# ═════════════════════════════════════════════
# PAGE : HABITS
# ═════════════════════════════════════════════
elif st.session_state.page == "habits":
    st.header("🧥 Garde-Robe")

    if not wardrobe:
        st.error("vetements.json introuvable.")
        st.stop()

    # ── Météo & Suggestion ──────────────────────────────────────────────
    wx = get_weather()
    if "error" in wx:
        st.warning(f"⚠️ {wx['error']}")
        # Fallback values for suggestion
        wx_temp_min = 10.0
        wx_temp_max = 20.0
        wx_wind = 10.0
    else:
        wx_temp_min = wx.get('temp_min', 10.0)
        wx_temp_max = wx.get('temp_max', 20.0)
        wx_wind = wx.get('wind', 10.0)

    feels, pluie, snow, icon = get_weather_info(wx)

    # Suggestion initiale
    if not st.session_state.suggested or not any(st.session_state.tenue.values()):
        res = suggest_outfit(wardrobe, wx_temp_min, wx_temp_max, wx_wind, pluie)
        st.session_state.use_body = res.pop("__use_body", False)
        st.session_state.t_outfit = res.pop("__t_outfit", 15.0)
        st.session_state.tenue = res
        st.session_state.suggested = True

    # Calcul thermique global pour la page
    tenue = st.session_state.tenue
    total_thermal, target_thermal, gap = calculate_thermal_gap(tenue, feels, st.session_state.get('use_body', False))

    # Bandeaux météo
    extras = []
    if pluie:  extras.append("🌧 Pluie · Imperméable recommandé")
    if snow:   extras.append("❄️ Neige")
    if feels < 10: extras.append("🥶 Très froid · Écharpe conseillée")
    if st.session_state.use_body: extras.append("👕 Body actif")
    extra_html = "  ·  ".join(f"<span style='color:#60a5fa;font-size:.8em;'>{e}</span>" for e in extras)

    st.markdown(
        f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:10px;"
        f"padding:12px 20px;display:flex;align-items:center;gap:16px;margin-bottom:16px;'>"
        f"<div style='font-size:2em;'>{icon}</div>"
        f"<div>"
        f"<div style='color:#e2e8f0;font-weight:600;font-size:1.05em;'>"
        f"Montréal — {wx.get('temp', 'N/A')}°C "
        f"<span style='color:#64748b;font-size:.85em;'>(ressenti {feels}°C)</span>"
        f"{'  ' + extra_html if extra_html else ''}"
        f"</div>"
        f"<div style='color:#64748b;font-size:.8em;'>{wx.get('desc', 'Inconnu')} · Hum. {wx.get('humidity', 'N/A')}% · Vent {wx.get('wind', 'N/A')} km/h</div>"
        f"</div></div>",
        unsafe_allow_html=True)

    st.info(
        f"✨ **Tenue optimisée pour {st.session_state.t_outfit - 5:.1f}°C à {st.session_state.t_outfit + 5:.1f}°C.**\n\n"
        f"Il fera entre **{wx.get('temp_min', 'N/A')}°C** et **{wx.get('temp_max', 'N/A')}°C** à Montréal aujourd'hui (8h-23h).")

    # ── Tabs ───────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs(["👔 Tenue du Jour", "📦 Inventaire", "📊 Stats", "📜 Historique", "🚀 Recommandations"])


    def handle_resuggest():
        # Re-calculer les variables locales nécessaires
        wx_cb = get_weather()
        f_cb, p_cb, s_cb, i_cb = get_weather_info(wx_cb)

        if "error" in wx_cb:
            t_min_cb, t_max_cb, wind_cb = 10.0, 20.0, 10.0
        else:
            t_min_cb = wx_cb.get('temp_min', 10.0)
            t_max_cb = wx_cb.get('temp_max', 20.0)
            wind_cb = wx_cb.get('wind', 10.0)

        res = suggest_outfit(wardrobe, t_min_cb, t_max_cb, wind_cb, p_cb)
        st.session_state.use_body = res.pop("__use_body", False)
        st.session_state.t_outfit = res.pop("__t_outfit", 15.0)
        st.session_state.tenue = res
        st.session_state.suggested = True


    def handle_reset():
        st.session_state.tenue = {s["id"]: None for s in SLOTS}
        st.session_state.use_body = False


    # ══════════════════════════════════════════
    # TENUE DU JOUR
    # ══════════════════════════════════════════
    with t1:
        ba, bb, bc, _ = st.columns([2, 2, 3, 3])
        with ba:
            st.button("✨ Re-suggérer", on_click=handle_resuggest)
        with bb:
            st.button("🗑 Réinitialiser", on_click=handle_reset)
        with bc:
            # On utilise le toggle pour permettre la modification manuelle après suggestion
            st.toggle("👕 Body en coton (+1.5)", key="use_body")
        st.markdown("")


        # ─────────────────────────────────────────────────────────────────
        # RENDER D'UN SLOT — grille 10 cases pixel art
        # ─────────────────────────────────────────────────────────────────
        def render_slot(slot_id: str):
            cfg = next(s for s in SLOTS if s["id"] == slot_id)
            emoji = cfg["emoji"]
            cats = cfg["categories"]
            need = cfg["need"]
            item = st.session_state.tenue.get(slot_id)

            all_items = [v for v in wardrobe if v.get('categorie') in cats]
            nav_items = ([None] + all_items) if need != "ALWAYS" else all_items

            if need == "ALWAYS":
                tag_txt = "REQUIS";
                tag_col = "#3b82f6"
            elif need == "METEO":
                tag_txt = "MÉTÉO";
                tag_col = "#f59e0b"
            else:
                tag_txt = "OPT.";
                tag_col = "#334155"

            # Header du slot
            st.markdown(
                f"<p style='font-size:.65em;letter-spacing:.1em;text-transform:uppercase;"
                f"color:#64748b;margin-bottom:4px;'>"
                f"{emoji} {slot_id} "
                f"<span style='color:{tag_col};'>{tag_txt}</span></p>",
                unsafe_allow_html=True)

            if not nav_items:
                st.markdown(
                    "<div style='background:#0a0d14;border:1px dashed #1e293b;border-radius:10px;"
                    "height:110px;display:flex;align-items:center;justify-content:center;"
                    "color:#334155;font-size:.7em;'>Aucun item</div>",
                    unsafe_allow_html=True)
                return

            ca, cb, cc = st.columns([1, 6, 1])

            if ca.button("‹", key=f"prev_{slot_id}"):
                cur = nav_items.index(item) if item in nav_items else 0
                st.session_state.tenue[slot_id] = nav_items[(cur - 1) % len(nav_items)]
                st.rerun()

            with cb:
                if item:
                    prop = proprete_pct(item)
                    vie = vie_pct(item)
                    lav = needs_wash(item)
                    hs = is_worn_out(item)
                    bdg = badge_html(item)
                    avant = ports_avant_lavage(item)
                    ep = item.get('etat_propre', 60)
                    th = thermal_score(item)
                    border_col = "#ef4444" if (lav or hs) else (
                        "#3b82f6" if prop >= 70 else (
                            "#f59e0b" if prop >= 40 else "#ef4444"))

                    # Pixel art ou emoji fallback
                    ap = asset_path(item['id'])
                    if ap:
                        b64 = to_b64(ap)
                        img_block = (
                            f"<img src='data:image/png;base64,{b64}' "
                            f"style='height:72px;width:auto;image-rendering:pixelated;"
                            f"image-rendering:crisp-edges;margin-bottom:6px;' />")
                    else:
                        cat_emo = EMO_CAT.get(item.get('categorie', ''), emoji)
                        img_block = f"<div style='font-size:2.2em;margin-bottom:4px;'>{cat_emo}</div>"

                    st.markdown(
                        f"<div style='background:#0f172a;border:1px solid {border_col};"
                        f"border-radius:10px;padding:10px 8px;text-align:center;"
                        f"min-height:110px;display:flex;flex-direction:column;"
                        f"align-items:center;justify-content:center;gap:2px;'>"
                        f"{img_block}"
                        f"<div style='font-size:.72em;font-weight:600;color:#e2e8f0;"
                        f"line-height:1.2;max-width:100%;overflow:hidden;text-overflow:ellipsis;"
                        f"white-space:nowrap;'>{item['nom']}</div>"
                        f"<div style='font-size:.6em;color:#64748b;'>"
                        f"{item.get('couleur', '')} · 🌡 {th:.1f}/10</div>"
                        f"<div style='display:flex;gap:5px;margin-top:3px;"
                        f"align-items:center;justify-content:center;'>"
                        f"{bdg}"
                        f"<span style='font-size:.58em;color:#60a5fa;'>⚙{vie:.0f}%</span>"
                        f"</div>"
                        f"<div style='font-size:.56em;color:#475569;margin-top:2px;'>"
                        f"{avant}/{ep} avant lavage</div>"
                        f"</div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='background:#0a0d14;border:1px dashed #1e293b;"
                        f"border-radius:10px;height:110px;display:flex;flex-direction:column;"
                        f"align-items:center;justify-content:center;gap:6px;opacity:.45;'>"
                        f"<div style='font-size:1.8em;'>{emoji}</div>"
                        f"<div style='font-size:.62em;color:#334155;'>Non porté</div>"
                        f"</div>",
                        unsafe_allow_html=True)

            if cc.button("›", key=f"next_{slot_id}"):
                cur = nav_items.index(item) if item in nav_items else 0
                st.session_state.tenue[slot_id] = nav_items[(cur + 1) % len(nav_items)]
                st.rerun()


        # ── Grille 6 colonnes × 2 lignes ─────────────────────────────────
        st.markdown("#### Tenue sélectionnée")
        ROW1 = ["Manteau", "Veste", "Haut", "Pantalon", "Chaussures", "Echarpe"]
        ROW2 = ["Casquette", "Lunettes", "Bijoux 1", "Bijoux 2", "Montre", "Pendentif"]

        cols_r1 = st.columns(6)
        for i, sid in enumerate(ROW1):
            with cols_r1[i]:
                render_slot(sid)

        st.markdown("")
        cols_r2 = st.columns(6)
        for i, sid in enumerate(ROW2):
            with cols_r2[i]:
                render_slot(sid)

        # ── Score thermique global ────────────────────────────────────────
        worn = [v for v in st.session_state.tenue.values() if v is not None]
        if worn:
            th_col = "#4ade80" if abs(gap) < 3.0 else "#fb923c" if abs(gap) < 6.0 else "#f87171"

            # Recommandation Body
            body_rec = ""
            if gap > 4 and not st.session_state.get('use_body', False):
                body_rec = " · 💡 <span style='color:#fb923c;'>Body recommandé</span>"
            elif gap < -4 and st.session_state.get('use_body', False):
                body_rec = " · 💡 <span style='color:#60a5fa;'>Body facultatif</span>"

            st.markdown(
                f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:10px;"
                f"padding:12px 20px;margin-top:8px;display:flex;align-items:center;gap:20px;'>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:.62em;color:#64748b;letter-spacing:.1em;'>SCORE THERMIQUE</div>"
                f"<div style='font-size:1.4em;font-weight:700;color:{th_col};'>"
                f"{total_thermal:.1f} / {target_thermal:.1f}</div>"
                f"<div style='font-size:.62em;color:#475569;'>tenue / cible</div>"
                f"</div>"
                f"<div style='flex:1;font-size:.72em;color:#64748b;'>"
                f"Ressenti = {feels:.1f}°C · "
                f"Gap = {gap:+.1f}"
                f"{body_rec}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True)

        # ── Résumé + Validation ───────────────────────────
        st.markdown("---")

        # Slots obligatoires manquants
        manquants = []
        for sc in SLOTS:
            sid = sc["id"]
            if sc["need"] == "ALWAYS" and tenue.get(sid) is None:
                manquants.append(sc["emoji"] + " " + sid)
            elif sc["need"] == "METEO":
                t = sc.get("trigger", "")
                requis = (feels < 20 or pluie) if t == "cold_or_rain" else (feels < 10)
                if requis and tenue.get(sid) is None:
                    has_items = any(v.get('categorie') in sc["categories"] for v in wardrobe)
                    if has_items:
                        manquants.append(sc["emoji"] + " " + sid + " (météo)")

        # Items qui nécessitent un lavage
        sale_selectionnes = [i for i in worn if needs_wash(i)]

        if manquants:
            st.warning("⚠️ Slots requis : **" + ", ".join(manquants) + "**")
        if sale_selectionnes:
            noms = ", ".join(i['nom'] for i in sale_selectionnes)
            st.error("🧺 À laver avant de remettre : **" + noms + "**")

        if worn:
            r1, r2, r3 = st.columns(3)
            tmin = max(i.get('temp_min', -30) for i in worn)
            tmax = min(i.get('temp_max', 40) for i in worn)

            # Handle multi-style items for display
            all_styles = set()
            for i in worn:
                s = i.get('style', '')
                if isinstance(s, list):
                    all_styles.update(s)
                elif s:
                    all_styles.add(s)
            sts = list(all_styles)

            r1.metric("🌡️ Plage", f"{tmin}°→{tmax}°C", "✓" if tmin <= feels <= tmax else "⚠")
            r2.metric("🧥 Score Thermique", f"{total_thermal:.1f}", f"Cible: {target_thermal:.1f}")

            # Calculate style score for current selection
            current_score = style_score(worn)
            r3.metric("🎨 Score Style", f"{current_score:.0f}%", " + ".join(sts[:2]))

            # Color distribution for verification
            colors = [i.get('couleur', '') for i in worn if i.get('couleur')]
            total_colors = len(colors)
            if total_colors > 0:
                counts = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
                for c in colors:
                    counts[get_color_category(c)] += 1

                n_pct = (counts["Neutre"] / total_colors) * 100
                s_pct = (counts["Secondaire"] / total_colors) * 100
                a_pct = (counts["Accent"] / total_colors) * 100

                st.markdown(
                    f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:8px 12px;margin-top:10px;font-size:0.75em;color:#94a3b8;'>"
                    f"<b>📊 Distribution des couleurs ({total_colors} items) :</b><br>"
                    f"<span style='color:#e2e8f0;'>Neutre: {n_pct:.0f}%</span> (cible 60%) · "
                    f"<span style='color:#60a5fa;'>Secondaire: {s_pct:.0f}%</span> (cible 30%) · "
                    f"<span style='color:#fb923c;'>Accent: {a_pct:.0f}%</span> (cible 10%)"
                    f"</div>",
                    unsafe_allow_html=True
                )

            if gap > 5 and not st.session_state.use_body:
                st.warning("💡 Conseil : Ajoute un **body en coton** pour plus de chaleur.")
            elif gap < -5 and st.session_state.use_body:
                st.info("💡 Conseil : Tu peux retirer le body, il fait assez chaud.")

            st.markdown("")
            _, cbv, _ = st.columns([1, 4, 1])
            with cbv:
                can_go = not manquants and not sale_selectionnes
                if st.button("✅  PORTER CETTE TENUE AUJOURD'HUI", key="valider", type="primary", disabled=not can_go):
                    updated = load_wardrobe()
                    ids_worn = {i['id'] for i in worn}
                    log = []
                    for itm in updated:
                        if itm['id'] in ids_worn:
                            itm['portes'] = itm.get('portes', 0) + 1
                            p = itm['portes']
                            ep = itm.get('etat_propre', 60)
                            lav_now = (p % ep == 0) and p > 0
                            avant_n = ep - (p % ep) if not lav_now else 0
                            log.append({"nom": itm['nom'], "portes": p, "lav_now": lav_now,
                                        "avant": avant_n, "ep": ep, "vie": vie_pct(itm)})
                    save_wardrobe(updated)
                    save_history(st.session_state.tenue)
                    st.session_state.suggested = False
                    st.session_state.tenue = {s["id"]: None for s in SLOTS}
                    st.success(f"✅ {len(worn)} items mis à jour.")
                    for l in log:
                        if l['lav_now']:
                            st.markdown(
                                f"• 🧺 **{l['nom']}** — {l['portes']} ports → **À laver !** (fréquence: {l['ep']})")
                        else:
                            st.markdown(
                                f"• **{l['nom']}** — {l['portes']} ports · lavage dans {l['avant']} ports · vie {l['vie']:.0f}%")
                    st.balloons()
                if not can_go and sale_selectionnes:
                    st.caption("Retire les items à laver pour valider.")
                elif not can_go:
                    st.caption("Complète les slots obligatoires.")
        else:
            st.info("Aucun item sélectionné. Clique sur **✨ Re-suggérer**.")

    # ══════════════════════════════════════════
    # INVENTAIRE
    # ══════════════════════════════════════════
    with t2:
        f1, f2, f3 = st.columns(3)
        # Catégories dynamiques depuis le JSON
        all_cats = sorted(set(v.get('categorie', '') for v in wardrobe if v.get('categorie')))
        cat_f = f1.selectbox("Catégorie", ["Toutes"] + all_cats)

        # Handle multi-style items for filter
        all_styles_set = set()
        for v in wardrobe:
            s = v.get('style', '')
            if isinstance(s, list):
                all_styles_set.update(s)
            elif s:
                all_styles_set.add(s)
        all_styl = sorted(list(all_styles_set))

        sty_f = f2.selectbox("Style", ["Tous"] + all_styl)
        eta_f = f3.selectbox("État", ["Tous", "✓ Propres", "⚠ Mi-sales", "🧺 À laver", "💀 HS"])

        items_f = wardrobe.copy()
        if cat_f != "Toutes": items_f = [v for v in items_f if v.get('categorie') == cat_f]
        if sty_f != "Tous":
            items_f = [v for v in items_f if
                       (sty_f == v.get('style') if isinstance(v.get('style'), str) else sty_f in v.get('style', []))]
        if eta_f == "✓ Propres":
            items_f = [v for v in items_f if proprete_pct(v) >= 70 and not needs_wash(v)]
        elif eta_f == "⚠ Mi-sales":
            items_f = [v for v in items_f if 30 <= proprete_pct(v) < 70]
        elif eta_f == "🧺 À laver":
            items_f = [v for v in items_f if needs_wash(v)]
        elif eta_f == "💀 HS":
            items_f = [v for v in items_f if is_worn_out(v)]

        st.markdown("---")
        if not items_f:
            st.info("Aucun vêtement ne correspond à ces critères.")
        else:
            cols = st.columns(4)
            for idx, item in enumerate(items_f):
                with cols[idx % 4]:
                    pct = proprete_pct(item)
                    vie = vie_pct(item)

                    # Color based on state
                    if needs_wash(item):
                        bg, brd = "#2d0a0a", "#7f1d1d"
                    elif pct < 50:
                        bg, brd = "#2d1a0a", "#7c2d12"
                    else:
                        bg, brd = "#0f172a", "#1e293b"

                    # Pixel art ou emoji fallback
                    ap = asset_path(item['id'])
                    if ap:
                        b64 = to_b64(ap)
                        img_block = (
                            f"<img src='data:image/png;base64,{b64}' "
                            f"style='height:64px;width:auto;image-rendering:pixelated;"
                            f"image-rendering:crisp-edges;margin-bottom:6px;' />")
                    else:
                        emo = EMO_CAT.get(item.get('categorie', ''), '👔')
                        img_block = f"<div style='font-size:1.8em;margin-bottom:4px;'>{emo}</div>"

                    st.markdown(
                        f"<div style='background:{bg};border:1px solid {brd};border-radius:8px;padding:12px 8px;text-align:center;margin-bottom:10px;min-height:140px;display:flex;flex-direction:column;align-items:center;justify-content:center;'>"
                        f"{img_block}"
                        f"<div style='font-size:.75em;font-weight:600;color:#e2e8f0;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;width:100%;'>{item['nom']}</div>"
                        f"<div style='font-size:.6em;color:#64748b;'>{item.get('marque', '')} · {item.get('couleur', '')}</div>"
                        f"<div style='display:flex;justify-content:center;gap:8px;margin-top:6px;'>"
                        f"<span style='font-size:.55em;color:#94a3b8;'>🧼 {pct:.0f}%</span>"
                        f"<span style='font-size:.55em;color:#60a5fa;'>⚙️ {vie:.0f}%</span>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
    # 📊 Stats
    # ══════════════════════════════════════════
    with t3:
        df_g = pd.DataFrame(wardrobe)
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**Par Catégorie**")
            cat_counts = df_g['categorie'].value_counts().reset_index()
            cat_counts.columns = ['Catégorie', 'Nombre']
            fig = px.pie(cat_counts, names='Catégorie', values='Nombre', hole=.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=10, l=0, r=0, b=10),
                              legend=dict(font=dict(color="#94a3b8")))
            st.plotly_chart(fig, width='stretch')
        with r2:
            st.markdown("**Palette de Couleurs**")
            color_counts = df_g['couleur'].value_counts().reset_index()
            color_counts.columns = ['Couleur', 'Nombre']
            fig = px.bar(color_counts, x='Nombre', y='Couleur', orientation='h',
                         color='Couleur', color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=10, l=0, r=0, b=10),
                              xaxis=dict(gridcolor="#1e293b", color="#64748b"),
                              yaxis=dict(gridcolor="#1e293b", color="#64748b"),
                              showlegend=False)
            st.plotly_chart(fig, width='stretch')

        st.markdown("---")
        st.markdown("#### 🧺 À laver maintenant")
        lav_list = [v for v in wardrobe if needs_wash(v)]
        if lav_list:
            for itm in lav_list:
                ap = asset_path(itm['id'])
                if ap:
                    b64 = to_b64(ap)
                    img_block = (
                        f"<img src='data:image/png;base64,{b64}' "
                        f"style='height:32px;width:auto;image-rendering:pixelated;"
                        f"image-rendering:crisp-edges;' />")
                else:
                    e = EMO_CAT.get(itm.get('categorie', ''), '👔')
                    img_block = f"<div style='font-size:1.2em;'>{e}</div>"

                p = itm.get('portes', 0);
                ep = itm.get('etat_propre', 60)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:12px;padding:8px 12px;"
                    f"background:#2d0a0a;border-radius:8px;margin-bottom:6px;border:1px solid #7f1d1d;'>"
                    f"<div style='width:40px;display:flex;justify-content:center;'>{img_block}</div>"
                    f"<div style='flex:1;'>"
                    f"<div style='font-size:.85em;color:#e2e8f0;font-weight:500;'>{itm['nom']}</div>"
                    f"<div style='font-size:.7em;color:#64748b;'>{itm.get('marque', '')} · {p} ports · lavage /{ep}</div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True)

    # 📜 Historique
    with t4:
        st.markdown("#### Dernières tenues portées")
        history = load_history()
        if history:
            for entry in reversed(history[-10:]):
                st.write(f"📅 **{entry['date']}**")
                items = [v['nom'] for v in entry['tenue'].values() if v]
                st.caption(", ".join(items))
        else:
            st.info("Aucun historique pour le moment.")

    # 🚀 Recommandations
    with t5:
        st.markdown("#### 🛍 Suggestions d'achats")
        recs = get_purchase_recommendations(wardrobe)
        if recs:
            for r in recs:
                # Icon based on type
                icon = "📦"
                if r.get("type") == "Basique":
                    icon = "💎"
                elif r.get("type") == "Polyvalence":
                    icon = "🔄"
                elif r.get("type") == "Harmonie":
                    icon = "🎨"
                elif r.get("type") == "Style":
                    icon = "✨"

                pot = r.get("potentiel", 50)
                pot_col = "#4ade80" if pot >= 80 else "#fb923c" if pot >= 60 else "#94a3b8"

                st.markdown(
                    f"<div style='background:#111827;border:1px solid #1e293b;border-radius:12px;padding:16px;margin-bottom:12px;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
                    f"<div style='display:flex;gap:12px;'>"
                    f"<div style='font-size:1.5em;'>{icon}</div>"
                    f"<div>"
                    f"<div style='font-size:1em;font-weight:700;color:#f8fafc;'>{r['nom']}</div>"
                    f"<div style='font-size:.75em;color:#94a3b8;margin-top:4px;line-height:1.4;'>{r['raison']}</div>"
                    f"</div>"
                    f"</div>"
                    f"<div style='background:{pot_col}22;color:{pot_col};padding:4px 8px;border-radius:6px;font-size:.65em;font-weight:700;border:1px solid {pot_col}44;'>"
                    f"POTENTIEL {pot}%"
                    f"</div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.success("Ta garde-robe est équilibrée !")

elif st.session_state.page == "sante":
    st.header("🍎 Santé & Nutrition")
    sante_data = load_sante()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Get today's entry if it exists
    today_entry = next((e for e in sante_data if e['date'] == today_str), {})

    # Get last known weight
    last_weight = 75.0
    if sante_data:
        for entry in reversed(sante_data):
            if 'poids' in entry:
                last_weight = entry['poids']
                break

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### ⚖️ Suivi du Poids")
        with st.form("weight_form"):
            current_weight = st.number_input("Poids du jour (kg)", min_value=40.0, max_value=200.0,
                                             value=today_entry.get('poids', last_weight), step=0.1)

            if st.form_submit_button("Enregistrer & Optimiser"):
                # Update today's weight
                sante_data = update_sante_data(sante_data, today_str, weight=current_weight)

                # Auto-Optimization
                base_t, daily_targets = calculate_daily_targets(current_weight, today_str, sante_data)
                plan, msg = optimize_nutrition(daily_targets)

                if plan:
                    totals = calculate_plan_totals(plan)
                    update_sante_data(sante_data, today_str, weight=current_weight, targets=daily_targets,
                                      base_targets=base_t, consumed=totals, foods=plan)
                    st.session_state.nutrition_plan = plan
                    if msg: st.warning(msg)
                    st.success("Poids enregistré et diète du jour générée !")
                else:
                    st.error(f"Erreur d'optimisation : {msg}")

                st.rerun()

        if sante_data:
            df_sante = pd.DataFrame(sante_data)
            if 'poids' in df_sante.columns:
                df_plot = df_sante.dropna(subset=['poids'])
                if not df_plot.empty:
                    fig_weight = px.line(df_plot, x='date', y='poids', title="Évolution du Poids", markers=True)
                    fig_weight.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                             font_color="#94a3b8")
                    st.plotly_chart(fig_weight, width='stretch')

            # Calculate daily targets (base and compensated)
            base_t, targets = calculate_daily_targets(current_weight, today_str, sante_data)

            st.markdown(f"#### 🎯 Objectifs du Jour")
            is_sport = datetime.strptime(today_str, "%Y-%m-%d").weekday() < 5
            st.caption(f"{'💪 Jour de Sport' if is_sport else '休 Jour de Repos'} | 📈 Compensé avec l'écart d'hier")

            c1, c2 = st.columns(2)
            c1.write(f"**Calories :** {targets['Calories']:.0f} kcal")
            c1.write(f"**Protéines :** {targets['Protéines']:.1f}g")
            c1.write(f"**Lipides :** {targets['Lipides']:.1f}g")
            c2.write(f"**Glucides :** {targets['Glucides']:.1f}g")
            c2.write(f"**Fibres :** {targets['Fibres']:.0f}g")
            c2.write(f"**Sodium :** < {targets['Sodium_Max']:.0f}mg")

            with st.expander("Détails Micronutriments"):
                st.write(f"**Magnésium :** {targets['Magnésium']:.0f}mg")
                st.write(f"**Omega-3 :** {targets['Omega3']:.1f}g")
                st.write(f"**Vitamine C :** {targets['VitC']:.0f}mg")
                st.write(f"**Fer :** {targets['Fer']:.0f}mg")
                st.write(f"**Zinc :** {targets['Zinc']:.0f}mg")
                st.write(f"**Calcium :** {targets['Calcium']:.0f}mg")

    with col2:
        st.markdown("#### 🍴 Plan Nutritionnel du Jour")
        st.caption("Plan optimisé pour aujourd'hui selon ton poids et ton historique.")

        if sante_data:
            # Plan is automatically generated on weight entry, but we can also have a manual button
            if st.button("🔄 Re-générer la diète du jour", type="secondary"):
                with st.spinner("Optimisation en cours..."):
                    base_t, daily_targets = calculate_daily_targets(current_weight, today_str, sante_data)
                    plan, msg = optimize_nutrition(daily_targets)
                    if plan:
                        st.session_state.nutrition_plan = plan
                        totals = calculate_plan_totals(plan)
                        update_sante_data(sante_data, today_str, targets=daily_targets, base_targets=base_t,
                                          consumed=totals, foods=plan)
                    else:
                        st.error(msg)

            # Load plan from session state or from today's entry
            plan = st.session_state.get('nutrition_plan', today_entry.get('foods', []))

            if plan:
                # Custom HTML Table for styling
                table_html = """<table style='width:100%; border-collapse: collapse; font-size: 0.85em;'>
<thead>
<tr style='border-bottom: 1px solid #1e293b; text-align: left;'>
<th style='padding: 8px;'>Aliment</th>
<th style='padding: 8px;'>Quantité</th>
<th style='padding: 8px;'>Calories</th>
<th style='padding: 8px;'>Protéines</th>
<th style='padding: 8px;'>Prix</th>
</tr>
</thead>
<tbody>"""

                for item in plan:
                    color = "#f87171" if item.get('is_extra') else "#e2e8f0"
                    weight = "bold" if item.get('is_extra') else "normal"
                    extra_info = f" (+{item['diff_qty']:.0f}g)" if item.get('is_extra') else ""

                    # Special handling for supplements units
                    try:
                        # Handle string with 'g' suffix
                        raw_qty = str(item['Quantité']).replace('g', '')
                        qty_val = float(raw_qty)
                    except (ValueError, TypeError):
                        qty_val = 0.0

                    display_qty = f"{qty_val:.2f}g"
                    if qty_val >= 1.0:
                        display_qty = f"{qty_val:.0f}g"

                    if "Liquide" in item['Aliment'] or "Trophic" in item['Aliment']:
                        # 1 drop is approx 0.03g
                        gouttes = qty_val / 0.03
                        display_qty = f"{gouttes:.1f} gouttes"
                    elif "Gélules" in item['Aliment'] or "Now" in item['Aliment']:
                        # 1 softgel is approx 0.5g
                        gelules = qty_val / 0.5
                        display_qty = f"{gelules:.1f} gélules"

                    table_html += f"""
<tr style='border-bottom: 1px solid #0f172a; color: {color}; font-weight: {weight};'>
<td style='padding: 8px;'>{item['Aliment']}</td>
<td style='padding: 8px;'>{display_qty}{extra_info}</td>
<td style='padding: 8px;'>{item['Calories']:.0f} kcal</td>
<td style='padding: 8px;'>{item['Protéines']:.1f}g</td>
<td style='padding: 8px;'>{item['Prix']:.2f} CAD</td>
</tr>"""

                table_html += "</tbody></table>"
                st.markdown(table_html, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                # Calcul des totaux réels
                totals = calculate_plan_totals(plan)

                c1, c2, c3 = st.columns(3)
                c1.metric("Coût Total", f"{totals['Prix']:.2f} CAD")
                c2.metric("Calories", f"{round(totals['Calories'])} kcal")
                c3.metric("Protéines", f"{round(totals['Protéines'])} g")

                st.markdown("#### 📊 Performance vs Objectifs")


                # Helper to show progress
                def show_progress(label, current, target, unit="", is_max=False):
                    if target > 0:
                        percent = current / target
                        if is_max:
                            status = "✅" if percent <= 1.0 else "⚠️"
                        else:
                            status = "✅" if 0.95 <= percent <= 1.05 else "⚠️"

                        st.write(
                            f"{status} **{label}** : {current:.1f}{unit} / {target:.1f}{unit} ({percent * 100:.1f}%)")
                        st.progress(min(percent, 1.0))
                    else:
                        st.write(f"**{label}** : {current:.1f}{unit}")


                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    show_progress("Calories", totals.get('Calories', 0), targets['Calories'], " kcal")
                    show_progress("Protéines", totals.get('Protéines', 0), targets['Protéines'], "g")
                    show_progress("Lipides", totals.get('Lipides', 0), targets['Lipides'], "g")
                    show_progress("Glucides", totals.get('Glucides', 0), targets['Glucides'], "g")

                with col_p2:
                    show_progress("Fibres", totals.get('Fibres', 0), targets['Fibres'], "g")
                    show_progress("Sucres", totals.get('Sucres_Max', 0), targets['Sucres_Max'], "g", is_max=True)
                    show_progress("Sodium", totals.get('Sodium_Max', 0), targets['Sodium_Max'], "mg", is_max=True)
                    show_progress("Cholestérol", totals.get('Cholesterol_Max', 0), targets['Cholesterol_Max'], "mg",
                                  is_max=True)

                with st.expander("Toutes les Vitamines & Minéraux"):
                    st.markdown("##### 💊 Vitamines")
                    v_cols = st.columns(2)
                    vitamins = [
                        ("Vitamine A", 'VitA', 'VitA', "µg"),
                        ("Vitamine B1", 'VitB1', 'VitB1', "mg"),
                        ("Vitamine B2", 'VitB2', 'VitB2', "mg"),
                        ("Vitamine B3", 'VitB3', 'VitB3', "mg"),
                        ("Vitamine B5", 'VitB5', 'VitB5', "mg"),
                        ("Vitamine B6", 'VitB6', 'VitB6', "mg"),
                        ("Vitamine B9", 'VitB9', 'VitB9', "µg"),
                        ("Vitamine B12", 'VitB12', 'VitB12', "µg"),
                        ("Vitamine C", 'VitC', 'VitC', "mg"),
                        ("Vitamine D", 'VitD', 'VitD', "µg"),
                        ("Vitamine E", 'VitE', 'VitE', "mg"),
                        ("Vitamine K", 'VitK', 'VitK', "µg"),
                    ]
                    for i, (label, t_key, d_col, unit) in enumerate(vitamins):
                        with v_cols[i % 2]:
                            show_progress(label, totals.get(d_col, 0), targets[t_key], unit)

                    st.markdown("---")
                    st.markdown("##### 💎 Minéraux")
                    m_cols = st.columns(2)
                    minerals = [
                        ("Magnésium", 'Magnésium', 'Magnésium', "mg"),
                        ("Fer", 'Fer', 'Fer', "mg"),
                        ("Zinc", 'Zinc', 'Zinc', "mg"),
                        ("Calcium", 'Calcium', 'Calcium', "mg"),
                        ("Potassium", 'Potassium', 'Potassium', "mg"),
                        ("Chlorure", 'Chlorure', 'Chlorure', "mg"),
                        ("Cuivre", 'Cuivre', 'Cuivre', "mg"),
                        ("Iode", 'Iode', 'Iode', "µg"),
                        ("Manganèse", 'Manganèse', 'Manganèse', "mg"),
                        ("Phosphore", 'Phosphore', 'Phosphore', "mg"),
                        ("Sélénium", 'Sélénium', 'Sélénium', "µg"),
                    ]
                    for i, (label, t_key, d_col, unit) in enumerate(minerals):
                        with m_cols[i % 2]:
                            show_progress(label, totals.get(d_col, 0), targets[t_key], unit)

                    st.markdown("---")
                    st.markdown("##### 🧬 Autres")
                    o_cols = st.columns(2)
                    others = [
                        ("Omega-3", 'Omega3', 'Omega 3', "g"),
                    ]
                    for i, (label, t_key, d_col, unit) in enumerate(others):
                        with o_cols[i % 2]:
                            show_progress(label, totals.get(d_col, 0), targets[t_key], unit)
        else:
            st.info("Entrez votre poids pour commencer l'optimisation.")

elif st.session_state.page == "agenda":
    st.header("📅 Agenda & Réussite Académique")
    agenda_data = load_agenda()
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### 🏫 Cours UQAM")
        for cours in agenda_data["cours"]:
            st.info(f"{cours['heure']} — {cours['nom']} ({cours['local']})")
    with col2:
        st.markdown("#### ☕ Travail (Barista)")
        st.write(f"**Prochaine shift :** {agenda_data['travail']['prochain']}")
        st.write("**Heures cette semaine :** 15h")