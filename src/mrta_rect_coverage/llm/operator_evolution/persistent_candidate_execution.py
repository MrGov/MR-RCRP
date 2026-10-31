"""Opt-in warm processes for frozen development operators (Proposed-vNext).

Reuses the original bounded worker, including hash/AST checks, fresh candidate
module, output bounds and DP counters on EVERY call. Arguments/results still
cross a process boundary. Timeout/error discards the worker. Trusted Python
imports remain warm; process lifetime isolation differs from the original
per-call process. This is timeout-only isolation, not an OS security sandbox.
Use only for the frozen, reviewed stateless E5/E7 operators.
"""
from __future__ import annotations

import multiprocessing
import sys
import warnings
from dataclasses import dataclass, field
from time import perf_counter

from .candidate_execution import CandidateProxy, CandidateExecutionResult, _candidate_worker, _terminate

IDENTITY = 'timeout_only_warm_process_vnext'


class _BorrowedConnection:
    def __init__(self, connection):
        self.connection = connection
    def send(self, value):
        self.connection.send(value)
    def recv(self):
        return self.connection.recv()
    def close(self):
        # The original worker closes its per-call view, not the host connection.
        pass


def _warm_worker(connection, path, operator_type, max_output_chars, expected_hash):
    from ...core.dp_evaluator import RouteDPEvaluator
    original_evaluate = RouteDPEvaluator.evaluate_route
    original_warning = warnings.showwarning
    module_name = f'isolated_operator_{__import__("pathlib").Path(path).stem}_{multiprocessing.current_process().pid}'
    try:
        connection.send(('host_ready', ''))
        while connection.recv() == 'call':
            try:
                _candidate_worker(_BorrowedConnection(connection), path, operator_type,
                                  max_output_chars, expected_hash)
            finally:
                # No candidate namespace or nested DP instrumentation survives.
                RouteDPEvaluator.evaluate_route = original_evaluate
                warnings.showwarning = original_warning
                sys.modules.pop(module_name, None)
    except (EOFError, OSError):
        pass
    finally:
        connection.close()


@dataclass
class PersistentCandidateProxy(CandidateProxy):
    _process: object = field(default=None, init=False, repr=False)
    _connection: object = field(default=None, init=False, repr=False)
    process_starts: int = field(default=0, init=False)

    @classmethod
    def from_validated(cls, proxy):
        return cls(proxy.path, proxy.operator_type, proxy.expected_code_hash,
                   proxy.timeout_ms, proxy.max_output_chars, proxy.import_timeout_s)

    def close(self):
        if self._process is not None:
            _terminate(self._process)
            self._process.join(timeout=.2)
            self._process.close()
            self._process = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, args, *, timeout_ms):
        wall = perf_counter()
        def outcome(status, *, runtime=0., message='', response=None):
            data = response or ()
            success = status == 'success'
            return CandidateExecutionResult(status=status, runtime_ms=runtime,
                result=data[1] if success else None, error_message=message,
                executor_identity=IDENTITY, wall_time_ms=(perf_counter()-wall)*1000,
                stdout=str(data[2]) if len(data)>2 else '', stderr=str(data[3]) if len(data)>3 else '',
                stdout_truncated=bool(data[4]) if len(data)>4 else False,
                stderr_truncated=bool(data[5]) if len(data)>5 else False,
                route_dp_calls=data[6].get('calls',0) if success and len(data)>6 else 0,
                route_dp_cache_misses=data[6].get('cache_misses',0) if success and len(data)>6 else 0)
        if not self.expected_code_hash:
            return outcome('source_hash_missing', message='Expected source hash required')
        try:
            if self._process is None or not self._process.is_alive():
                self.close()
                context = multiprocessing.get_context('spawn')
                self._connection, child = context.Pipe()
                self._process = context.Process(target=_warm_worker, args=(child,str(self.path),
                    self.operator_type,self.max_output_chars,self.expected_code_hash),daemon=True)
                self._process.start(); child.close(); self.process_starts += 1
                if not self._connection.poll(self.import_timeout_s):
                    self.close()
                    return outcome('timeout', message='Candidate host import timed out')
                if self._connection.recv()[0] != 'host_ready':
                    raise RuntimeError('Unexpected host handshake')
            self._connection.send('call')
            if not self._connection.poll(self.import_timeout_s):
                self.close()
                return outcome('timeout', message='Candidate import timed out')
            ready = self._connection.recv()
            if ready[0] != 'ready':
                self.close()
                return outcome(str(ready[0]), message=str(ready[1]), response=ready)
            started = perf_counter()
            self._connection.send(('run',tuple(args)))
            if not self._connection.poll(max(0.,timeout_ms/1000)):
                self.close()
                return outcome('timeout', runtime=(perf_counter()-started)*1000,
                               message=f'Candidate exceeded {timeout_ms:g} ms timeout')
            response = self._connection.recv()
            runtime = (perf_counter()-started)*1000
            if response[0] != 'success':
                self.close()
                return outcome('runtime_error',runtime=runtime,message=str(response[1]),response=response)
            return outcome('success', runtime=runtime, response=response)
        except (EOFError, OSError, RuntimeError) as exc:
            self.close()
            return outcome('runtime_error',message=f'Candidate process communication failed: {exc}')
