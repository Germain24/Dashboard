"""D-Vine Copula + helpers matriciels (nearest_pos_def, is_pos_def)."""

from __future__ import annotations

import numpy as np
from scipy import stats

from .copulas import BivariateCopula


def is_pos_def(B: np.ndarray) -> bool:
    try:
        np.linalg.cholesky(B)
        return True
    except np.linalg.LinAlgError:
        return False


def nearest_pos_def(A: np.ndarray) -> np.ndarray:
    B = (A + A.T) / 2
    U, s, Vt = np.linalg.svd(B)
    A_pd = U @ np.diag(np.maximum(s, 1e-8)) @ Vt
    A_pd = (A_pd + A_pd.T) / 2
    I = np.eye(A.shape[0]); k = 1
    while True:
        try:
            np.linalg.cholesky(A_pd)
            break
        except np.linalg.LinAlgError:
            A_pd += I * (-np.min(np.real(np.linalg.eigvals(A_pd))) * k**2 + np.spacing(np.linalg.norm(A)))
            k += 1
    return A_pd


class DVineCopula:
    def __init__(self, family="t", max_trees=None, trunc_high=20.0):
        self.family = family; self.max_trees = max_trees; self.trunc_high = trunc_high
        self.copulas: dict = {}; self.fitted = False; self.n_trees_fitted = 0
        self.order: list[int] = []; self.n = 0; self.correction = 1.0

    def _greedy_order(self, U: np.ndarray) -> list[int]:
        n = U.shape[1]
        tau_mat = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                from scipy.stats import kendalltau
                tau, _ = kendalltau(U[:, i], U[:, j])
                tau_mat[i, j] = tau_mat[j, i] = abs(tau) if not np.isnan(tau) else 0.0
        tm = np.nan_to_num(tau_mat); i_m, j_m = np.unravel_index(np.argmax(np.triu(tm, 1)), tm.shape)
        order = [int(i_m), int(j_m)]; remaining = set(range(n)) - set(order)
        while remaining:
            left, right = order[0], order[-1]
            best_tau, best_node, best_side = -1, None, None
            for r in remaining:
                vl = tau_mat[left, r] if not np.isnan(tau_mat[left, r]) else 0.0
                vr = tau_mat[right, r] if not np.isnan(tau_mat[right, r]) else 0.0
                if vl > best_tau: best_tau, best_node, best_side = vl, r, "left"
                if vr > best_tau: best_tau, best_node, best_side = vr, r, "right"
            if best_node is None: best_node = next(iter(remaining)); best_side = "right"
            if best_side == "left": order.insert(0, best_node)
            else: order.append(best_node)
            remaining.remove(best_node)
        return order

    def fit(self, U: np.ndarray) -> "DVineCopula":
        n_obs, n = U.shape; self.n = n
        max_trees = min(self.max_trees or (n-1), n-1)
        self.order = self._greedy_order(U)
        U_ord = U[:, self.order]
        V = {i: U_ord[:, i].copy() for i in range(n)}
        dep_history = []
        tree = 1
        for tree in range(1, max_trees+1):
            V_next = {}
            for edge in range(n-tree):
                cop = BivariateCopula(family=self.family).fit(V[edge], V[edge+tree])
                self.copulas[(tree, edge)] = cop
                if tree < max_trees:
                    V_next[edge] = cop.h_function(V[edge], V[edge+tree])
                    V_next[edge+tree] = cop.h_function(V[edge+tree], V[edge])
            V = V_next
            pct = np.mean((np.concatenate(list(V.values())) < 0.01) | (np.concatenate(list(V.values())) > 0.99)) * 100 if V else 0
            dep_history.append(pct)
            if tree >= 3 and all(d > self.trunc_high for d in dep_history[-3:]): break
        self.n_trees_fitted = tree; self.fitted = True
        return self

    def implied_correlation(self) -> np.ndarray:
        rho_mat = np.eye(self.n); corrections, deps = [], []
        for edge in range(self.n-1):
            cop = self.copulas.get((1, edge))
            if not cop: continue
            fam = cop.family_fit or cop.family
            if fam in ("gaussian","t"):
                rho = cop.rho
                corrections.append(np.sqrt((cop.df+1)/cop.df) if fam=="t" else 1.0)
            elif fam == "clayton":
                tau = cop.theta/(cop.theta+2); rho = np.sin(np.pi/2*tau); corrections.append(np.sqrt(5/4))
            elif fam == "gumbel":
                tau = 1-1/cop.theta; rho = np.sin(np.pi/2*tau); corrections.append(np.sqrt(9/8))
            elif fam == "frank":
                rho = np.sin(np.pi/2*np.clip(cop.theta/9,-0.99,0.99)); corrections.append(1.0)
            elif fam == "bb7":
                tau = 1-2/(cop.delta*(cop.theta+2)); rho = np.sin(np.pi/2*np.clip(tau,-0.99,0.99))
                w = cop.theta/(cop.theta+cop.delta); corrections.append(w*np.sqrt(9/8)+(1-w)*np.sqrt(5/4))
            else:
                rho = 0.0; corrections.append(1.0)
            deps.append(abs(rho))
            i, j = self.order[edge], self.order[edge+1]
            rho_mat[i, j] = rho_mat[j, i] = rho
        self.correction = float(np.average(corrections, weights=np.array(deps)+1e-10)) if corrections else 1.0
        return rho_mat

    def simulate(self, n_obs: int = 100000) -> np.ndarray:
        rho_mat = self.implied_correlation()
        if not is_pos_def(rho_mat): rho_mat = nearest_pos_def(rho_mat)
        z = np.random.multivariate_normal(np.zeros(self.n), rho_mat, n_obs)
        return stats.norm.cdf(z)
