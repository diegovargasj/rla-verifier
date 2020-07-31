from decimal import Decimal

import utils


class Audit:
    """
    Audit class that defines the common objects and methods for running a BRAVO audit.
    """
    def __init__(self, risk_limit, audit_type, n_winners, preliminary, recount):
        self.required_headers = {'table', 'candidate', 'votes'}
        self.vote_count = {}
        self.risk_limit = Decimal(risk_limit)
        self.n_winners = n_winners
        self.audit_type = audit_type
        self.T = {} if self.is_ballot_polling() else 1.0
        self.Sw = None
        self.Sl = None
        self.candidates = []
        self.max_p_value = 1
        self.primary_column = 'candidate'

        self.preliminary = preliminary
        self.recount_df = recount

        if self.is_ballot_polling():
            self.audit = self._ballot_polling
            self.validate = utils.validate_ballot_polling

        else:
            self.audit = self._batch_comparison
            self.validate = utils.validate_batch_comparison

    def is_ballot_polling(self):
        return self.audit_type == utils.BALLOTPOLLING

    def is_batch_comparison(self):
        return self.audit_type == utils.COMPARISON

    def sanity_check(self):
        assert 0 < self.risk_limit < 1
        assert self.n_winners > 0
        assert set(self.preliminary.columns) >= self.required_headers

    def _update_accum_recount(self, accum_recount, recount):
        if self.is_ballot_polling():
            for candidate in recount:
                accum_recount[candidate] += recount[candidate]

        else:
            for table in recount:
                for candidate in recount[table]:
                    accum_recount[candidate] += recount[table][candidate]

        return accum_recount

    def _vote_count_transform(self, vote_count):
        return vote_count

    def _vote_recount_transform(self, recount):
        return recount

    def _ballot_polling(self, recount, T):
        transformed_count = self._vote_count_transform(self.vote_count)
        transformed_recount = self._vote_recount_transform(recount)
        return utils.ballot_polling_SPRT(transformed_count, transformed_recount, T, self.risk_limit, self.Sw, self.Sl)

    def _batch_comparison(self, recount, beta):
        transformed_vote_count = self._vote_count_transform(self.vote_count)
        W = [w for w in self.Sw]
        L = [l for l in self.Sl]
        u = utils.MICRO_upper_bound(transformed_vote_count, W, L, self.Sw, self.Sl)
        V = self.preliminary.groupby('table').sum()['votes'].max()
        um = u * V
        U = um * len(self.preliminary['table'].unique())
        for table in recount:
            table_df = self.preliminary[self.preliminary['table'] == table]
            table_report = table_df.groupby(self.primary_column).sum()['votes'].to_dict()
            transformed_table_report = self._vote_count_transform(table_report)
            transformed_recount = self._vote_recount_transform(recount[table]['votes'])
            beta *= utils.batch_comparison_SPRT(
                transformed_vote_count,
                transformed_table_report,
                transformed_recount,
                self.Sw,
                self.Sl,
                um,
                U
            ) ** recount[table]['n']

        return beta, 1 / beta

    def verify(self):
        if self.is_ballot_polling():
            recount = self.recount_df.groupby('candidate').sum()['votes'].to_dict()

        else:
            recount = {}
            for table in self.recount_df['table'].unique():
                recount[table] = {}
                n = self.recount_df.table.value_counts()[table] / len(self.candidates)
                table_df = self.recount_df[self.recount_df['table'] == table]
                votes_per_candidate = table_df.groupby('candidate').sum()['votes'] // n
                recount[table]['votes'] = votes_per_candidate.to_dict()
                recount[table]['n'] = n

        self.T, self.max_p_value = self.audit(recount, self.T)


class Plurality(Audit):
    """
    A plurality election chooses the n candidates with most votes.
    If n == 1, this becomes a simple majority election.
    """
    def __init__(self, risk_limit, audit_type, n_winners, preliminary, recount):
        super().__init__(risk_limit, audit_type, n_winners, preliminary, recount)
        self.vote_count = self.preliminary.groupby('candidate').sum()['votes'].to_dict()
        self.candidates = list(self.vote_count.keys())
        self.table_count = self.preliminary.groupby('table').sum()['votes'].to_dict()
        self.tables = list(self.table_count.keys())
        self.W, self.L = utils.get_W_L_sets(self.vote_count, self.n_winners)
        self.Sw = {w: 0 for w in self.W}
        self.Sl = {l: 0 for l in self.L}
        if self.is_ballot_polling():
            for winner in self.W:
                self.T[winner] = {}
                for loser in self.L:
                    self.T[winner][loser] = Decimal(1.0)


class SuperMajority(Plurality):
    """
    A super majority election chooses the candidate with most votes, if they
    amount to more than half the total.
    """
    def __init__(self, risk_limit, audit_type, preliminary, recount):
        super().__init__(risk_limit, audit_type, 1, preliminary, recount)
        self.Sw = {'w': 0}
        self.Sl = {'l': 0}
        self.T = {'w': {'l': Decimal(1.0)}} if self.is_ballot_polling() else 1.0

    def _vote_count_transform(self, vote_count):
        candidates = list(self.vote_count.keys())
        candidates = sorted(candidates, key=lambda c: self.vote_count[c], reverse=True)
        W = candidates[:self.n_winners]
        L = candidates[self.n_winners:]
        transformed = {
            'w': sum([vote_count[c] for c in W]),
            'l': sum([vote_count[c] for c in L])
        }
        return transformed

    def _vote_recount_transform(self, recount):
        return self._vote_count_transform(recount)


class DHondt(Audit):
    """
    A proportional method, in which the current party votes is divided by the
    number of seats assigned to them + 1.
    """
    def __init__(self, risk_limit, audit_type, n_winners, preliminary, recount):
        super().__init__(risk_limit, audit_type, n_winners, preliminary, recount)
        self.required_headers.add('party')
        self.preliminary['party'] = self.preliminary['party'].fillna('')
        self.vote_count = self.preliminary.groupby('party').sum()['votes'].to_dict()
        self.table_count = self.preliminary.groupby('table').sum()['votes'].to_dict()
        self.candidate_count = self.preliminary.groupby('candidate').sum()['votes'].to_dict()
        self.candidates = list(self.candidate_count.keys())
        self.parties = list(self.vote_count.keys())
        self.primary_column = 'party'
        self.party_members = {}
        members_per_party = {}
        for party in self.parties:
            p = self.preliminary[self.preliminary['party'] == party]
            candidates = p.sort_values('votes', ascending=False)['candidate'].unique()
            members_per_party[party] = list(candidates)
            for c in candidates:
                self.party_members[c] = party

        self.pseudo_vote_count = {
            (p, i): utils.p(p, self.vote_count, i) for p in self.parties if p
            for i in range(min(n_winners, len(members_per_party[p])))
        }

        self.W, self.L = utils.get_W_L_sets(self.pseudo_vote_count, n_winners)
        self.winning_candidates = []
        for party in self.parties:
            if any([p == party for p, i in self.W]):
                seats = max([i for p, i in self.W if p == party]) + 1
                self.winning_candidates.extend(members_per_party[party][:seats])

        self.Sw = {}
        self.Sl = {}
        for party in self.parties:
            wp = list(filter(lambda x: x[0] == party, self.W))
            lp = list(filter(lambda x: x[0] == party, self.L))
            if wp:
                self.Sw[party] = max(wp, key=lambda x: x[1])[1]

            if lp:
                self.Sl[party] = min(lp, key=lambda x: x[1])[1]

        self.Wp = []
        for winner in self.W:
            if winner[0] not in self.Wp:
                self.Wp.append(winner[0])

        self.Lp = []
        for loser in self.L:
            if loser[0] not in self.Lp:
                self.Lp.append(loser[0])

        if self.is_ballot_polling():
            for winner in self.Wp:
                self.T[winner] = {loser: Decimal(1) for loser in self.Lp if winner != loser}

        self.Tp = {}
        for p in self.Wp:
            seats = max([w[1] for w in self.W if w[0] == p]) + 1
            self.Tp[p] = Plurality(self.risk_limit, self.audit_type, seats,
                                   self.preliminary[self.preliminary['party'] == p], recount)

    def _vote_recount_transform(self, recount):
        transformed = {}
        for candidate in recount:
            party = self.party_members[candidate]
            if party not in transformed:
                transformed[party] = 0

            transformed[party] += recount[candidate]

        return transformed

    def verify(self):
        super().verify()
        for p in self.Tp:
            self.Tp[p].verify()

        max_p_value = max([self.Tp[p].max_p_value for p in self.Tp])
        self.max_p_value = max(self.max_p_value, max_p_value)
