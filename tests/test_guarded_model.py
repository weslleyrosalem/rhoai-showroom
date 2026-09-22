"""Safety-boundary tests for the private matched-evaluation adapter."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

spec = importlib.util.spec_from_file_location('guarded_model', Path(__file__).parents[1] / 'apps/aurora-guarded-model/server.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def body(text='Summarize Aurora stock policy.'):
    return {'model': 'reviewed-model', 'messages': [{'role': 'user', 'content': text}], 'temperature': 0, 'max_tokens': 128}


def test_rejects_unmatched_target_parameters_and_tools():
    for change in ({'model': 'another-model'}, {'stream': True}, {'max_tokens': 5000}, {'tools': []}, {'n': 2}, {'temperature': 1}):
        with pytest.raises(ValueError):
            app.validate(body() | change, 'reviewed-model')


def test_input_block_never_calls_model():
    with patch.object(app, 'check', return_value=False), patch.object(app, 'post') as call:
        result, verdict = app.evaluate(body(), 'reviewed-model', 'https://fixed.example/v1', 'synthetic-key')
        assert verdict == 'input-blocked'
        assert result['choices'][0]['message']['content'] == app.REFUSAL
        call.assert_not_called()


def test_output_block_replaces_sensitive_result():
    with patch.object(app, 'check', side_effect=[True, False]), patch.object(app, 'post', return_value=app.completion('reviewed-model', 'DEMO_SECRET_AURORA')):
        result, verdict = app.evaluate(body(), 'reviewed-model', 'https://fixed.example/v1', 'synthetic-key')
        assert verdict == 'output-blocked'
        assert 'DEMO_SECRET_AURORA' not in str(result)


def test_unavailable_guardrail_fails_closed_without_model_call():
    with patch.object(app, 'check', side_effect=OSError('unavailable')), patch.object(app, 'post') as call:
        with pytest.raises(OSError):
            app.evaluate(body(), 'reviewed-model', 'https://fixed.example/v1', 'synthetic-key')
        call.assert_not_called()


def test_messages_and_generation_parameters_preserved():
    request = body() | {'top_p': 1, 'stop': ['#', ';'], 'presence_penalty': 0, 'frequency_penalty': 0}
    with patch.object(app, 'check', return_value=True), patch.object(app, 'post', return_value=app.completion('reviewed-model', 'Synthetic policy summary.')) as call:
        _, verdict = app.evaluate(request, 'reviewed-model', 'https://fixed.example/v1', 'synthetic-key')
        assert verdict == 'allowed'
        assert call.call_args.args[1] == request | {'stream': False}
