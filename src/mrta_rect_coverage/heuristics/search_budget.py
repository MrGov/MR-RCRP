"""Shared deadline signal for bounded structural ALNS actions."""


class SearchBudgetExhausted(RuntimeError):
    def __init__(self, phase, *, detail=''):
        self.phase = phase
        self.detail = detail
        super().__init__(f'structural search budget exhausted at {phase}: {detail}')
