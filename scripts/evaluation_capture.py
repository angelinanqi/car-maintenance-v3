"""Evaluation-only instrumentation; active only inside an isolated serial runner.

Wrap existing functions without changing their inputs, results or model behaviour.
The patch is process-wide: do not install it in the running application server.
"""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from pathlib import Path
from threading import local
from time import perf_counter
from unittest.mock import patch


def snapshot(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return deepcopy(asdict(value) if is_dataclass(value) else value)


def record_snapshot(record):
    return {"chunk_id": record.chunk_id, "rank": record.rank,
            "text": record.text, "metadata": snapshot(record.metadata)}


class EvaluationCapture:
    def __init__(self, query_module, grounded_module, provider_class, *, asset_dir):
        self.query = query_module
        self.grounded = grounded_module
        self.provider = provider_class
        self.asset_dir = Path(asset_dir)
        self.calls = []
        self.attempts = []
        self.intent = None
        self.generation_result = None
        self.selected_attempt_id = None
        self._local = local()
        self._stack = ExitStack()
        self._results = {}

    def __enter__(self):
        original_generate = self.grounded.generate
        if self.query.generate is not original_generate:
            raise RuntimeError("Query generation alias changed; update evaluation instrumentation")
        original_prepare = self.grounded.prepare_context
        original_call = self.provider.generate
        original_interpret = self.query.interpret

        def interpret(*args, **kwargs):
            result = original_interpret(*args, **kwargs)
            self.intent = snapshot(result)
            return result

        def prepare(*args, **kwargs):
            result = original_prepare(*args, **kwargs)
            attempt = getattr(self._local, "attempt", None)
            if attempt is not None:
                attempt["packed_context"] = snapshot(result)
            return result

        def generate(question, records, client, **kwargs):
            parent = getattr(self._local, "attempt", None)
            attempt = {"id": len(self.attempts) + 1,
                       "parent_id": parent["id"] if parent else None,
                       "question": question,
                       "input_records": [record_snapshot(r) for r in records],
                       "validation_feedback": snapshot(kwargs.get("_validation_feedback")),
                       "call_ids": []}
            self.attempts.append(attempt)
            self._local.attempt = attempt
            try:
                result = original_generate(question, records, client, **kwargs)
                attempt["result"] = snapshot(result)
                # A parent may return the exact reply object from a correction.
                # Retain the object so Python cannot reuse its id for a later reply.
                _, origin = self._results.setdefault(id(result), (result, attempt["id"]))
                attempt["returned_attempt_id"] = origin
                if parent is None:
                    self.generation_result = snapshot(result)
                    self.selected_attempt_id = origin
                return result
            except Exception as error:
                attempt["error_type"] = type(error).__name__
                raise
            finally:
                self._local.attempt = parent

        def call(client, prompt, **kwargs):
            attempt = getattr(self._local, "attempt", None)
            event = {"id": len(self.calls) + 1,
                     "stage": "answer_generation" if attempt else "intent_analysis",
                     "attempt_id": attempt["id"] if attempt else None,
                     "prompt": prompt, "schema": snapshot(kwargs.get("schema")),
                     "images": []}
            for item in kwargs.get("images") or []:
                digest = sha256(item.data).hexdigest()
                self.asset_dir.mkdir(parents=True, exist_ok=True)
                path = self.asset_dir / digest
                if path.exists() and sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError("Captured image hash mismatch")
                if not path.exists():
                    path.write_bytes(item.data)
                event["images"].append({"label": item.label, "mime_type": item.mime_type,
                                        "sha256": digest, "asset_path": str(path)})
            self.calls.append(event)
            if attempt is not None:
                attempt["call_ids"].append(event["id"])
            started = perf_counter()
            try:
                result = original_call(client, prompt, **kwargs)
                event["response"] = result
                return result
            except Exception as error:
                event["error_type"] = type(error).__name__
                raise
            finally:
                event["provider"] = client.provider
                event["model"] = client.model
                event["elapsed_seconds"] = round(perf_counter() - started, 4)

        try:
            for target, name, replacement in (
                (self.query, "interpret", interpret),
                (self.query, "generate", generate),
                (self.grounded, "generate", generate),
                (self.grounded, "prepare_context", prepare),
                (self.provider, "generate", call),
            ):
                self._stack.enter_context(patch.object(target, name, replacement))
        except BaseException:
            self._stack.close()
            raise
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)

    def artifact(self):
        return {"intent": self.intent, "generation_attempts": self.attempts,
                "selected_attempt_id": self.selected_attempt_id,
                "generation_result": self.generation_result, "calls": self.calls}
