import numpy as np
import scipy.optimize as opt
import scipy.stats as stats

def sigmoid(x):
    e = np.exp(x)
    e = e/(1 + np.sum(e, axis=1, keepdims=True))
    return e

class Zipcode(object):
    def __init__(self, tri, pop):
        self.tri = tri
        self.pop = pop

class Market(object):
    def __init__(self, zipcodes):
        self.zipcodes = zipcodes
        self.n = len(zipcodes)
        self.pop = sum([z.pop for z in zipcodes])
        self.zipvec = {'tri':np.array([z.tri for z in zipcodes]).reshape((-1,1)),
                      'pop':np.array([z.pop for z in zipcodes]).reshape((-1,1))}
    
class Markets(object):
    def __init__(self, markets_list):
        self.markets_list = markets_list
        self.n = len(markets_list)
        self.pop = np.array([m.pop for m in markets_list]).reshape((-1,1))
        
class Cost(object):
    def __init__(self, static_pars, dynamic_pars):
        self.static_pars = static_pars
        self.mc_static0 = self.mc_static(0)
        self.J = static_pars['static_mc'].shape[1]
        self.dynamic_pars = dynamic_pars
        
    def mc_static(self, Q):
        MC = self.static_pars['static_mc']
        return MC
    
    def evaluate_dynamic_base(self, market):
        C = np.zeros((market.n, self.J))
        pars = self.dynamic_pars
        C = pars['alpha_0']*market.zipvec['tri']**pars['alpha_tri']* \
                market.zipvec['pop']**pars['alpha_pop']
        return C
    
    def u2p(self, u):
        sigma = self.dynamic_pars['sigma']
        u = np.maximum(u, 1e-4)
        u = (np.log(u)+sigma**2)/sigma
        p = stats.norm.cdf(u)
        return p
    
    def p2u(self, p):
        p = np.maximum(p, 1e-4)
        u = stats.norm.ppf(p)
        u = stats.norm.cdf(u - self.dynamic_pars['sigma'])/p
        return u
    
    def evaluate_static(self, Q):
        C = self.static_pars['static_mc']*Q
        return C
        
class Costs(object):
    def __init__(self, costs_list):
        self.T = len(costs_list)
        self.costs_list = costs_list
        self.J = costs_list[0].J
        
class Demand(object):
    def __init__(self, alpha, beta, xi, delta_q = 0.2):
        self.alpha = alpha
        self.beta = beta
        self.xi = xi
        self.delta_q = delta_q
        
    def combine(self, p, q):
        z = self.xi-self.alpha*p+self.beta*q + (self.beta-self.delta_q)*(1-q)
        return z
        
    def evaluate(self, p, q, markets):
        z = self.combine(p, q)
        Q = np.sum(sigmoid(z)*markets.pop, axis=0, keepdims=True)
        return Q
    
    def elastisity(self, p, q, markets): # Negative
        z = self.combine(p, q)
        s = sigmoid(z)
        Q = np.sum(sigmoid(z)*markets.pop, axis=0, keepdims=True)
        dQdp = -self.alpha*np.sum(s*(1-s)*markets.pop, axis=0, keepdims=True)
        e = dQdp*p/Q
        return e
    
    def evaluate2(self, p, q, markets): 
        z = self.combine(p, q)
        s = sigmoid(z)
        Q = np.sum(sigmoid(z)*markets.pop, axis=0, keepdims=True)
        dQdp = -self.alpha*np.sum(s*(1-s)*markets.pop, axis=0, keepdims=True)
        e = dQdp*p/Q
        return Q, e
    
    def inv_boost(self, p, q, markets):
        M = markets.n
        z = self.combine(p, q)
        s = sigmoid(z)
        ds = s*(1-s)*self.delta_q
        dQ = []
        for m in range(M):
            market = markets.markets_list[m]
            dQm = market.zipvec['pop']*ds[[m],:]
            dQ.append(dQm)
        return dQ
    
    def shares_by_market(self, p, q):
        z = self.combine(p, q)
        return sigmoid(z)
    
    def utility2money(self, u):
        return u/self.alpha
    
    
class Demands(object):
    def __init__(self, demands_list):
        self.T = len(demands_list)
        self.demands_list = demands_list
        
    def evaluate(self, p, q, markets):
        out = []
        for t in range(self.T):
            demand = self.demands_list[t]
            e = demand.evaluate(p[t], q[t], markets)
            out.append(e)
        return out
    
    def combine(self, p, q):
        out = []
        for t in range(self.T):
            demand = self.demands_list[t]
            z = demand.combine(p[t], q[t])
            out.append(z)
        return out
    
    def shares_by_market(self, p, q):
        out = []
        for t in range(self.T):
            demand = self.demands_list[t]
            s = demand.shares_by_market(p[t], q[t])
            out.append(s)
        return out
    
class Model(object):
    def __init__(self, markets, demands, costs, q_init, delta=0.92):
        self.markets = markets
        self.costs = costs
        self.demands = demands
        self.T = min([self.demands.T, self.costs.T])
        self.J = self.costs.J
        self.M = self.markets.n
        self.q = q_init
        self.p = self.eqm_prices()
        self.delta = delta
        self.sigma = self.initialize_sigma()
        
    def initialize_sigma(self):
        sigma = []
        M = self.M
        T = self.T
        J = self.J
        for t in range(T):
            sigma_t = []
            for m in range(M):
                Zm = self.markets.markets_list[m].n
                sigma_t.append(np.zeros((Zm, J)))
            sigma.append(sigma_t)
        return sigma
    
    def eqm_price(self, t):
        q = self.q[t]
        demand = self.demands.demands_list[t]
        cost = self.costs.costs_list[t]
        def eq(p):
            p = p.reshape(1,-1)
            Q, e = demand.evaluate2(p, q, self.markets)
            c = cost.mc_static(Q)
            out = e*(p-c)/p + 1
            return out.reshape(-1,) 
        price = opt.fsolve(eq, cost.mc_static0.reshape(-1,))
        return price.reshape(1,-1)
        
    def eqm_prices(self):
        T = self.T
        prices = []
        for t in range(T):
            price = self.eqm_price(t)
            prices.append(price)
        return prices
    
    def update_q(self, learning_rate=1): 
        T = self.T
        M = self.M
        pr_cum = self.calc_probs_eq()
        for t in range(1, T):
            demand = self.demands.demands_list[t]
            for m in range(M):
                market = self.markets.markets_list[m]
                dq = np.sum(pr_cum[t][m]*market.zipvec['pop'], axis=0, keepdims=True)/market.pop
                temp = self.q[0][[m],:] + dq
                self.q[t][[m],:] = (1-learning_rate)*self.q[t][[m],:] + learning_rate*temp
    
    def tr1(self, t, demand_boosts, mcs):
        delta = self.delta
        out = []
        T = self.T
        for m in range(self.M):
            market = self.markets.markets_list[m]
            Zm = market.n
            J = self.costs.J
            tr = np.zeros((Zm, J))
            for tau in range(1,T-t):
                price = self.p[t+tau]
                mc = mcs[t+tau]
                boost = demand_boosts[t+tau][m]
                tr += delta**tau*boost*(price - mc)
            out.append(tr)
        return out
    
    def tr0(self, t, demand_boosts, mcs, prob_inv_cum):
        delta = self.delta
        out = []
        T = self.T
        for m in range(self.M):
            market = self.markets.markets_list[m]
            Zm = market.n
            J = self.costs.J
            tr = np.zeros((Zm, J))
            for tau in range(1,T-t):
                price = self.p[t+tau]
                mc = mcs[t+tau]
                demand_boost = demand_boosts[t+tau][m]
                prob_inv_cum_iter = prob_inv_cum[t][tau][m]
                tr += delta**tau*demand_boost*(price - mc)*prob_inv_cum_iter
            out.append(tr)
        return out
    
    def tc0(self, t, prob_inv_cum):
        delta = self.delta
        out = []
        T = self.T     
        for m in range(self.M):
            market = self.markets.markets_list[m]
            Zm = market.n
            J = self.J
            tc = np.zeros((Zm, J))
            for tau in range(1,T-t-1):
                cost = self.costs.costs_list[t+tau]
                tc_base = cost.evaluate_dynamic_base(market)
                prob_inv_marg = self.sigma[t+tau][m]
                dprob_inv_cum = prob_inv_cum[t][tau+1][m] - prob_inv_cum[t][tau][m]
                u = self.costs.costs_list[t+tau].p2u(prob_inv_marg)
                tc += delta**tau*u*tc_base*dprob_inv_cum
            out.append(tc)
        return out
    
    def br_inv(self, t, demand_boosts, mcs, prob_inv_cum):
        tr1 = self.tr1(t, demand_boosts, mcs)
        tr0 = self.tr0(t, demand_boosts, mcs, prob_inv_cum)
        tc0 = self.tc0(t, prob_inv_cum)
        sigma_opt = []
        for m in range(self.M):
            market = self.markets.markets_list[m]
            costs = self.costs.costs_list[t]
            tc1 = costs.evaluate_dynamic_base(market)
            u = (tr1[m] - tr0[m] + tc0[m])/tc1[m]
            br = costs.u2p(u)
            sigma_opt.append(br)
        return sigma_opt
    
    def inv_forward_effect(self, t):
        cost = self.costs.costs_list[t]
        demand = self.demands.demands_list[t]
        p = self.p[t]
        q = self.q[t]
        boost = demand.inv_boost(p, q, self.markets)
        Q = demand.evaluate(p, q, self.markets)
        mc = cost.mc_static(Q)
        return boost, mc
    
    def calc_probs0(self):
        sigma = self.sigma
        prob_inv_cum = []
        T = self.T
        M = self.M
        J = self.J
        for t in range(T):
            prob_inv_cum_iter = [None for a in range(T-t)]
            if T-t>1:
                prob_inv_cum_iter[1] = []
                for m in range(M):
                    market = self.markets.markets_list[m]
                    Zm = market.n
                    prob_inv_cum_iter[1].append(np.zeros((Zm,J)))
            for tau in range(2,T-t):
                prob_inv_cum_iter[tau] = []
                for m in range(M):
                    market = self.markets.markets_list[m]
                    Zm = market.n
                    temp = prob_inv_cum_iter[tau-1][m] + \
                            (1 - prob_inv_cum_iter[tau-1][m])*self.sigma[t+tau-1][m]
                    prob_inv_cum_iter[tau].append(temp)
            prob_inv_cum.append(prob_inv_cum_iter)
        return prob_inv_cum
    
    def calc_probs_eq(self):
        sigma = self.sigma
        T = self.T
        M = self.M
        J = self.J
        prob_inv_cum = [None for a in range(T)]
        prob_inv_cum[0] = []
        for m in range(M):
            market = self.markets.markets_list[m]
            Zm = market.n
            prob_inv_cum[0].append(np.zeros((Zm,J)))
        for tau in range(1,T):
            prob_inv_cum[tau] = []
            for m in range(M):
                market = self.markets.markets_list[m]
                Zm = market.n
                temp = prob_inv_cum[tau-1][m] + \
                        (1 - prob_inv_cum[tau-1][m])*self.sigma[tau-1][m]
                prob_inv_cum[tau].append(temp)    
        for t in range(T):
            prob_inv_cum_iter = [None for a in range(T-t)]
            if T-t>1:
                prob_inv_cum_iter[1] = []
                for m in range(M):
                    market = self.markets.markets_list[m]
                    Zm = market.n
                    prob_inv_cum_iter[1].append(self.sigma[t][m])
            for tau in range(2,T-t):
                prob_inv_cum_iter[tau] = []
                for m in range(M):
                    market = self.markets.markets_list[m]
                    Zm = market.n
                    temp = prob_inv_cum_iter[tau-1][m] + \
                            (1 - prob_inv_cum_iter[tau-1][m])*self.sigma[t+tau-1][m]
                    prob_inv_cum_iter[tau].append(temp)
            prob_inv_cum.append(prob_inv_cum_iter)
        return prob_inv_cum
    
    def brs_inv(self):
        T = self.T
        sigma_out = []
        prob_inv_cum = self.calc_probs0()
        demand_boosts = []
        mcs = []
        for t in range(T):
            boost, mc = self.inv_forward_effect(t)
            demand_boosts.append(boost)
            mcs.append(mc)
        for t in range(T):
            br = self.br_inv(t, demand_boosts, mcs, prob_inv_cum)
            sigma_out.append(br)
        return sigma_out
    
    def find_eqm(self, tol=1e-4, verbose=False, learning_rate=1):
        dif = 2*tol
        while dif > tol:
            self.p = self.eqm_prices()
            sigma = self.brs_inv()
            dif = 0
            for t in range(self.T):
                for m in range(self.M):
                    d = np.max(np.abs(sigma[t][m] - self.sigma[t][m]))
                    dif = np.maximum(dif, d)
            self.sigma = sigma
            self.update_q(learning_rate=learning_rate)
            if verbose:
                print(dif)
                
    def consumer_surplus(self):
        out = []
        s = self.demands.shares_by_market(self.p, self.q)
        z = self.demands.combine(self.p, self.q)
        for t in range(self.T):
            u = np.log(1 + np.sum(np.exp(z[t]), axis=1, keepdims=True))
            u = self.demands.demand_list[t].utility2money(u)
            out.append(u)
        return out

    def static_profits(self):
        out = []
        s = self.demands.shares_by_market(self.p, self.q)
        for t in range(self.T):
            cost = self.costs.costs_list[t]
            pi = self.p[t]*s[t]*self.markets.pop - cost.evaluate_static(s[t]*self.markets.pop)
            out.append(pi)
        return out

    def average_price(self):
        p = np.zeros((self.T,))
        Q = self.demands.evaluate(self.p, self.q, self.markets)
        for t in range(self.T):
            s = Q[t]/np.sum(Q[t])
            p[t] = np.sum(self.p[t]*s)
        return p

    def average_quality(self):
        q = np.zeros((self.T,))
        s = self.demands.shares_by_market(self.p, self.q)
        for t in range(self.T):
            Q = s[t]*self.markets.pop
            q[t] = np.sum(self.q[t]*Q)/np.sum(Q)
        return q

    def mobile_penetration(self):
        out = np.zeros((self.T,))
        Q = self.demands.evaluate(self.p, self.q, self.markets)
        for t in range(self.T):
            out[t] = np.sum(Q[t])/np.sum(self.markets.pop)
        return out

    def dynamic_costs(self):
        out = []
        for t in range(self.T):
            temp = np.zeros((self.M,self.J))
            sigma = self.sigma[t]
            cost = self.costs.costs_list[t]
            for m in range(self.M):
                market = self.markets.markets_list[m]
                u = cost.p2u(sigma[m])
                C = cost.evaluate_dynamic_base(market)
                temp[[m],:] = np.sum(u*C, axis=0, keepdims=True)
            out.append(temp)
        return out