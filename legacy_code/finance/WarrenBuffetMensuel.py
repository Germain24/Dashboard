import os
import time
import json
import threading
import warnings
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import yfinance as yf
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import kendalltau
from tqdm import tqdm

warnings.filterwarnings('ignore')


# ==================== CONFIGURATION ====================
class Config:
    DATA_DIR = "data"
    FOLDER_PATH = os.path.join(DATA_DIR, "financials_by_company")
    OUTPUT_DIR = Path(FOLDER_PATH)
    TICKERS_CSV = "tickers.csv"
    EXCEL_FILE = "ToutBroker.xlsx"
    CACHE_FILE = os.path.join(DATA_DIR, "cache_status.json")
    REPORT_FILE = os.path.join(DATA_DIR, "analysis_report.txt")
    ERROR_LOG_FILE = os.path.join(DATA_DIR, "error_log.txt")
    PARAMS_FILE = "params.json"

    # Valeurs par défaut
    MAX_AGE_YEARS = 1
    CURRENT_YEAR = datetime.now().year
    SCORE_THRESHOLD = 80
    MAX_REQUESTS_PER_HOUR = 2000
    REQUESTS_PER_TICKER = 4
    PER_MAX = 40
    PEG_MAX = 1.0
    TAUX_DEFAUT = 0.04
    TAUX_OBLIGATAIRES = {
        'United States': 0.042, 'France': 0.029, 'Germany': 0.024, 'United Kingdom': 0.040,
        'Switzerland': 0.007, 'Canada': 0.035, 'Japan': 0.008, 'China': 0.023, 'India': 0.067,
        'South Korea': 0.030, 'Australia': 0.043, 'Hong Kong': 0.038, 'Taiwan': 0.015,
        'Brazil': 0.135, 'Mexico': 0.095, 'Sweden': 0.020, 'Netherlands': 0.027,
        'Belgium': 0.030, 'Denmark': 0.025, 'Norway': 0.035, 'Israel': 0.045,
        'Singapore': 0.030, 'South Africa': 0.095, 'Indonesia': 0.068, 'Turkey': 0.280,
    }

    # Paramètres de l'optimiseur
    SHARPE_TARGET_PERCENT = 0.90
    MIN_ALLOCATION_THRESHOLD = 0.01
    N_MULTISTART = 5
    USE_BROKER_CONSTRAINTS = True
    BUDGET_BROKERS = {
        'Trading212': 733.70,
        'BoursDirect': 0,
        'BoursDirect2': 24472.0
    }
    VINE_TRUNC_HIGH = 20.0
    VINE_FAMILY = 'auto'
    DEDUP_FUZZY_THRESHOLD = 0.80
    FORCED_BUY_TICKERS = []

    @classmethod
    def load_params(cls):
        if os.path.exists(cls.PARAMS_FILE):
            try:
                with open(cls.PARAMS_FILE, 'r', encoding='utf-8') as f:
                    params = json.load(f)
                    for k, v in params.items():
                        setattr(cls, k, v)
                cls.OUTPUT_DIR = Path(cls.FOLDER_PATH)
                print(f"  -> Paramètres chargés depuis {cls.PARAMS_FILE}")
            except Exception as e:
                print(f"  ! Erreur chargement {cls.PARAMS_FILE}: {e}")


# ==================== RATE LIMITER ====================
class RateLimiter:
    def __init__(self, max_requests_per_hour, requests_per_ticker):
        self.max_requests_per_hour = max_requests_per_hour
        self.requests_per_ticker = requests_per_ticker
        self.request_timestamps = []
        self.lock = threading.Lock()
        # Calcul du délai théorique pour une répartition uniforme sur 1 heure (3600s)
        # Ex: 3600 / (2000 / 4) = 7.2 secondes
        self.min_interval = 3600.0 / (max_requests_per_hour / requests_per_ticker)
        self.last_ticker_time = 0

    def wait_for_slot(self):
        with self.lock:
            # 1. Respect du délai "Steady Pace" (Lissage sur la durée)
            now = time.time()
            elapsed = now - self.last_ticker_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)

            # 2. Protection contre le dépassement strict de la limite horaire (Burst protection)
            while True:
                now = time.time()
                cutoff = now - 3600.0
                self.request_timestamps = [t for t in self.request_timestamps if t > cutoff]

                if len(self.request_timestamps) + self.requests_per_ticker <= self.max_requests_per_hour:
                    for _ in range(self.requests_per_ticker):
                        self.request_timestamps.append(now)
                    self.last_ticker_time = now
                    return

                # Attendre que le plus vieux jeton expire
                sleep_time = (self.request_timestamps[0] + 3600.0) - now + 0.1
                time.sleep(max(sleep_time, 1.0))


# ==================== CACHE MANAGER ====================
class CacheManager:
    def __init__(self):
        self.cache_file = Config.CACHE_FILE
        self.cache = self._load()
        self.lock = threading.Lock()

    def _load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save(self):
        with self.lock:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)

    def update(self, ticker, latest_year, score=None, metrics=None):
        with self.lock:
            self.cache[ticker] = {
                'last_update': datetime.now().isoformat(),
                'latest_year': latest_year,
                'score': score,
                'metrics': metrics,
                'status': 'success',
            }

    def _infer_country(self, symbol):
        """Tente de deviner le pays à partir du suffixe du ticker."""
        suffix_map = {
            '.PA': 'France', '.DE': 'Germany', '.F': 'Germany', '.VI': 'Austria',
            '.MC': 'Spain', '.MI': 'Italy', '.AS': 'Netherlands', '.L': 'United Kingdom',
            '.CO': 'Denmark', '.ST': 'Sweden', '.OL': 'Norway', '.HE': 'Finland',
            '.SW': 'Switzerland', '.LS': 'Portugal', '.BR': 'Belgium', '.HK': 'Hong Kong',
            '.SS': 'China', '.SZ': 'China', '.NS': 'India', '.BO': 'India',
            '.KS': 'South Korea', '.KQ': 'South Korea', '.T': 'Japan', '.TW': 'Taiwan',
            '.TWO': 'Taiwan', '.AX': 'Australia', '.MX': 'Mexico', '.SA': 'Brazil',
            '.JO': 'South Africa', '.JK': 'Indonesia', '.IS': 'Turkey', '.BA': 'Argentina',
            '.TO': 'Canada', '.WA': 'Poland', '.SN': 'Chile', '.LM': 'Peru', '.PR': 'Czech Republic',
            '.IL': 'Israel', '.BK': 'Thailand', '.KL': 'Malaysia', '.SG': 'Singapore'
        }
        for suffix, p in suffix_map.items():
            if symbol.upper().endswith(suffix):
                return p
        return 'United States' if '.' not in symbol else 'Inconnu'

    def get_cached_result(self, ticker):
        """Retourne le score et les metrics si l'analyse est récente ET les données financières aussi."""
        with self.lock:
            info = self.cache.get(ticker, {})
            if not info or 'last_update' not in info or info.get('status') != 'success':
                return None

            try:
                last_update = datetime.fromisoformat(info['last_update'])
                age_days = (datetime.now() - last_update).days

                # On vérifie aussi l'âge des données financières stockées
                cached_year = info.get('latest_year', 0)
                age_fin = Config.CURRENT_YEAR - cached_year

                # Si l'analyse a moins de 60 jours et données fraîches
                if age_days < 60 and age_fin <= Config.MAX_AGE_YEARS and info.get('metrics'):
                    score = info.get('score')
                    metrics = info.get('metrics')

                    # RÉPARATION : Si le pays est inconnu, on l'infère
                    if metrics.get('Pays') == 'Inconnu':
                        metrics['Pays'] = self._infer_country(ticker)
                        # On force le signal Achat à True pour les ETF
                        if metrics.get('Secteur') == 'ETF' or metrics.get('QuoteType') == 'ETF':
                            metrics['Achat'] = True

                    return (float(score) if score is not None else 0.0), metrics
            except:
                pass
            return None

    def get_status(self, ticker, file_path):
        with self.lock:
            info = self.cache.get(ticker, {})
            cached_year = info.get('latest_year', 0)

        latest_year = 0
        if cached_year > 0:
            latest_year = cached_year
        elif file_path.exists():
            try:
                # On lit tout l'index pour s'assurer de prendre la date la plus récente
                # (le fichier peut être trié par ordre croissant, donc la 1ère ligne serait la plus ancienne)
                idx = pd.read_excel(file_path, sheet_name="income", usecols=[0], index_col=0).index
                latest_year = pd.to_datetime(idx).year.max()
            except:
                return "download"

        if latest_year == 0: return "download"
        age = Config.CURRENT_YEAR - latest_year
        if age > Config.MAX_AGE_YEARS:
            return "too_old"
        elif age <= 1:
            return "local_ok"
        else:
            return "update"


# ==================== COPULA CLASSES (Full Implementation) ====================
class BivariateCopula:
    """
    Copule bivariée avec 5 familles disponibles + sélection automatique par AIC.
    """
    N_PARAMS = {'gaussian': 1, 't': 2, 'clayton': 1, 'gumbel': 1, 'frank': 1, 'bb7': 2}
    AUTO_FAMILIES = ['gaussian', 't', 'clayton', 'gumbel', 'frank', 'bb7']

    def __init__(self, family='auto'):
        self.family = family
        self.family_fit = None
        self.rho = 0.0
        self.df = 4.0
        self.theta = 1.0
        self.delta = 0.5
        self.aic = np.inf
        self.fitted = False

    @staticmethod
    def kendall_to_pearson(tau):
        return np.sin(np.pi / 2 * tau)

    @staticmethod
    def kendall_to_clayton(tau):
        return max(2 * max(tau, 1e-6) / (1 - max(tau, 1e-6)), 0.01)

    @staticmethod
    def kendall_to_gumbel(tau):
        return max(1 / (1 - max(tau, 1e-6)), 1.001)

    @staticmethod
    def _clip(u):
        return np.clip(u, 1e-10, 1 - 1e-10)

    def _log_density_gaussian(self, u, v, rho):
        u, v = self._clip(u), self._clip(v)
        x, y = stats.norm.ppf(u), stats.norm.ppf(v)
        r2 = rho ** 2
        return -0.5 * np.log(1 - r2) - (r2 * (x ** 2 + y ** 2) - 2 * rho * x * y) / (2 * (1 - r2))

    def _log_density_t(self, u, v, rho, df):
        from scipy.special import gammaln
        u, v = self._clip(u), self._clip(v)
        x, y = stats.t.ppf(u, df), stats.t.ppf(v, df)
        r2 = rho ** 2
        quad = (x ** 2 + y ** 2 - 2 * rho * x * y) / (df * (1 - r2))
        return (gammaln((df + 2) / 2) + gammaln(df / 2) - 2 * gammaln((df + 1) / 2)
                - 0.5 * np.log(1 - r2) - ((df + 2) / 2) * np.log(1 + quad)
                + ((df + 1) / 2) * np.log(1 + x ** 2 / df) + ((df + 1) / 2) * np.log(1 + y ** 2 / df))

    def _log_density_clayton(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        theta = max(theta, 1e-6)
        log_c = np.log(theta + 1) - (theta + 1) * (np.log(u) + np.log(v)) - (2 + 1 / theta) * np.log(
            u ** (-theta) + v ** (-theta) - 1)
        return np.where(np.isfinite(log_c), log_c, -1e10)

    def _log_density_gumbel(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        theta = max(theta, 1.001)
        lu, lv = -np.log(u), -np.log(v)
        S = lu ** theta + lv ** theta
        C = np.exp(-S ** (1 / theta))
        log_c = np.log(C) + (1 / theta - 2) * np.log(S) + (theta - 1) * (np.log(lu) + np.log(lv)) + np.log(
            S ** (1 / theta) + theta - 1) - np.log(u) - np.log(v)
        return np.where(np.isfinite(log_c), log_c, -1e10)

    def _log_density_frank(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        if abs(theta) < 1e-6: return np.zeros(len(u))
        et, etu, etv = np.exp(-theta), np.exp(-theta * u), np.exp(-theta * v)
        num = theta * (et - 1) * np.exp(-theta * (u + v))
        den = ((et - 1) + (etu - 1) * (etv - 1)) ** 2
        return np.log(np.abs(num)) - np.log(np.maximum(np.abs(den), 1e-300))

    def _log_density_bb7(self, u, v, theta, delta):
        u, v = self._clip(u), self._clip(v)
        theta, delta = max(theta, 1.001), max(delta, 0.01)
        eps = 1e-6

        def _C(u_, v_):
            a, b = (1 - (1 - u_) ** theta) ** (-delta), (1 - (1 - v_) ** theta) ** (-delta)
            return 1 - (1 - np.maximum(a + b - 1, 1e-300) ** (-1 / delta)) ** (1 / theta)

        density = (_C(u + eps, v + eps) - _C(u + eps, v - eps) - _C(u - eps, v + eps) + _C(u - eps, v - eps)) / (
                4 * eps * eps)
        return np.log(np.maximum(density, 1e-300))

    def _h_gaussian(self, u, v, rho):
        u, v = self._clip(u), self._clip(v)
        x, y = stats.norm.ppf(u), stats.norm.ppf(v)
        return stats.norm.cdf((x - rho * y) / np.sqrt(1 - rho ** 2))

    def _h_t(self, u, v, rho, df):
        u, v = self._clip(u), self._clip(v)
        x, y = stats.t.ppf(u, df), stats.t.ppf(v, df)
        num = x - rho * y
        denom = np.sqrt((df + y ** 2) * (1 - rho ** 2) / (df + 1))
        return stats.t.cdf(num / denom, df + 1)

    def _h_clayton(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        return np.clip(
            v ** (-(theta + 1)) * np.maximum(u ** (-theta) + v ** (-theta) - 1, 1e-300) ** (-(1 + 1 / theta)), 1e-10,
            1 - 1e-10)

    def _h_gumbel(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        lu, lv = -np.log(u), -np.log(v)
        S = lu ** theta + lv ** theta
        C = np.exp(-S ** (1 / theta))
        return np.clip(C / v * lv ** (theta - 1) * S ** (1 / theta - 1), 1e-10, 1 - 1e-10)

    def _h_frank(self, u, v, theta):
        u, v = self._clip(u), self._clip(v)
        if abs(theta) < 1e-6: return u.copy()
        et, etu, etv = np.exp(-theta), np.exp(-theta * u), np.exp(-theta * v)
        return np.clip(((et - 1) * etu) / np.maximum((et - 1) + (etu - 1) * (etv - 1), 1e-300), 1e-10, 1 - 1e-10)

    def _h_bb7(self, u, v, theta, delta):
        u, v = self._clip(u), self._clip(v)
        eps = 1e-5

        def _C(u_, v_):
            a, b = (1 - (1 - u_) ** theta) ** (-delta), (1 - (1 - v_) ** theta) ** (-delta)
            return 1 - (1 - np.maximum(a + b - 1, 1e-300) ** (-1 / delta)) ** (1 / theta)

        return np.clip((_C(u, v + eps) - _C(u, v - eps)) / (2 * eps), 1e-10, 1 - 1e-10)

    def _fit_single(self, family, u, v, tau):
        cop = BivariateCopula(family=family)
        if family == 'gaussian':
            res = minimize(lambda p: -np.nansum(cop._log_density_gaussian(u, v, np.clip(p[0], -0.999, 0.999))),
                           [self.kendall_to_pearson(tau)], bounds=[(-0.999, 0.999)])
            cop.rho, ll = float(res.x[0]), -res.fun
        elif family == 't':
            res = minimize(
                lambda p: -np.nansum(cop._log_density_t(u, v, np.clip(p[0], -0.999, 0.999), max(p[1], 2.01))),
                [self.kendall_to_pearson(tau), 5.0], bounds=[(-0.999, 0.999), (2.01, 50.0)])
            cop.rho, cop.df, ll = float(res.x[0]), float(res.x[1]), -res.fun
        elif family == 'clayton':
            if tau <= 0:
                cop.theta, ll = 0.01, np.nansum(cop._log_density_clayton(u, v, 0.01))
            else:
                res = minimize(lambda p: -np.nansum(cop._log_density_clayton(u, v, max(p[0], 0.01))),
                               [self.kendall_to_clayton(tau)], bounds=[(0.01, 20.0)])
                cop.theta, ll = float(res.x[0]), -res.fun
        elif family == 'gumbel':
            if tau <= 0:
                cop.theta, ll = 1.001, np.nansum(cop._log_density_gumbel(u, v, 1.001))
            else:
                res = minimize(lambda p: -np.nansum(cop._log_density_gumbel(u, v, max(p[0], 1.001))),
                               [self.kendall_to_gumbel(tau)], bounds=[(1.001, 20.0)])
                cop.theta, ll = float(res.x[0]), -res.fun
        elif family == 'frank':
            res = minimize(lambda p: -np.nansum(cop._log_density_frank(u, v, p[0])), [1.0 if tau >= 0 else -1.0],
                           bounds=[(-30.0, 30.0)])
            cop.theta, ll = float(res.x[0]), -res.fun
        elif family == 'bb7':
            if tau <= 0:
                cop.theta, cop.delta, ll = 1.001, 0.5, np.nansum(cop._log_density_bb7(u, v, 1.001, 0.5))
            else:
                res = minimize(lambda p: -np.nansum(cop._log_density_bb7(u, v, max(p[0], 1.001), max(p[1], 0.01))),
                               [max(self.kendall_to_gumbel(tau), 1.001), max(self.kendall_to_clayton(tau), 0.01)],
                               bounds=[(1.001, 10.0), (0.01, 10.0)])
                cop.theta, cop.delta, ll = float(res.x[0]), float(res.x[1]), -res.fun
        cop.family_fit, cop.aic, cop.fitted = family, 2 * self.N_PARAMS[family] - 2 * ll, True
        return cop, cop.aic

    def fit(self, u, v):
        tau, _ = kendalltau(u, v)
        if np.isnan(tau): tau = 0.0
        families = self.AUTO_FAMILIES if self.family == 'auto' else [self.family]
        best_cop, best_aic = None, np.inf
        for fam in families:
            try:
                cop, aic = self._fit_single(fam, u, v, tau)
                if aic < best_aic: best_aic, best_cop = aic, cop
            except:
                continue
        if best_cop is None: best_cop, _ = self._fit_single('gaussian', u, v, tau)
        self.__dict__.update(best_cop.__dict__)
        return self

    def h_function(self, u, v):
        fam = self.family_fit or self.family
        if fam == 'gaussian': return self._h_gaussian(u, v, self.rho)
        if fam == 't': return self._h_t(u, v, self.rho, self.df)
        if fam == 'clayton': return self._h_clayton(u, v, self.theta)
        if fam == 'gumbel': return self._h_gumbel(u, v, self.theta)
        if fam == 'frank': return self._h_frank(u, v, self.theta)
        if fam == 'bb7': return self._h_bb7(u, v, self.theta, self.delta)
        return self._h_gaussian(u, v, self.rho)


class DVineCopula:
    def __init__(self, family='t', max_trees=None, trunc_high=20.0):
        self.family, self.max_trees, self.trunc_high = family, max_trees, trunc_high
        self.copulas, self.fitted, self.n_trees_fitted = {}, False, 0

    def _greedy_order(self, U):
        n = U.shape[1]
        tau_mat = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                tau, _ = kendalltau(U[:, i], U[:, j])
                tau_mat[i, j] = tau_mat[j, i] = abs(tau) if not np.isnan(tau) else 0.0

        # On remplace les NaN éventuels par 0 avant argmax
        tau_mat_safe = np.nan_to_num(tau_mat, nan=0.0)
        i_max, j_max = np.unravel_index(np.argmax(np.triu(tau_mat_safe, 1)), tau_mat.shape)
        order = [int(i_max), int(j_max)]
        remaining = set(range(n)) - set(order)
        while remaining:
            left, right = order[0], order[-1]
            best_tau, best_node, best_side = -1, None, None
            for r in remaining:
                val_left = tau_mat[left, r] if not np.isnan(tau_mat[left, r]) else 0.0
                val_right = tau_mat[right, r] if not np.isnan(tau_mat[right, r]) else 0.0
                if val_left > best_tau: best_tau, best_node, best_side = val_left, r, 'left'
                if val_right > best_tau: best_tau, best_node, best_side = val_right, r, 'right'

            if best_node is None:
                best_node = next(iter(remaining))
                best_side = 'right'

            if best_side == 'left':
                order.insert(0, best_node)
            else:
                order.append(best_node)
            remaining.remove(best_node)
        return order

    def fit(self, U, verbose=True):
        n_obs, n = U.shape
        self.n = n
        max_trees = min(self.max_trees or (n - 1), n - 1)
        self.order = self._greedy_order(U)
        U_ordered = U[:, self.order]
        V = {i: U_ordered[:, i].copy() for i in range(n)}
        dep_history = []
        for tree in range(1, max_trees + 1):
            V_next = {}
            for edge in range(n - tree):
                cop = BivariateCopula(family=self.family).fit(V[edge], V[edge + tree])
                self.copulas[(tree, edge)] = cop
                if tree < max_trees:
                    V_next[edge] = cop.h_function(V[edge], V[edge + tree])
                    V_next[edge + tree] = cop.h_function(V[edge + tree], V[edge])
            V = V_next
            pct_extreme = np.mean(
                (np.concatenate(list(V.values())) < 0.01) | (np.concatenate(list(V.values())) > 0.99)) * 100 if V else 0
            dep_history.append(pct_extreme)
            if tree >= 3 and all(d > self.trunc_high for d in dep_history[-3:]): break
        self.n_trees_fitted, self.fitted = tree, True
        return self

    def simulate(self, n_obs=100000):
        """
        Simule des scénarios à partir de la corrélation impliquée et des marginales t.
        """
        rho_mat = self.implied_correlation()
        if not is_pos_def(rho_mat): rho_mat = nearest_pos_def(rho_mat)

        # Simulation d'une distribution normale multivariée pour la copule gaussienne/t
        z = np.random.multivariate_normal(np.zeros(self.n), rho_mat, n_obs)
        U = stats.norm.cdf(z)  # Probabilités uniformes jointes
        return U

    def implied_correlation(self):
        rho_mat = np.eye(self.n)
        corrections = []
        deps = []
        for edge in range(self.n - 1):
            cop = self.copulas.get((1, edge))
            if not cop: continue
            fam = cop.family_fit or cop.family

            # Calcul de rho et de la correction
            if fam in ('gaussian', 't'):
                rho = cop.rho
                if fam == 't':
                    corrections.append(np.sqrt((cop.df + 1) / cop.df))
                else:
                    corrections.append(1.0)
            elif fam == 'clayton':
                tau = cop.theta / (cop.theta + 2)
                rho = np.sin(np.pi / 2 * tau)
                corrections.append(np.sqrt(5 / 4))
            elif fam == 'gumbel':
                tau = 1 - 1 / cop.theta
                rho = np.sin(np.pi / 2 * tau)
                corrections.append(np.sqrt(9 / 8))
            elif fam == 'frank':
                rho = np.sin(np.pi / 2 * np.clip(cop.theta / 9, -0.99, 0.99))
                corrections.append(1.0)
            elif fam == 'bb7':
                tau = 1 - 2 / (cop.delta * (cop.theta + 2))
                rho = np.sin(np.pi / 2 * np.clip(tau, -0.99, 0.99))
                w = cop.theta / (cop.theta + cop.delta)
                corrections.append(w * np.sqrt(9 / 8) + (1 - w) * np.sqrt(5 / 4))
            else:
                rho = 0.0
                corrections.append(1.0)

            deps.append(abs(rho))
            i, j = self.order[edge], self.order[edge + 1]
            rho_mat[i, j] = rho_mat[j, i] = rho

        self.correction = float(np.average(corrections, weights=np.array(deps) + 1e-10)) if corrections else 1.0
        return rho_mat


def nearest_pos_def(A):
    B = (A + A.T) / 2
    U, s, Vt = np.linalg.svd(B)
    A_pd = U @ np.diag(np.maximum(s, 1e-8)) @ Vt
    A_pd = (A_pd + A_pd.T) / 2
    I = np.eye(A.shape[0])
    k = 1
    while True:
        try:
            np.linalg.cholesky(A_pd)
            break
        except np.linalg.LinAlgError:
            A_pd += I * (-np.min(np.real(np.linalg.eigvals(A_pd))) * k ** 2 + np.spacing(np.linalg.norm(A)))
            k += 1
    return A_pd


def is_pos_def(B):
    try:
        np.linalg.cholesky(B)
        return True
    except np.linalg.LinAlgError:
        return False


# ==================== MAIN PIPELINE ====================
class MasterInvest:
    def __init__(self):
        Config.load_params()
        self.setup_dirs()
        self.cache = CacheManager()
        self.rate_limiter = RateLimiter(Config.MAX_REQUESTS_PER_HOUR, Config.REQUESTS_PER_TICKER)
        self.results_lock = threading.Lock()

    def setup_dirs(self):
        if not os.path.exists(Config.DATA_DIR): os.makedirs(Config.DATA_DIR)
        if not os.path.exists(Config.FOLDER_PATH): os.makedirs(Config.FOLDER_PATH)

    def fetch_data(self, symbol):
        self.rate_limiter.wait_for_slot()
        try:
            t = yf.Ticker(symbol)
            data = {
                "income": t.financials.transpose(),
                "balance": t.balance_sheet.transpose(),
                "cashflow": t.cashflow.transpose(),
                "info": t.info
            }
            return data
        except:
            return None

    def _extract_metrics(self, symbol, info):
        """Extrait les métriques de base du dictionnaire info de yfinance."""
        if not info: info = {}

        quote_type = info.get('quoteType', '').upper()
        secteur = info.get('sector', 'Inconnu')
        if quote_type == 'ETF' or 'ETF' in info.get('longName', '').upper() or 'ETF' in info.get('shortName',
                                                                                                 '').upper():
            secteur = 'ETF'

        pays = info.get('country', 'Inconnu')
        if pays == 'Inconnu':
            pays = self.cache._infer_country(symbol)

        return {
            'Nom': info.get('longName', info.get('shortName', symbol)),
            'Pays': pays,
            'Prix': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'EPS': info.get('trailingEps', 0),
            'PER': info.get('trailingPE', 0),
            'Volume': info.get('volume', info.get('regularMarketVolume', 0)),
            'Secteur': secteur,
            'QuoteType': quote_type
        }

    @staticmethod
    def _filter_incomplete_rows(df):
        num_cols = df.select_dtypes(include=[np.number]).columns
        if len(num_cols) == 0:
            return df
        # On garde les dates mais on filtre les lignes trop vides
        filtered = df[df[num_cols].isnull().mean(axis=1) < 0.5]
        # Formater l'index en string (Date) pour Excel s'il s'agit de Datetime
        try:
            if isinstance(filtered.index, pd.DatetimeIndex):
                filtered.index = filtered.index.strftime('%Y-%m-%d')
        except:
            pass
        return filtered

    @staticmethod
    def _exponential_weights(n):
        if n <= 0: return []
        if n == 1: return [1.0]
        raw = [np.exp(-0.1 * i) for i in range(n)]
        total = sum(raw)
        return [w / total for w in raw]

    def analyze_financials(self, symbol, data):
        """Analyse financière détaillée inspirée de Warren Buffet."""
        try:
            info = data.get("info", {})
            metrics = self._extract_metrics(symbol, info)

            # Cas spécial pour les tickers forcés (ETFs, etc.) ou détectés comme ETFs
            is_etf = metrics.get('Secteur') == 'ETF' or metrics.get('QuoteType') == 'ETF'

            if symbol.upper() in [t.upper() for t in Config.FORCED_BUY_TICKERS] or is_etf:
                metrics['Achat'] = True
                if is_etf:
                    metrics['Secteur'] = 'ETF'
                else:
                    metrics['Secteur'] = 'ETF / Forced'
                # On donne 100 à tous les ETF (pas de MOAT à calculer)
                return 100.0, metrics, pd.DataFrame(), pd.DataFrame()

            income = data.get("income")
            balance = data.get("balance")
            cashflow = data.get("cashflow")

            if income is None or income.empty or balance is None or balance.empty:
                return 0, self._extract_metrics(symbol, info), pd.DataFrame(), pd.DataFrame()

            # Nettoyage et alignement temporel
            income = self._filter_incomplete_rows(income.sort_index(ascending=True))
            balance = self._filter_incomplete_rows(balance.sort_index(ascending=True))
            cashflow = self._filter_incomplete_rows(cashflow.sort_index(ascending=True))

            common_dates = income.index.intersection(balance.index).intersection(cashflow.index)
            if common_dates.empty:
                return 0, self._extract_metrics(symbol, info), pd.DataFrame(), pd.DataFrame()

            income = income.loc[common_dates]
            balance = balance.loc[common_dates]
            cashflow = cashflow.loc[common_dates]

            n = len(income)
            weights = self._exponential_weights(n)

            def safe(func, default=0):
                try:
                    # On force la conversion en numérique AVANT l'opération si possible
                    # en essayant d'exécuter la fonction
                    r = func()
                    if isinstance(r, (pd.Series, pd.DataFrame)):
                        r = pd.to_numeric(r, errors='coerce')
                    return r.fillna(default) if hasattr(r, 'fillna') else (r if r is not None else default)
                except:
                    return pd.Series([default] * n, index=income.index)

            # Pré-conversion des colonnes financières en numérique
            for df_in in [income, balance, cashflow]:
                for col in df_in.columns:
                    df_in[col] = pd.to_numeric(df_in[col], errors='coerce').fillna(0)

            analyse = pd.DataFrame(index=income.index)
            analyse["Gross Profit Margin"] = safe(lambda: income["Gross Profit"] / income["Total Revenue"])
            analyse["SGA"] = safe(lambda: income["Selling General And Administration"] / income["Gross Profit"], 1)
            analyse["Research & Development"] = safe(
                lambda: income["Research And Development"] / income["Gross Profit"], 1)
            analyse["Depreciation"] = safe(lambda: income["Reconciled Depreciation"] / income["Gross Profit"], 1)
            analyse["Interest Expense"] = safe(lambda: income["Interest Expense"] / income["Operating Income"], 1)
            analyse["Pretax Income"] = safe(lambda: income["Pretax Income"], 1)
            analyse["Net Income"] = safe(lambda: income["Net Income"], 1)
            analyse["Net Income / Total Revenue"] = safe(lambda: income["Net Income"] / income["Total Revenue"], 1)
            # Correction: Ordinary Shares Number might not be in balance columns
            shares_col = "Ordinary Shares Number" if "Ordinary Shares Number" in balance.columns else balance.columns[0]
            analyse["EPS"] = safe(lambda: income["Net Income"] / balance[shares_col], 1)

            cash = pd.Series([0] * n, index=income.index)
            for col in ["Cash Cash Equivalents And Short Term Investments", "Inventory", "Accounts Receivable"]:
                try:
                    if col in balance.columns:
                        cash += balance[col].fillna(0)
                except:
                    pass
            analyse["Cash Cash Equivalents And Short Term Investments"] = cash

            analyse["Debt Ratio"] = safe(
                lambda: balance["Current Debt"] / balance["Long Term Debt And Capital Lease Obligation"], 1)
            analyse["Liab Ratio"] = safe(lambda: balance["Total Assets"] / balance["Current Liabilities"])
            analyse["Long term debt Ratio"] = safe(lambda: balance["Current Debt"] / balance["Pretax Income"])
            analyse["Debt to Shareholders Equity Ratio"] = safe(
                lambda: balance["Total Liabilities Net Minority Interest"] / balance["Common Stock Equity"])
            analyse["Retained Earnings"] = safe(lambda: balance["Retained Earnings"])
            analyse["Return on Shareholders' Equity"] = safe(
                lambda: income["Net Income"] / balance["Stockholders Equity"])
            analyse["Capital Stock Var"] = safe(
                lambda: cashflow["Issuance Of Capital Stock"] + cashflow["Repurchase Of Capital Stock"])
            analyse["Capex Ratio"] = safe(lambda: cashflow["Capital Expenditure"] / income["Net Income"])
            analyse["Repurchase Of Capital Stock"] = safe(lambda: -cashflow["Repurchase Of Capital Stock"])

            # --- CALCUL DU ROIC ---
            # Formule: EBIT / (Working Capital + Fixed Assets) ou EBIT / (Total Debt + Equity - Cash)
            def compute_roic():
                ebit = income["Operating Income"]
                debt = balance["Total Debt"] if "Total Debt" in balance.columns else (
                        balance.get("Current Debt", 0) + balance.get("Long Term Debt And Capital Lease Obligation", 0)
                )
                equity = balance["Common Stock Equity"]
                cash_assets = balance.get("Cash Cash Equivalents And Short Term Investments", 0)
                invested_capital = debt + equity - cash_assets
                return ebit / invested_capital

            analyse["ROIC"] = safe(compute_roic, 0)

            score_df = pd.DataFrame(index=income.index)
            score_df["Gross Profit Margin"] = (analyse["Gross Profit Margin"] / 0.6).clip(0, 1)
            score_df["SGA"] = ((1 - analyse["SGA"]) / 0.8).clip(0, 1)
            score_df["Research & Development"] = ((1 - analyse["Research & Development"]) / 0.3).clip(0, 1)
            score_df["Depreciation"] = ((1 - analyse["Depreciation"]) / 0.15).clip(0, 1)
            score_df["Interest Expense"] = ((1 - analyse["Interest Expense"]) / 0.15).clip(0, 1)

            score_df["Pretax Income"] = (analyse["Pretax Income"].diff() > 0).astype(int)
            score_df.iloc[0, score_df.columns.get_loc("Pretax Income")] = 1
            score_df["Net Income"] = (analyse["Net Income"].diff() > 0).astype(int)
            score_df.iloc[0, score_df.columns.get_loc("Net Income")] = 1
            score_df["Net Income1"] = (analyse["Net Income"] > 0).astype(int)
            score_df["Net Income / Total Revenue"] = (analyse["Net Income / Total Revenue"] / 0.2).clip(0, 1)
            score_df["EPS"] = (analyse["EPS"].diff() > 0).astype(int)
            score_df.iloc[0, score_df.columns.get_loc("EPS")] = 1
            score_df["Cash Cash Equivalents And Short Term Investments"] = (
                    analyse["Cash Cash Equivalents And Short Term Investments"].diff() > 0
            ).astype(int)
            score_df.iloc[0, score_df.columns.get_loc("Cash Cash Equivalents And Short Term Investments")] = 1

            score_df["Debt Ratio"] = ((1 - analyse["Debt Ratio"]) / 0.6).clip(0, 1)
            score_df["Liab Ratio"] = analyse["Liab Ratio"].clip(0, 1)
            score_df["Long term debt Ratio"] = ((1 - analyse["Long term debt Ratio"]) / 0.25).clip(0, 1)
            score_df["Debt to Shareholders Equity Ratio"] = (
                    (1 - analyse["Debt to Shareholders Equity Ratio"]) / 0.8).clip(0, 1)
            score_df["Retained Earnings"] = (analyse["Retained Earnings"].diff() / 0.05).clip(0, 1)
            score_df.iloc[0, score_df.columns.get_loc("Retained Earnings")] = 1
            score_df["Capital Stock Var"] = (analyse["Capital Stock Var"] < 0).astype(int)
            score_df["Return on Shareholders' Equity"] = (analyse["Return on Shareholders' Equity"] / 0.2).clip(0, 1)
            score_df["ROIC"] = (analyse["ROIC"] / 0.1).clip(0, 1)
            score_df["Capex Ratio"] = ((1 - analyse["Capex Ratio"]) / 0.25).clip(0, 1)
            score_df["Repurchase Of Capital Stock"] = (analyse["Repurchase Of Capital Stock"] > 0).astype(int)

            score_df = score_df.fillna(0)
            row_scores = score_df.mean(axis=1)
            total_score = sum(row_scores.iloc[i] * weights[i] for i in range(n)) * 100

            # --- Calcul CAGR pour PEG (Filtre Ticker logic) ---
            growth_rev = np.nan
            growth_eps = np.nan
            try:
                # 1. Croissance Chiffre d'Affaires
                rev_row = None
                for label in ('Total Revenue', 'Revenue', 'TotalRevenue'):
                    if label in income.columns:
                        rev_row = income[label].dropna()
                        break
                if rev_row is not None and len(rev_row) >= 2:
                    rev_values = rev_row.values.astype(float)
                    n_years = len(rev_values) - 1
                    r0, rn = rev_values[0], rev_values[-1]
                    if r0 > 0 and rn > 0 and n_years > 0:
                        growth_rev = (rn / r0) ** (1.0 / n_years) - 1.0

                # 2. Croissance EPS
                eps_row = analyse["EPS"].dropna()
                if len(eps_row) >= 2:
                    eps_values = eps_row.values.astype(float)
                    # On évite les EPS négatifs pour le CAGR
                    if eps_values[0] > 0 and eps_values[-1] > 0:
                        growth_eps = (eps_values[-1] / eps_values[0]) ** (1.0 / (len(eps_values) - 1)) - 1.0
            except:
                pass

            # On prend la meilleure croissance disponible pour le PEG
            growth = max([g for g in [growth_rev, growth_eps] if not np.isnan(g)] or [np.nan])

            metrics = self._extract_metrics(symbol, info)
            metrics['CAGR'] = growth
            metrics['CAGR_Rev'] = growth_rev
            metrics['CAGR_EPS'] = growth_eps

            # Calcul du signal d'achat
            secteur = metrics.get('Secteur', 'Inconnu')
            pays = metrics.get('Pays', 'Inconnu')
            prix = metrics.get('Prix', 0)
            eps = metrics.get('EPS', 0)
            per = metrics.get('PER', 0)

            achat = False
            if 'ETF' in str(secteur).upper():
                achat = True
                metrics['PEG'] = np.nan
            else:
                taux = Config.TAUX_OBLIGATAIRES.get(pays, Config.TAUX_DEFAUT)
                seuil_prix = eps / (0.02 + taux) if (eps and eps > 0) else 0
                peg = per / (growth * 100) if (growth and growth > 0) else np.nan

                if pays != 'Inconnu' and per > 0 and per < Config.PER_MAX and \
                        (np.isnan(peg) or peg < Config.PEG_MAX) and prix < seuil_prix:
                    achat = True
                metrics['PEG'] = peg

            metrics['Achat'] = achat

            # Enrichir les données pour la sauvegarde
            data["score_df"] = score_df
            data["analyse"] = analyse

            self.save_data(symbol, data)

            # S'assurer que le ticker est dans l'index pour la suite
            score_df.index = [
                data.get('formatted_date', 'Date Inconnue')] if 'formatted_date' in data else score_df.index

            return total_score, metrics, analyse, score_df
        except Exception as e:
            print(f"  ! Erreur analyse {symbol}: {e}")
            return 0, self._extract_metrics(symbol, data.get("info", {})), pd.DataFrame(), pd.DataFrame()

    # ── Dictionnaire de RÉDUCTION vers formes canoniques courtes ──────────────
    ABBREV_REDUCTIONS = {
        ' aeroportuario ': ' aerop ', ' international ': ' intl ', ' national ': ' natl ',
        ' american ': ' amer ', ' european ': ' euro ', ' technology ': ' tech ',
        ' technologies ': ' tech ', ' systems ': ' sys ', ' semiconductor ': ' semi ',
        ' information ': ' info ', ' infrastructure ': ' infra ', ' engineering ': ' eng ',
        ' pharmaceutical ': ' pharma ', ' pharmaceuticals ': ' pharma ', ' healthcare ': ' hlth ',
        ' biologics ': ' biol ', ' medical ': ' med ', ' hospital ': ' hosp ',
        ' laboratories ': ' lab ', ' laboratory ': ' lab ', ' financial ': ' fin ',
        ' insurance ': ' ins ', ' investment ': ' invest ', ' investments ': ' invest ',
        ' capital ': ' cap ', ' manufacturing ': ' mfg ', ' management ': ' mgmt ',
        ' corporation ': ' corp ', ' associates ': ' assoc ', ' partners ': ' partner ',
        ' acquisition ': ' acq ', ' holdings ': ' hldg ', ' properties ': ' prop ',
        ' property ': ' prop ', ' construction ': ' constr ', ' distribution ': ' dist ',
        ' distillery ': ' distl ', ' industries ': ' ind ', ' industrial ': ' indl ',
        ' electronic ': ' elec ', ' electronics ': ' elec ', ' equipment ': ' equip ',
        ' environmental ': ' envir ', ' materials ': ' matl ', ' material ': ' matl ',
        ' chemical ': ' chem ', ' chemicals ': ' chem ', ' energy ': ' engy ',
        ' aerospace ': ' aero ', ' defense ': ' def ', ' communications ': ' comm ',
        ' telecommunication ': ' telecom ', ' telecommunications ': ' telecom ', ' entertainment ': ' entmt ',
        ' development ': ' dev ', ' resources ': ' res ', ' research ': ' rsch ',
        ' sciences ': ' sci ', ' science ': ' sci ', ' transportation ': ' transp ',
        ' logistics ': ' logis ', ' automotive ': ' auto ', ' motors ': ' mtr ',
        ' motor ': ' mtr ', ' services ': ' svc ', ' service ': ' svc ',
        ' markets ': ' mkt ', ' market ': ' mkt ', ' electric ': ' elec ',
        ' university ': ' univ ', ' education ': ' educ ', ' agricultural ': ' agric ',
        ' wholesale ': ' whsl ', ' cosmetics ': ' cosmet ', ' beverages ': ' bev ',
        ' beverage ': ' bev ', ' laojiao ': ' lao jiao ', ' kla tencor ': ' klacorp ',
        ' tencor ': ' klacorp ', ' kla ': ' klacorp ',
    }

    @staticmethod
    def _normalize_shortname(sn: str) -> str:
        if not sn: return ''
        s = sn.strip().lower()
        s = re.split(r'\s+-\s+', s)[0]
        s = s.replace('-', ' ').replace('.', ' ')
        s = re.sub(r'[\,\(\)\[\]:]+$', '', s).strip()
        s = s.replace('&', ' ').replace('+', ' ')
        s = re.sub(r'\s+', ' ', s).strip()
        s = ' ' + s + ' '
        for long_form, short_form in MasterInvest.ABBREV_REDUCTIONS.items():
            s = s.replace(long_form, short_form)
        s = s.strip()
        NOISE = r'\b(incorporated|corporation|limited|holdings?|inc|corp|ltd|plc|nv|ag|se|sa|ab|llc|lp|adr|gdr|drn|spon|unsp|cdi|cedear|ord|del|de|la|the|grp|group|sab|cvr|cv)\b'
        s = re.sub(NOISE, '', s, flags=re.IGNORECASE)
        s = re.sub(r'\b[a-z]{1,2}\b', '', s)
        s = re.sub(r'\b\d+\b', '', s)
        s = re.sub(r'[^\w\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _fuzzy_token_set_ratio(a: str, b: str) -> float:
        def _lev_ratio(s1: str, s2: str) -> float:
            if not s1 and not s2: return 1.0
            if not s1 or not s2: return 0.0
            prev = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1, 1):
                curr = [i] + [0] * len(s2)
                for j, c2 in enumerate(s2, 1):
                    if c1 == c2:
                        curr[j] = prev[j - 1]
                    else:
                        curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
                prev = curr
            return 1.0 - prev[len(s2)] / max(len(s1), len(s2))

        if not a or not b: return 0.0
        tokens_a, tokens_b = set(a.split()), set(b.split())
        if not tokens_a or not tokens_b: return 0.0
        if len(tokens_a) == 1 and len(tokens_b) == 1:
            return 1.0 if (a == b and len(a) >= 4) else 0.0
        inter = sorted(tokens_a & tokens_b)
        inter_str = ' '.join(inter)
        str_a = (inter_str + ' ' + ' '.join(sorted(tokens_a - tokens_b))).strip()
        str_b = (inter_str + ' ' + ' '.join(sorted(tokens_b - tokens_a))).strip()
        token_set_score = max(_lev_ratio(inter_str, str_a), _lev_ratio(inter_str, str_b), _lev_ratio(str_a, str_b))
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        nospace_score = _lev_ratio(a.replace(' ', ''), b.replace(' ', ''))
        if nospace_score >= 0.90: return 0.40 * token_set_score + 0.10 * jaccard + 0.50 * nospace_score
        return 0.65 * token_set_score + 0.25 * jaccard + 0.10 * nospace_score

    def deduplicate_tickers(self, returns, df):
        print(f"\n[Dédoublonnage] Analyse des cross-listings...")
        cols = list(returns.columns)
        ticker_col = 'Ticker Yahoo Finance'

        # On regroupe par nom d'entreprise normalisé
        # On va garder le ticker qui a le plus gros volume parmi les doublons
        company_groups = {}  # Normalized Name -> List of (Ticker, Volume)

        for t in cols:
            row = df[df[ticker_col] == t].iloc[0]
            raw_name = str(row['Nom'])
            norm_name = self._normalize_shortname(raw_name)
            volume = float(row.get('Volume', 0))

            # Exclusion du matching flou pour les ETF ou les actifs forcés
            is_forced = t.upper() in [ft.upper() for ft in Config.FORCED_BUY_TICKERS]
            if is_forced or 'ETF' in str(row['Secteur']).upper() or 'ETF' in raw_name.upper():
                company_groups[f"ETF_EXACT_{t}"] = [(t, volume)]
                continue

            # Recherche d'un groupe existant via fuzzy matching
            found_key = None
            for existing_name in company_groups:
                if self._fuzzy_token_set_ratio(norm_name, existing_name) >= Config.DEDUP_FUZZY_THRESHOLD:
                    found_key = existing_name
                    break

            if found_key:
                company_groups[found_key].append((t, volume))
            else:
                company_groups[norm_name] = [(t, volume)]

        tickers_kept = []
        for name, group in company_groups.items():
            # On trie par volume décroissant et on prend le premier
            best_ticker = sorted(group, key=lambda x: x[1], reverse=True)[0][0]
            tickers_kept.append(best_ticker)

        if len(tickers_kept) < len(cols):
            print(f"  -> {len(cols) - len(tickers_kept)} doublons (variantes d'entreprises) supprimés.")

        return returns[tickers_kept]

    def portfolio_performance(self, weights, returns, cov_mat):
        daily = (returns * weights).sum(axis=1)
        cum = (1 + daily).prod()
        n_years = len(returns) / 252
        ret = cum ** (1 / n_years) - 1
        vol = np.sqrt(np.dot(weights.T, np.dot(cov_mat, weights)))
        sharpe = (ret - Config.TAUX_DEFAUT) / vol if vol > 0 else 0
        return ret, vol, sharpe

    def vine_copula_risk(self, weights, cov_mat, correction):
        vol = np.sqrt(np.dot(weights.T, np.dot(cov_mat, weights)))
        return vol * correction

    def _clean_name(self, s):
        """Nettoie un nom pour comparaison (majuscules, sans espaces ni caractères spéciaux)."""
        return "".join(filter(str.isalnum, str(s).upper()))

    def _get_broker_col(self, b_name, columns):
        """Recherche une colonne broker avec une correspondance intelligente."""

        def _full_clean(v):
            return self._clean_name(v).replace("TRADING", "TRADDING").replace("BOURSE", "BOURS")

        clean_b = _full_clean(b_name)

        # 1. Correspondance exacte
        for c in columns:
            if clean_b == _full_clean(c):
                return c

        # 2. Correspondance avec chiffres
        import re
        b_num_match = re.search(r'(\d+)$', b_name)
        b_num = b_num_match.group(1) if b_num_match else None

        # On cherche tous les candidats plausibles
        candidates = []
        for c in columns:
            clean_c = _full_clean(c)
            if clean_b in clean_c or clean_c in clean_b:
                c_num_match = re.search(r'(\d+)$', c)
                c_num = c_num_match.group(1) if c_num_match else None

                if b_num == c_num:
                    candidates.append((c, 0))  # Perfect number match
                elif b_num is not None and c_num is None:
                    candidates.append((c, 1))  # Number in config but not in Excel (Fallback possible)
                elif b_num is None and c_num is not None:
                    candidates.append((c, 2))  # Number in Excel but not in config (Unlikely)

        if candidates:
            # On prend le meilleur score (0 > 1 > 2)
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        return None

    def _is_true(self, val):
        if pd.isna(val) or str(val).strip() == '':
            return True  # Par défaut, si c'est vide, on considère l'actif disponible

        if isinstance(val, (bool, np.bool_)): return val
        # Gestion des nombres (0 = False, autre = True)
        try:
            num = float(val)
            return num != 0
        except (ValueError, TypeError):
            pass
        return str(val).strip().upper() in ['VRAI', 'TRUE', 'OUI', '1', '1.0']

    def _prepare_optimization(self, tickers, df):
        total_capital = sum(Config.BUDGET_BROKERS.values())
        if total_capital <= 0: return [], []

        active_brokers = self._get_active_brokers()
        ticker_col = 'Ticker Yahoo Finance'
        base_cols = {ticker_col, 'Nom', 'Pays', 'Prix', 'EPS', 'PER', 'Croissance', 'PEG', 'Volume', 'Achat',
                     'Chance MOAT', 'Secteur', 'Poids'}
        broker_cols_in_df = [c for c in df.columns if c not in base_cols]

        matrix_access = []
        for t in tickers:
            row = df[df[ticker_col] == t].iloc[0]
            row_access = []
            for b_name in active_brokers:
                col = self._get_broker_col(b_name, broker_cols_in_df)
                access = True
                if col:
                    val = row[col]
                    if not pd.isna(val): access = self._is_true(val)
                row_access.append(access)
            matrix_access.append(row_access)

        return matrix_access, active_brokers

    def _get_active_brokers(self):
        return [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]

    def _optimize_portfolio_convex(self, tickers, returns, cov_mat, matrix_access, active_brokers, vine, is_etf_list):
        num_tickers = len(tickers)
        num_brokers = len(active_brokers)
        total_capital = sum(Config.BUDGET_BROKERS.values())

        # 1. Préparation des contraintes et bornes
        broker_ratios = [Config.BUDGET_BROKERS[b] / total_capital for b in active_brokers]

        # Variable : une matrice (num_tickers x num_brokers) aplatie
        n_vars = num_tickers * num_brokers

        # Bornes : 0 si non accessible, sinon [0, budget_broker]
        bounds = []
        for i in range(num_tickers):
            for j in range(num_brokers):
                if matrix_access[i][j]:
                    # Plafond à 100% du capital disponible sur ce broker
                    max_w = broker_ratios[j]
                    bounds.append((0.0, max_w))
                else:
                    bounds.append((0.0, 0.0))

        # Contraintes : La somme des poids d'un broker j doit être égale à son ratio de capital
        constraints = []
        for j in range(num_brokers):
            def broker_sum_constraint(w_flat, b_idx=j):
                w_matrix = w_flat.reshape(num_tickers, num_brokers)
                return np.sum(w_matrix[:, b_idx]) - broker_ratios[b_idx]

            constraints.append({'type': 'eq', 'fun': broker_sum_constraint})

        mean_rets = returns.mean().values * 252

        # --- SIMULATION MONTE CARLO VIA COPULE ---
        print(f"    * Lancement de 500000 simulations Monte Carlo (Ratio STARR)...")
        U_sim = vine.simulate(n_obs=500000)

        # Transformation des probabilités U en rendements via les marginales t-Student ajustées
        sim_returns = np.zeros((500000, num_tickers))
        for i in range(num_tickers):
            # On ajuste une distribution t sur les rendements historiques de l'actif i
            params = stats.t.fit(returns.iloc[:, i])
            # On transforme U_sim[:, i] en rendements sim_i
            sim_returns[:, i] = stats.t.ppf(U_sim[:, i], *params)

        def get_starr(w_flat, alpha=0.05):
            w_matrix = w_flat.reshape(num_tickers, num_brokers)
            w_global = np.sum(w_matrix, axis=1)

            # Rendements du portefeuille pour chaque scénario (journaliers)
            port_returns = np.dot(sim_returns, w_global)

            # Rendement moyen annuel attendu basé sur l'historique (plus stable)
            mean_ret = np.dot(w_global, mean_rets)

            # Calcul de la CVaR en échelle ANNUELLE cohérente avec mean_ret
            # sim_returns sont journaliers → CVaR journalière × sqrt(252) pour annualiser
            var_threshold = np.percentile(port_returns, alpha * 100)
            tail_returns = port_returns[port_returns <= var_threshold]

            cvar_daily = -np.mean(tail_returns) if len(tail_returns) > 0 else 1e-4
            cvar = cvar_daily * np.sqrt(252)  # Annualisation de la CVaR

            # Plancher bas (0.5%) pour éviter division par zéro, sans écraser le signal
            cvar = max(cvar, 0.005)

            starr = mean_ret / cvar
            if mean_ret < 0:
                starr = mean_ret * cvar  # Pénaliser les rendements négatifs

            return mean_ret, cvar, starr

        def get_perf(w_flat):
            # On garde une interface similaire mais on retourne STARR à la place de Sharpe si désiré
            # Ici on va optimiser directement le STARR
            ret, risk, ratio = get_starr(w_flat)
            return ret, risk, ratio

        # --- PHASE 1 : MAX STARR (MULTI-START) ---
        best_starr_w = None
        best_starr_val = -np.inf
        fallback_w0 = None

        print(f"    * Recherche du Global Max STARR (Solveur Convexe Multi-Start)...")
        for start_node in range(5):
            w0 = np.zeros(n_vars)
            for j in range(num_brokers):
                idx_avail = [i for i in range(num_tickers) if matrix_access[i][j]]
                if idx_avail:
                    val = broker_ratios[j] / len(idx_avail)
                    for i_idx in idx_avail:
                        w0[i_idx * num_brokers + j] = val

            if fallback_w0 is None:
                # Appliquer les bornes strictes avant de copier en fallback
                lb = [b[0] for b in bounds]
                ub = [b[1] for b in bounds]
                w0 = np.clip(w0, lb, ub)
                fallback_w0 = w0.copy()

            if start_node > 0:
                w0 += np.random.normal(0, 0.01, size=n_vars)
                lb = [b[0] for b in bounds]
                ub = [b[1] for b in bounds]
                w0 = np.clip(w0, lb, ub)

            res = minimize(
                lambda w: -get_starr(w)[2],
                w0, method='SLSQP', bounds=bounds, constraints=constraints,
                options={'ftol': 1e-6, 'maxiter': 500, 'eps': 1e-3}
            )
            if res.success and res.fun is not None and -res.fun > best_starr_val:
                best_starr_val = -res.fun
                best_starr_w = res.x

        if best_starr_w is None:
            best_starr_w = fallback_w0
            best_starr_val = get_starr(best_starr_w)[2]

        # --- PHASE 2 : MIN CVAR (STARR >= 90% du Max) ---
        print(f"    * Sélection du Min CVaR dans la zone STARR >= 90% du max...")
        target_starr = 0.9 * best_starr_val if best_starr_val >= 0 else 1.1 * best_starr_val
        starr_constraint = {'type': 'ineq', 'fun': lambda w: get_starr(w)[2] - target_starr}

        res_min_risk = minimize(
            lambda w: get_starr(w)[1],
            best_starr_w, method='SLSQP', bounds=bounds, constraints=constraints + [starr_constraint],
            options={'ftol': 1e-6, 'maxiter': 500, 'eps': 1e-3}
        )

        final_w_flat = res_min_risk.x if (res_min_risk.success and res_min_risk.x is not None) else best_starr_w
        final_ret, final_risk, final_starr = get_starr(final_w_flat)

        # --- PHASE 3 : QUANTIFICATION (1% Increments) ---
        w_matrix_cont = final_w_flat.reshape(num_tickers, num_brokers)
        final_matrix_discrete = np.zeros((num_tickers, num_brokers), dtype=int)

        for j in range(num_brokers):
            if broker_ratios[j] > 0:
                poids_relatifs = w_matrix_cont[:, j] / broker_ratios[j]
                # Hare-Niemeyer pour discrétiser en 100 unités (1% chacune)
                poids_pct = poids_relatifs * 100
                entiers = np.floor(np.maximum(poids_pct, 0)).astype(int)
                restes = poids_pct - entiers
                diff = 100 - entiers.sum()
                if diff > 0:
                    indices_prioritaires = np.argsort(restes)[-diff:]
                    for idx in indices_prioritaires:
                        entiers[idx] += 1
                final_matrix_discrete[:, j] = entiers

        print(f"    * Max STARR possible : {best_starr_val:.2f}")
        print(
            f"    * Solution retenue (Min CVaR dans zone 90%) : STARR {final_starr:.2f}, CVaR {final_risk * 100:.2f}%")

        return final_matrix_discrete, final_starr, [100] * num_brokers

    @staticmethod
    def _hare_niemeyer(exact_pcts_series, target=100):
        floors = exact_pcts_series.apply(lambda x: int(x))
        remainders = exact_pcts_series - floors
        deficit = target - int(floors.sum())
        if deficit > 0:
            top_idx = remainders.nlargest(int(deficit)).index
            floors[top_idx] += 1
        elif deficit < 0:
            bot_idx = remainders.nsmallest(int(-deficit)).index
            floors[bot_idx] -= 1
        return floors.astype(int)

    def update_excel(self, results):
        print(f"\n[2/3] Mise à jour de {Config.EXCEL_FILE}...")
        ticker_col = 'Ticker Yahoo Finance'
        score_col = 'Chance MOAT'

        original_cols = []
        # 1. Chargement et normalisation rapide de l'existant
        if os.path.exists(Config.EXCEL_FILE):
            try:
                df = pd.read_excel(Config.EXCEL_FILE)
                original_cols = df.columns.tolist()
                # Normalisation de la colonne ticker (une seule fois, de façon vectorisée)
                if ticker_col not in df.columns:
                    potential = [c for c in df.columns if isinstance(c, str) and 'TICKER' in c.upper()]
                    col_to_rename = potential[0] if potential else df.columns[0]
                    df.rename(columns={col_to_rename: ticker_col}, inplace=True)
                    original_cols = [ticker_col if c == col_to_rename else c for c in original_cols]

                if 'Secteur' not in df.columns:
                    potential_secteur = [c for c in df.columns if isinstance(c, str) and 'SECTEUR' in c.upper()]
                    if potential_secteur:
                        col_secteur = potential_secteur[0]
                        df.rename(columns={col_secteur: 'Secteur'}, inplace=True)
                        original_cols = ['Secteur' if c == col_secteur else c for c in original_cols]

                if 'Achat' not in df.columns:
                    potential_achat = [c for c in df.columns if isinstance(c, str) and 'ACHAT' in c.upper()]
                    if potential_achat:
                        col_achat = potential_achat[0]
                        df.rename(columns={col_achat: 'Achat'}, inplace=True)
                        original_cols = ['Achat' if c == col_achat else c for c in original_cols]

                # On s'assure que l'index est propre pour une fusion immédiate
                df[ticker_col] = df[ticker_col].astype(str).str.strip().str.upper()
                df.set_index(ticker_col, inplace=True)
            except Exception as e:
                print(f"  ! Erreur lecture {Config.EXCEL_FILE}: {e}")
                df = pd.DataFrame(columns=[ticker_col]).set_index(ticker_col)
        else:
            df = pd.DataFrame(columns=[ticker_col]).set_index(ticker_col)

        # 2. Préparation des nouveaux résultats
        new_data_list = []
        for ticker, res in results.items():
            score, metrics = res
            growth = metrics.get('CAGR', 0)
            final_score = float(score) if score is not None else 0.0
            if 0 < final_score <= 1.0: final_score *= 100

            peg = metrics.get('PEG')

            entry = {
                ticker_col: str(ticker).strip().upper(),
                'Nom': metrics.get('Nom', ''),
                'Pays': metrics.get('Pays', 'Inconnu'),
                'Secteur': metrics.get('Secteur', ''),
                'Prix': float(metrics.get('Prix', 0)),
                'EPS': float(metrics.get('EPS', 0)),
                'PER': round(float(metrics.get('PER', 0)), 2) if metrics.get('PER', 0) else np.nan,
                'Croissance': round(float(growth) * 100, 2) if (growth and not np.isnan(growth)) else np.nan,
                'PEG': round(float(peg), 3) if (peg and not np.isnan(peg)) else np.nan,
                'Volume': int(metrics.get('Volume', 0)),
                'Achat': metrics.get('Achat', False),
                score_col: round(final_score, 2)
            }
            new_data_list.append(entry)

        # 3. Création d'un DataFrame temporaire avec les nouveaux résultats
        new_df = pd.DataFrame(new_data_list).set_index(ticker_col)

        # 4. Fusion "intelligente" : on donne priorité aux nouvelles données tout en préservant
        # toutes les colonnes existantes (ex: brokers) de l'utilisateur.
        # combine_first garde l'index de new_df ET df, et remplit avec les valeurs de l'utilisateur
        # si new_df ne les fournit pas. On s'assure d'abord que les colonnes ont le même type si possible.

        # Pour les secteurs et textes, si l'utilisateur avait mis "ETF" (à la main), on ne veut l'écraser
        # QUE si new_df a une meilleure valeur (hors vide).
        # On remplace les vides de new_df par NaN pour que combine_first garde la valeur utilisateur si elle existe.
        new_df.replace('', np.nan, inplace=True)

        # Protection des entrées manuelles 'ETF' de l'utilisateur
        if 'Secteur' in df.columns:
            user_etf_mask = df['Secteur'].astype(str).str.upper().str.contains('ETF', na=False)
            for t in df[user_etf_mask].index:
                if t in new_df.index:
                    new_df.at[t, 'Secteur'] = df.at[t, 'Secteur']

        # Protection du signal Achat manuel si l'utilisateur l'a forcé à VRAI
        if 'Achat' in df.columns:
            for t in df.index:
                if t in new_df.index:
                    # On conserve l'achat s'il était explicitement vrai dans le fichier de l'utilisateur
                    val = df.at[t, 'Achat']
                    if val is True or str(val).strip().upper() in ['VRAI', 'OUI', '1', '1.0', 'TRUE']:
                        new_df.at[t, 'Achat'] = True

        df = new_df.combine_first(df)

        # 5. Post-traitement (Secteur/Poids) uniquement pour les nouveaux et existants vides
        if 'Secteur' not in df.columns:
            df['Secteur'] = 'TODO'
        if 'Poids' not in df.columns:
            df['Poids'] = 0.0

        mask_new = df['Secteur'].isna() | (df['Secteur'] == "")
        df.loc[mask_new, 'Secteur'] = 'TODO'
        df.loc[mask_new, 'Poids'] = 0.0

        # On s'assure que les colonnes broker de Config existent ou ont un équivalent
        for b_name in Config.BUDGET_BROKERS:
            if not self._get_broker_col(b_name, df.columns):
                df[b_name] = np.nan

        # 6. Sauvegarde
        df.reset_index(inplace=True)

        # Restauration de l'ordre original des colonnes
        if original_cols:
            if ticker_col not in original_cols:
                original_cols.insert(0, ticker_col)
            current_cols = df.columns.tolist()
            ordered_cols = []
            for col in original_cols:
                if col in current_cols:
                    ordered_cols.append(col)
                    current_cols.remove(col)
            ordered_cols.extend(current_cols)
            df = df[ordered_cols]

        df.to_excel(Config.EXCEL_FILE, index=False)
        print(f"  -> {Config.EXCEL_FILE} mis à jour avec succès (colonnes préservées).")
        return df

    def run_repartition(self, df):
        print(f"\n[3/3] Calcul de la répartition optimale...")
        ticker_col = 'Ticker Yahoo Finance'
        score_col = 'Chance MOAT'
        achat_col = 'Achat'

        # On identifie les colonnes broker
        base_cols = {ticker_col, 'Nom', 'Pays', 'Prix', 'EPS', 'PER', 'Croissance', 'PEG', 'Volume', achat_col,
                     score_col, 'Secteur', 'Poids'}
        broker_cols = [c for c in df.columns if c not in base_cols]
        active_brokers = [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]

        def is_available(row):
            if str(row.get(ticker_col, '')).upper() in forced_tickers_upper: return True
            if 'ETF' in str(row.get('Secteur', '')).upper(): return True
            if not Config.USE_BROKER_CONSTRAINTS: return True
            if not active_brokers: return True

            # 1. On cherche d'abord explicitement sur nos brokers actifs
            has_vrai_chez_nous = False
            has_data_chez_nous = False
            for b_name in active_brokers:
                col = self._get_broker_col(b_name, broker_cols)
                if col:
                    val = row[col]
                    if not pd.isna(val):
                        has_data_chez_nous = True
                        if self._is_true(val): has_vrai_chez_nous = True

            if has_vrai_chez_nous: return True

            # 2. Si on a des données explicites chez nous et que c'est FAUX
            # on vérifie si c'est dispo ailleurs avant de rejeter
            has_vrai_ailleurs = False
            has_data_ailleurs = False
            for col in broker_cols:
                val = row[col]
                if not pd.isna(val):
                    has_data_ailleurs = True
                    if self._is_true(val): has_vrai_ailleurs = True

            if has_vrai_ailleurs and not has_vrai_chez_nous:
                # Dispo ailleurs mais pas chez nous -> Rejet
                return False

            # 3. Si AUCUNE donnée (ni chez nous ni ailleurs), on accepte par défaut
            if not has_data_ailleurs: return True

            return False

        # Filtrage avec debug pour comprendre pourquoi des actions sont exclues
        print(f"  - Analyse de {len(df)} tickers au total...")

        # 1. Score (On accepte aussi les ETF même sans score MOAT, ainsi que les actifs forcés)
        def clean_score(s):
            if pd.isna(s): return 0.0
            try:
                s_str = str(s).strip().replace(',', '.')
                if s_str.endswith('%'):
                    return float(s_str[:-1])
                val = float(s_str)
                if 0 < val <= 1.0:
                    val *= 100
                return val
            except:
                return 0.0

        df[score_col] = df[score_col].apply(clean_score)

        mask_sector_etf = df['Secteur'].astype(str).str.upper().str.contains('ETF')
        forced_tickers_upper = [t.upper() for t in Config.FORCED_BUY_TICKERS]
        mask_forced = df[ticker_col].str.upper().isin(forced_tickers_upper)
        mask_score = (df[score_col] >= Config.SCORE_THRESHOLD) | mask_sector_etf | mask_forced
        f1 = df[mask_score]
        print(f"    * {len(f1)} tickers ont un Score >= {Config.SCORE_THRESHOLD} (ou sont des ETF / Forcés)")

        # 2. Achat (Les ETF et actifs forcés sont considérés comme achetables par défaut)
        def check_achat_liberal(row):
            if str(row.get(ticker_col, '')).upper() in forced_tickers_upper: return True
            is_etf = 'ETF' in str(row.get('Secteur', '')).upper()
            if is_etf: return True
            return self._is_true(row.get(achat_col))

        f2 = f1[f1.apply(check_achat_liberal, axis=1)]
        print(f"    * {len(f2)} tickers ont un signal ACHAT valide (ou sont des ETF / Forcés)")

        # 3. Disponibilité
        mask_avail = f2.apply(is_available, axis=1)

        eligible = f2[mask_avail]
        print(f"    * {len(eligible)} tickers sont disponibles sur vos brokers (ou nouveaux)")

        if eligible.empty:
            print(f"  ! Aucun actif éligible après filtrage (Score >= {Config.SCORE_THRESHOLD} et Achat=VRAI).")
            return

        tickers = eligible[ticker_col].tolist()
        # On identifie les ETF pour l'affichage, mais ils passent dans le MÊME pipeline STARR
        etf_set = set()
        for t in tickers:
            row = df[df[ticker_col] == t]
            if not row.empty and ('ETF' in str(row['Secteur'].iloc[0]).upper()
                                  or t.upper() in [ft.upper() for ft in Config.FORCED_BUY_TICKERS]):
                etf_set.add(t)

        print(f"  Optimisation pour {len(tickers)} actifs éligibles "
              f"({len(etf_set)} ETF + {len(tickers) - len(etf_set)} actions) — pipeline STARR unifié.")
        if len(tickers) > 50:
            print(f"  (Note: {len(tickers)} actifs, l'optimisation peut être longue)")

        try:
            total_capital = sum(Config.BUDGET_BROKERS.values())

            # --- TÉLÉCHARGEMENT HISTORIQUE (ETF + ACTIONS ensemble) ---
            print(f"  - Téléchargement des données historiques (5 ans) pour {len(tickers)} actifs...")
            raw = yf.download(tickers, period="5y", interval="1d", progress=False, group_by='ticker')

            if raw.empty:
                print("  ! Données historiques vides.")
                return

            # Extraction des prix de clôture (gestion ticker unique vs multiple)
            if len(tickers) == 1:
                close_data = raw['Close'].to_frame()
                close_data.columns = [tickers[0]]
            else:
                close_data = pd.DataFrame()
                for t in tickers:
                    try:
                        if t in raw.columns.get_level_values(0):
                            close_data[t] = raw[t]['Close']
                    except Exception:
                        pass

            data = close_data

            # --- CONVERSION EN EUROS ---
            print(f"  - Conversion des prix en EUR (recherche des devises)...")
            currencies = {}
            for t in data.columns:
                try:
                    c = yf.Ticker(t).info.get('currency', 'EUR')
                    if pd.isna(c) or not c:
                        c = 'EUR'
                    currencies[t] = str(c)
                except Exception:
                    currencies[t] = 'EUR'

            distinct_currencies = set(currencies.values()) - {'EUR', 'eur'}
            if distinct_currencies:
                fx_symbols = []
                for c in distinct_currencies:
                    if c in ('GBp', 'GBX'):
                        fx_symbols.append('GBPEUR=X')
                    elif c.upper() == 'ZAC':
                        fx_symbols.append('ZAREUR=X')
                    elif c.upper() == 'ILA':
                        fx_symbols.append('ILSEUR=X')
                    else:
                        fx_symbols.append(f'{c.upper()}EUR=X')

                fx_symbols = list(set(fx_symbols))
                if fx_symbols:
                    print(f"  - Téléchargement des taux de change : {', '.join(fx_symbols)}")
                    fx_dl = yf.download(fx_symbols, period="5y", interval="1d", progress=False)
                    if not fx_dl.empty:
                        if len(fx_symbols) == 1:
                            fx_close = fx_dl['Close'].to_frame() if 'Close' in fx_dl else fx_dl.to_frame()
                            fx_close.columns = fx_symbols
                        else:
                            fx_close = fx_dl['Close'] if 'Close' in fx_dl else fx_dl

                        fx_close = fx_close.reindex(data.index).ffill().bfill()

                        for t in data.columns:
                            c = currencies[t]
                            if c in ('EUR', 'eur'):
                                continue
                            div_100 = False
                            base_cur = c.upper()
                            if c in ('GBp', 'GBX'):
                                base_cur = 'GBP';
                                div_100 = True
                            elif base_cur == 'ZAC':
                                base_cur = 'ZAR';
                                div_100 = True
                            elif base_cur == 'ILA':
                                base_cur = 'ILS';
                                div_100 = True
                            fx_sym = f'{base_cur}EUR=X'
                            if fx_sym in fx_close.columns:
                                if div_100:
                                    data[t] = data[t] / 100.0
                                data[t] = data[t] * fx_close[fx_sym]

            # Nettoyage
            old_cols = set(data.columns)
            data = data.dropna(axis=1, thresh=len(data) * 0.01).ffill()
            dropped = old_cols - set(data.columns)
            if dropped:
                print(f"  ! {len(dropped)} actifs supprimés (historique insuffisant) : {dropped}")

            if data.empty:
                print("  ! Données historiques vides après nettoyage.")
                return

            returns = data.pct_change().dropna()
            # Remplacement des NaN récents par la moyenne du portefeuille
            returns_mean = returns.mean(axis=1)
            for c in returns.columns:
                returns[c] = returns[c].fillna(returns_mean)
            returns = returns.dropna().clip(-0.5, 0.5)

            if returns.empty or len(returns) < 30:
                print("  ! Pas assez de données historiques.")
                return

            # Dédoublonnage (cross-listings), ETF exclus du fuzzy matching
            returns = self.deduplicate_tickers(returns, df)
            all_tickers_optim = returns.columns.tolist()
            etf_set_optim = etf_set & set(all_tickers_optim)

            print(f"  - {len(etf_set_optim)} ETF + {len(all_tickers_optim) - len(etf_set_optim)} actions "
                  f"dans l'optimisation STARR unifiée.")

            # --- COPULE DE VINE (ETF + ACTIONS) ---
            print("  - Ajustement de la copule de Vine (ETF + Actions)...")
            U = returns.rank() / (len(returns) + 1)
            vine = DVineCopula(family=Config.VINE_FAMILY, trunc_high=Config.VINE_TRUNC_HIGH).fit(U.values)
            corr_mat = vine.implied_correlation()
            if not is_pos_def(corr_mat):
                corr_mat = nearest_pos_def(corr_mat)

            vols = returns.std() * np.sqrt(252)
            cov_mat = np.outer(vols, vols) * corr_mat

            # --- OPTIMISATION CONVEXE STARR (ETF + ACTIONS) ---
            matrix_access, active_brokers = self._prepare_optimization(all_tickers_optim, df)

            print(f"  - Optimisation Convexe Globale (Ratio STARR via Copules & Monte Carlo)...")
            is_etf_list = [t in etf_set_optim for t in all_tickers_optim]
            units_final, final_ratio, b_units_list = self._optimize_portfolio_convex(
                all_tickers_optim, returns, cov_mat, matrix_access, active_brokers, vine, is_etf_list
            )

            # --- RECONSTRUCTION DES RÉSULTATS ---
            results = []
            num_tickers = len(all_tickers_optim)
            num_brokers = len(active_brokers)
            for i in range(num_tickers):
                for j in range(num_brokers):
                    u = units_final[i, j]  # entier 0-100 dans la pie du broker j
                    if u > 0:
                        b_name = active_brokers[j]
                        b_ratio = Config.BUDGET_BROKERS[b_name] / total_capital
                        pie_pct = float(u)  # % dans la pie du broker
                        global_pct = pie_pct * b_ratio  # % dans le portefeuille total
                        results.append({
                            'Ticker': all_tickers_optim[i],
                            'IsETF': all_tickers_optim[i] in etf_set_optim,
                            'Broker': b_name,
                            'Pie%': pie_pct,
                            'Poids total (%)': global_pct,
                        })

            alloc = pd.DataFrame(results)

            # Mise à jour des poids dans le DF principal
            df.set_index(ticker_col, inplace=True)
            df['Poids'] = 0.0
            df['Broker'] = ""
            for _, row in alloc.iterrows():
                if row['Ticker'] in df.index:
                    df.at[row['Ticker'], 'Poids'] = row['Poids total (%)']
                    df.at[row['Ticker'], 'Broker'] = row['Broker']

            df.reset_index(inplace=True)
            df.to_excel(Config.EXCEL_FILE, index=False)

            print("\n--- RÉPARTITION FINALE (GLOBAL) ---")
            if not alloc.empty:
                for _, row in alloc.sort_values('Poids total (%)', ascending=False).iterrows():
                    etf_label = " (ETF)" if row.get("IsETF", False) else ""
                    print(
                        f"    * {(row['Ticker'] + etf_label):<22} : {row['Poids total (%)']:>6.2f}% ({row['Broker']})")

                print("\n--- DÉTAILS DES PIES (PAR BROKER) ---")
                for b_name in Config.BUDGET_BROKERS:
                    if Config.BUDGET_BROKERS[b_name] <= 0:
                        continue
                    broker_alloc = alloc[alloc['Broker'] == b_name].sort_values('Pie%', ascending=False)
                    if broker_alloc.empty:
                        continue
                    print(f"\n  [{b_name}]")
                    for _, row in broker_alloc.iterrows():
                        etf_label = " (ETF)" if row.get("IsETF", False) else ""
                        print(f"    * {(row['Ticker'] + etf_label):<22} : {int(row['Pie%']):>3}%")
                    print(f"    (Total: {int(broker_alloc['Pie%'].sum())}%)")

                print("\n--- RÉCAPITULATIF PAR BROKER ---")
                broker_summary = alloc.groupby('Broker')['Poids total (%)'].sum()
                for b_name in Config.BUDGET_BROKERS:
                    if Config.BUDGET_BROKERS[b_name] <= 0:
                        continue
                    total_pct = broker_summary.get(b_name, 0.0)
                    target_pct = Config.BUDGET_BROKERS[b_name] / total_capital * 100
                    print(f"    * {b_name:<15} : {total_pct:>6.2f}% (Cible: {target_pct:>6.2f}%)")

                # Performance finale sur l'ensemble du portefeuille (ETF + actions)
                final_weights = np.zeros(len(all_tickers_optim))
                for i, t in enumerate(all_tickers_optim):
                    row_t = alloc[alloc['Ticker'] == t]
                    if not row_t.empty:
                        final_weights[i] = row_t['Poids total (%)'].sum() / 100

                ret, risk, ratio = self.portfolio_performance(final_weights, returns, cov_mat)
                print("\n--- PERFORMANCE ESTIMÉE (ETF + ACTIONS) ---")
                print(f"    * Rendement Annuel : {ret * 100:>6.2f}%")
                print(f"    * Volatilité (Risque): {risk * 100:>6.2f}%")
                print(f"    * Ratio de Sharpe   : {ratio:>6.2f}")
            else:
                print("    ! Aucune allocation générée.")

        except Exception as e:
            print(f"  ! Erreur optimisation: {e}")
            import traceback
            traceback.print_exc()

    def load_local_data(self, ticker):
        """Charge les données financières depuis le cache local (Excel)."""
        file_path = Config.OUTPUT_DIR / f"{ticker.replace(':', '_')}.xlsx"
        if not file_path.exists():
            return None
        try:
            # On liste d'abord les feuilles pour ne charger que celles qui existent
            xl = pd.ExcelFile(file_path)
            sheets_to_load = [s for s in ["income", "balance", "cashflow"] if s in xl.sheet_names]

            data = pd.read_excel(file_path, sheet_name=sheets_to_load, index_col=0)
            # On remet les index en datetime pour la cohérence
            for k in data:
                data[k].index = pd.to_datetime(data[k].index)

            # Charger les infos/métriques si disponibles
            if "info" in xl.sheet_names:
                info_df = pd.read_excel(file_path, sheet_name="info")
                if not info_df.empty:
                    # Conversion de la première ligne en dictionnaire
                    data["info"] = info_df.iloc[0].to_dict()

            return data
        except Exception as e:
            print(f"  ! Erreur lecture locale {ticker}: {e}")
            return None

    def save_data(self, ticker, data):
        """Sauvegarde les données financières dans un fichier Excel local."""
        if not data:
            return False

        # Vérification s'il y a au moins une donnée réelle avant de créer le fichier
        has_real_data = any(isinstance(df, pd.DataFrame) and not df.empty for df in data.values() if df is not None)
        if not has_real_data:
            return False

        file_path = Config.OUTPUT_DIR / f"{ticker.replace(':', '_')}.xlsx"
        try:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for key, df in data.items():
                    if key == "info" and isinstance(df, dict) and df:
                        # Sauvegarde des infos sous forme de table simple
                        pd.DataFrame([df]).to_excel(writer, sheet_name="info", index=False)
                    elif isinstance(df, pd.DataFrame) and not df.empty:
                        df.to_excel(writer, sheet_name=key)
            return True
        except Exception as e:
            print(f"  ! Erreur sauvegarde locale {ticker}: {e}")
            return False

    def merge_data(self, old_data, new_data):
        """Fusionne les anciennes données locales avec les nouvelles données de Yahoo Finance."""
        if not old_data: return new_data
        if not new_data: return old_data

        merged = {}
        for key in ["income", "balance", "cashflow"]:
            old_df = old_data.get(key)
            new_df = new_data.get(key)

            if old_df is None: old_df = pd.DataFrame()
            if new_df is None: new_df = pd.DataFrame()

            if not old_df.empty and not new_df.empty:
                # On concatène et on supprime les doublons basés sur l'index (la date)
                # On garde la version la plus récente ('last') en cas de conflit
                combined = pd.concat([old_df, new_df])
                combined = combined[~combined.index.duplicated(keep='last')].sort_index()
                merged[key] = combined
            elif not new_df.empty:
                merged[key] = new_df
            else:
                merged[key] = old_df

        # Le reste (info)
        merged["info"] = new_data.get("info") or old_data.get("info", {})
        return merged

    def _analyze_ticker_task(self, ticker_str, results, excellent_stocks):
        """Tâche d'analyse pour un seul ticker, utilisée en parallèle."""
        try:
            file_path = Config.OUTPUT_DIR / f"{ticker_str.replace(':', '_')}.xlsx"
            status = self.cache.get_status(ticker_str, file_path)

            data = None
            if status == "local_ok":
                data = self.load_local_data(ticker_str)
                if data is None: status = "download"

            if status in ["download", "update", "too_old"]:
                new_data = self.fetch_data(ticker_str)
                if status in ["update", "too_old"]:
                    old_data = self.load_local_data(ticker_str)
                    data = self.merge_data(old_data, new_data)
                else:
                    data = new_data

            if data:
                score, metrics, analyse_df, score_df = self.analyze_financials(ticker_str, data)

                with self.results_lock:
                    results[ticker_str] = (score, metrics)
                    if score >= Config.SCORE_THRESHOLD:
                        excellent_stocks.append(ticker_str)

                # Affichage des résultats
                is_achat = metrics.get('Achat', False)
                is_etf = 'ETF' in str(metrics.get('Secteur', '')).upper()
                status_icon = "⭐" if score >= Config.SCORE_THRESHOLD or is_etf else "📈"
                achat_tag = "[ACHAT]" if is_achat else ""

                output_msg = f"  {status_icon} {ticker_str: <6} | Score: {score: >6.2f}/100 | {metrics.get('Nom', ''):.30} {achat_tag}"

                if is_etf:
                    output_msg += f"\n     >>> ETF ÉLIGIBLE (DCA Strat)"
                elif score >= Config.SCORE_THRESHOLD:
                    if is_achat:
                        output_msg += f"\n     >>> OPPORTUNITÉ DÉCOUVERTE ! {ticker_str} est éligible à l'achat."
                    else:
                        output_msg += f"\n     (Score élevé mais critères d'achat non remplis pour {ticker_str})"
                else:
                    output_msg += f"\n     (Score insuffisant: {score:.2f} < {Config.SCORE_THRESHOLD})"

                tqdm.write(output_msg)

                # Post-processing data
                if not analyse_df.empty: data['analyse'] = analyse_df
                if not score_df.empty: data['score'] = score_df

                saved = self.save_data(ticker_str, data)

                # Cache update UNQUEMENT si on a réussi à sauvegarder (donc si on a des données réelles)
                if saved:
                    income_data = data.get("income")
                    latest_year = income_data.index.max().year if income_data is not None and not income_data.empty else 0
                    self.cache.update(ticker_str, latest_year, float(score) if score is not None else 0.0, metrics)
                    return True
                else:
                    tqdm.write(f"  ⚠️ {ticker_str: <6} | Aucune donnée financière réelle trouvée (pas de sauvegarde).")
                    return False
            else:
                tqdm.write(f"  ❌ {ticker_str: <6} | Échec récupération des données.")
                return False
        except Exception as e:
            tqdm.write(f"  ⚠️  Erreur sur {ticker_str}: {e}")
            return False

    def run(self):
        print("=== MASTER INVEST v1.0 ===")
        if not os.path.exists(Config.TICKERS_CSV):
            print(f"Erreur: {Config.TICKERS_CSV} introuvable.")
            return

        try:
            df_tickers = pd.read_csv(Config.TICKERS_CSV)
            col = df_tickers.columns[0]
            tickers = df_tickers[col].dropna().astype(str).str.strip().unique().tolist()
            if len(col) <= 5 and col.isupper() and col != "TICKER":
                tickers.insert(0, col)
            tickers = [t for t in tickers if t.upper() != "TICKER"]
        except:
            tickers = []

        if not tickers:
            print("Aucun ticker trouvé.")
            return

        print(f"[1/3] Analyse de {len(tickers)} tickers...")

        results = {}
        excellent_stocks = []

        # Séparation des tickers : Cache vs Analyse
        to_analyze = []
        for t in tickers:
            ticker_str = str(t).strip()
            if not ticker_str or ticker_str.upper() == "NAN": continue

            cached = self.cache.get_cached_result(ticker_str)
            if cached:
                score, metrics = cached
                if score is None: score = 0.0

                # Correction à la volée du pays si Inconnu (pour les données en cache)
                if metrics.get('Pays') == 'Inconnu':
                    metrics['Pays'] = self.cache._infer_country(ticker_str)

                results[ticker_str] = (score, metrics)
                if score >= Config.SCORE_THRESHOLD:
                    excellent_stocks.append(ticker_str)
            else:
                to_analyze.append(ticker_str)

        if results:
            print(f"  -> {len(results)} tickers chargés depuis le cache (données récentes).")

        if to_analyze:
            print(f"  -> {len(to_analyze)} tickers à analyser (en parallèle)...")
            max_workers = min(10, os.cpu_count() or 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._analyze_ticker_task, t, results, excellent_stocks): t for t in
                           to_analyze}
                for _ in tqdm(as_completed(futures), total=len(to_analyze), desc="Analyse"):
                    pass

        self.cache.save()

        if excellent_stocks:
            print(
                f"\n--- RÉCAPITULATIF EXCELLENCE (Score > {Config.SCORE_THRESHOLD}) : {len(excellent_stocks)} actifs ---")
            if len(excellent_stocks) > 50:
                print(", ".join(excellent_stocks[:50]) + " ...")
            else:
                print(", ".join(excellent_stocks))
        df = self.update_excel(results)
        self.run_repartition(df)
        print("\nWorkflow terminé. Vérifiez ToutBroker.xlsx")


if __name__ == "__main__":
    app = MasterInvest()
    app.run()