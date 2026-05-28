"""Copules bivariées (Gaussian, t, Clayton, Gumbel, Frank, BB7) + sélection AIC."""

from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import kendalltau


class BivariateCopula:
    N_PARAMS = {"gaussian":1,"t":2,"clayton":1,"gumbel":1,"frank":1,"bb7":2}
    AUTO_FAMILIES = ["gaussian","t","clayton","gumbel","frank","bb7"]

    def __init__(self, family="auto"):
        self.family = family; self.family_fit = None
        self.rho = 0.0; self.df = 4.0; self.theta = 1.0; self.delta = 0.5
        self.aic = np.inf; self.fitted = False

    @staticmethod
    def _clip(u): return np.clip(u, 1e-10, 1-1e-10)

    @staticmethod
    def ktau_to_pearson(tau): return np.sin(np.pi/2*tau)
    @staticmethod
    def ktau_to_clayton(tau): return max(2*max(tau,1e-6)/(1-max(tau,1e-6)), 0.01)
    @staticmethod
    def ktau_to_gumbel(tau): return max(1/(1-max(tau,1e-6)), 1.001)

    def _ld_gaussian(self, u, v, rho):
        u,v=self._clip(u),self._clip(v); x,y=stats.norm.ppf(u),stats.norm.ppf(v); r2=rho**2
        return -0.5*np.log(1-r2)-(r2*(x**2+y**2)-2*rho*x*y)/(2*(1-r2))

    def _ld_t(self, u, v, rho, df):
        from scipy.special import gammaln
        u,v=self._clip(u),self._clip(v); x,y=stats.t.ppf(u,df),stats.t.ppf(v,df); r2=rho**2
        q=(x**2+y**2-2*rho*x*y)/(df*(1-r2))
        return (gammaln((df+2)/2)+gammaln(df/2)-2*gammaln((df+1)/2)
                -0.5*np.log(1-r2)-((df+2)/2)*np.log(1+q)
                +((df+1)/2)*np.log(1+x**2/df)+((df+1)/2)*np.log(1+y**2/df))

    def _ld_clayton(self, u, v, theta):
        u,v=self._clip(u),self._clip(v); theta=max(theta,1e-6)
        lc=np.log(theta+1)-(theta+1)*(np.log(u)+np.log(v))-(2+1/theta)*np.log(u**(-theta)+v**(-theta)-1)
        return np.where(np.isfinite(lc), lc, -1e10)

    def _ld_gumbel(self, u, v, theta):
        u,v=self._clip(u),self._clip(v); theta=max(theta,1.001)
        lu,lv=-np.log(u),-np.log(v); S=lu**theta+lv**theta; C=np.exp(-S**(1/theta))
        lc=np.log(C)+(1/theta-2)*np.log(S)+(theta-1)*(np.log(lu)+np.log(lv))+np.log(S**(1/theta)+theta-1)-np.log(u)-np.log(v)
        return np.where(np.isfinite(lc), lc, -1e10)

    def _ld_frank(self, u, v, theta):
        u,v=self._clip(u),self._clip(v)
        if abs(theta)<1e-6: return np.zeros(len(u))
        et,etu,etv=np.exp(-theta),np.exp(-theta*u),np.exp(-theta*v)
        num=theta*(et-1)*np.exp(-theta*(u+v)); den=((et-1)+(etu-1)*(etv-1))**2
        return np.log(np.abs(num))-np.log(np.maximum(np.abs(den),1e-300))

    def _ld_bb7(self, u, v, theta, delta):
        u,v=self._clip(u),self._clip(v); theta,delta=max(theta,1.001),max(delta,0.01); eps=1e-6
        def _C(u_,v_):
            a,b=(1-(1-u_)**theta)**(-delta),(1-(1-v_)**theta)**(-delta)
            return 1-(1-np.maximum(a+b-1,1e-300)**(-1/delta))**(1/theta)
        d=(_C(u+eps,v+eps)-_C(u+eps,v-eps)-_C(u-eps,v+eps)+_C(u-eps,v-eps))/(4*eps*eps)
        return np.log(np.maximum(d,1e-300))

    def _h_gaussian(self,u,v,rho):
        u,v=self._clip(u),self._clip(v); x,y=stats.norm.ppf(u),stats.norm.ppf(v)
        return stats.norm.cdf((x-rho*y)/np.sqrt(1-rho**2))

    def _h_t(self,u,v,rho,df):
        u,v=self._clip(u),self._clip(v); x,y=stats.t.ppf(u,df),stats.t.ppf(v,df)
        return stats.t.cdf((x-rho*y)/np.sqrt((df+y**2)*(1-rho**2)/(df+1)), df+1)

    def _h_clayton(self,u,v,theta):
        u,v=self._clip(u),self._clip(v)
        return np.clip(v**(-(theta+1))*np.maximum(u**(-theta)+v**(-theta)-1,1e-300)**(-(1+1/theta)),1e-10,1-1e-10)

    def _h_gumbel(self,u,v,theta):
        u,v=self._clip(u),self._clip(v); lu,lv=-np.log(u),-np.log(v); S=lu**theta+lv**theta; C=np.exp(-S**(1/theta))
        return np.clip(C/v*lv**(theta-1)*S**(1/theta-1),1e-10,1-1e-10)

    def _h_frank(self,u,v,theta):
        u,v=self._clip(u),self._clip(v)
        if abs(theta)<1e-6: return u.copy()
        et,etu,etv=np.exp(-theta),np.exp(-theta*u),np.exp(-theta*v)
        return np.clip(((et-1)*etu)/np.maximum((et-1)+(etu-1)*(etv-1),1e-300),1e-10,1-1e-10)

    def _h_bb7(self,u,v,theta,delta):
        u,v=self._clip(u),self._clip(v); eps=1e-5
        def _C(u_,v_):
            a,b=(1-(1-u_)**theta)**(-delta),(1-(1-v_)**theta)**(-delta)
            return 1-(1-np.maximum(a+b-1,1e-300)**(-1/delta))**(1/theta)
        return np.clip((_C(u,v+eps)-_C(u,v-eps))/(2*eps),1e-10,1-1e-10)

    def h_function(self,u,v):
        f=self.family_fit or self.family
        if f=="gaussian": return self._h_gaussian(u,v,self.rho)
        if f=="t": return self._h_t(u,v,self.rho,self.df)
        if f=="clayton": return self._h_clayton(u,v,self.theta)
        if f=="gumbel": return self._h_gumbel(u,v,self.theta)
        if f=="frank": return self._h_frank(u,v,self.theta)
        if f=="bb7": return self._h_bb7(u,v,self.theta,self.delta)
        return self._h_gaussian(u,v,self.rho)

    def _fit_single(self, family, u, v, tau):
        c=BivariateCopula(family=family)
        if family=="gaussian":
            r=minimize(lambda p:-np.nansum(c._ld_gaussian(u,v,np.clip(p[0],-0.999,0.999))),[self.ktau_to_pearson(tau)],bounds=[(-0.999,0.999)])
            c.rho,ll=float(r.x[0]),-r.fun
        elif family=="t":
            r=minimize(lambda p:-np.nansum(c._ld_t(u,v,np.clip(p[0],-0.999,0.999),max(p[1],2.01))),[self.ktau_to_pearson(tau),5.0],bounds=[(-0.999,0.999),(2.01,50.0)])
            c.rho,c.df,ll=float(r.x[0]),float(r.x[1]),-r.fun
        elif family=="clayton":
            if tau<=0: c.theta,ll=0.01,np.nansum(c._ld_clayton(u,v,0.01))
            else:
                r=minimize(lambda p:-np.nansum(c._ld_clayton(u,v,max(p[0],0.01))),[self.ktau_to_clayton(tau)],bounds=[(0.01,20.0)])
                c.theta,ll=float(r.x[0]),-r.fun
        elif family=="gumbel":
            if tau<=0: c.theta,ll=1.001,np.nansum(c._ld_gumbel(u,v,1.001))
            else:
                r=minimize(lambda p:-np.nansum(c._ld_gumbel(u,v,max(p[0],1.001))),[self.ktau_to_gumbel(tau)],bounds=[(1.001,20.0)])
                c.theta,ll=float(r.x[0]),-r.fun
        elif family=="frank":
            r=minimize(lambda p:-np.nansum(c._ld_frank(u,v,p[0])),[1.0 if tau>=0 else -1.0],bounds=[(-30.0,30.0)])
            c.theta,ll=float(r.x[0]),-r.fun
        elif family=="bb7":
            if tau<=0: c.theta,c.delta,ll=1.001,0.5,np.nansum(c._ld_bb7(u,v,1.001,0.5))
            else:
                r=minimize(lambda p:-np.nansum(c._ld_bb7(u,v,max(p[0],1.001),max(p[1],0.01))),[max(self.ktau_to_gumbel(tau),1.001),max(self.ktau_to_clayton(tau),0.01)],bounds=[(1.001,10.0),(0.01,10.0)])
                c.theta,c.delta,ll=float(r.x[0]),float(r.x[1]),-r.fun
        c.family_fit,c.aic,c.fitted=family,2*self.N_PARAMS[family]-2*ll,True
        return c,c.aic

    def fit(self, u, v):
        tau,_=kendalltau(u,v)
        if np.isnan(tau): tau=0.0
        families=self.AUTO_FAMILIES if self.family=="auto" else [self.family]
        best,best_aic=None,np.inf
        for fam in families:
            try:
                c,aic=self._fit_single(fam,u,v,tau)
                if aic<best_aic: best_aic,best=aic,c
            except Exception: continue
        if best is None: best,_=self._fit_single("gaussian",u,v,tau)
        self.__dict__.update(best.__dict__)
        return self
