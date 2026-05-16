import os
import pandas as pd
import yfinance as yf
import streamlit as st
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINANCE_DIR = os.path.join(BASE_DIR, 'finance')


@st.cache_data(ttl=3600)
def get_hist():
    path = os.path.join(FINANCE_DIR, 'Historique_portefeuille.xlsx')
    if not os.path.exists(path):
        return None
    df = pd.read_excel(path, index_col=0)
    df.index = pd.to_datetime(df.index, dayfirst=True)
    return df


@st.cache_data(ttl=3600)
def get_portfolio():
    path_xlsx = os.path.join(FINANCE_DIR, 'ToutBroker.xlsx')
    path_csv = os.path.join(FINANCE_DIR, 'ToutBroker.csv')

    df = None
    if os.path.exists(path_xlsx):
        try:
            df = pd.read_excel(path_xlsx)
        except:
            pass

    if (df is None or df.empty) and os.path.exists(path_csv):
        try:
            df = pd.read_csv(path_csv, sep=';', encoding='latin-1', on_bad_lines='skip')
        except Exception as e:
            st.error(f"Erreur lors de la lecture du CSV : {e}")
            return []

    if df is None or df.empty:
        return []

    # Normalisation des noms de colonnes
    rename_map = {
        'Ticker Yahoo Finance': 'Ticker',
        'Poids': 'Pct_Float',
        'Prix': 'Prix_EUR'
    }
    df = df.rename(columns=rename_map)

    if 'Ticker' not in df.columns:
        # Recherche d'une colonne contenant "Ticker" si absent
        potential = [c for c in df.columns if 'Ticker' in c]
        if potential:
            df = df.rename(columns={potential[0]: 'Ticker'})
        else:
            return []

    if 'Pct_Float' not in df.columns:
        return []

    df['Pct_Float'] = pd.to_numeric(df['Pct_Float'], errors='coerce').fillna(0.0)

    # On ne garde que les lignes avec un poids > 0
    df = df[df['Pct_Float'] > 0].copy()

    if df.empty:
        return []

    # Si la somme est <= 1.1, on considère que c'est en décimal (0.40 au lieu de 40%)
    if df['Pct_Float'].sum() <= 1.1:
        df['Pct_Float'] = df['Pct_Float'] * 100

    colonnes_manquantes = {
        'Rendement_EUR': 0.0,
        'Volatility': 0.0,
        'Pays': 'Inconnu',
        'Devise': 'Unknown'
    }
    for col, default in colonnes_manquantes.items():
        if col not in df.columns:
            df[col] = default

    # Nettoyage des tickers (important pour éviter le bug 0.0)
    df['Ticker'] = df['Ticker'].astype(str).str.strip()
    df = df[df['Ticker'] != 'nan'].copy()
    df = df[df['Ticker'] != ''].copy()

    df['Prix_EUR'] = pd.to_numeric(df['Prix_EUR'], errors='coerce').fillna(0.0)

    records = df.to_dict('records')
    fx_cache = {}

    for rec in records:
        if rec['Ticker'] != 'Unknown' and rec['Ticker'] != 'nan':
            try:
                ticker_data = yf.Ticker(rec['Ticker'])

                # CORRECTION 1 : Récupération ultra-sécurisée de la devise (sans .get() sur fast_info)
                try:
                    devise = ticker_data.fast_info['currency']
                except:
                    try:
                        devise = ticker_data.info.get('currency', 'EUR')
                    except:
                        devise = 'EUR'

                rec['Devise'] = devise

                # Utilisation d'une période plus longue pour une volatilité plus stable (1 an)
                hist = ticker_data.history(period="1y")

                if not hist.empty:
                    closes = hist['Close'].dropna()

                    # On s'assure d'avoir au moins 10 jours de cotation pour la volatilité
                    if len(closes) >= 10:
                        # ... (reste de l'alignement FX)

                        # CORRECTION 2 : Retrait du fuseau horaire uniquement s'il y en a un
                        closes.index = pd.to_datetime(closes.index).normalize()
                        if closes.index.tz is not None:
                            closes.index = closes.index.tz_localize(None)

                        if devise != 'EUR' and pd.notna(devise):
                            fx_ticker = f"{devise}EUR=X"

                            if fx_ticker not in fx_cache:
                                fx_data = yf.Ticker(fx_ticker).history(period="1mo")
                                if not fx_data.empty:
                                    fx_closes_clean = fx_data['Close'].dropna()
                                    fx_closes_clean.index = pd.to_datetime(fx_closes_clean.index).normalize()
                                    if fx_closes_clean.index.tz is not None:
                                        fx_closes_clean.index = fx_closes_clean.index.tz_localize(None)
                                    fx_cache[fx_ticker] = fx_closes_clean
                                else:
                                    fx_cache[fx_ticker] = None

                            fx_closes = fx_cache[fx_ticker]

                            if fx_closes is not None:
                                fx_aligned = fx_closes.reindex(closes.index).ffill().bfill()
                                closes = closes * fx_aligned

                        # Calcul du Rendement (sur le dernier mois pour la pertinence court terme)
                        hist_1m = ticker_data.history(period="1mo")
                        if not hist_1m.empty:
                            c_1m = hist_1m['Close'].dropna()
                            if len(c_1m) > 1:
                                rec['Rendement_EUR'] = float((c_1m.iloc[-1] / c_1m.iloc[0]) - 1)

                        # CORRECTION 3 : Calcul de la Volatilité (annualisée sur 1 an)
                        daily_returns = closes.pct_change().dropna()
                        if len(daily_returns) > 5:
                            # On utilise l'écart-type des rendements quotidiens
                            vol_annuelle = float(daily_returns.std() * np.sqrt(252))
                            # On s'assure que la volatilité n'est pas aberrante (ex: 0.0001)
                            if vol_annuelle > 0.001:
                                rec['Volatility'] = vol_annuelle
                            else:
                                # Fallback si la volatilité est quasi-nulle (erreur de données ?)
                                rec['Volatility'] = 0.15  # Valeur par défaut raisonnable pour un actif risqué

                # CORRECTION 4 : Récupération du prix sans risque de plantage
                if rec['Prix_EUR'] == 0.0:
                    try:
                        if not hist.empty:
                            rec['Prix_EUR'] = float(hist['Close'].iloc[-1])
                        else:
                            rec['Prix_EUR'] = float(ticker_data.fast_info['last_price'])
                    except:
                        pass

            except Exception as e:
                # CORRECTION 5 : On loggue l'erreur pour comprendre ce qui bloque si ça arrive encore
                print(f"⚠️ Erreur avec le ticker {rec['Ticker']} : {e}")

    return records
