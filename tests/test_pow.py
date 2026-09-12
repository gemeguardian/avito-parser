"""
Unit tests for Proof-of-Work solver.
"""
import hashlib
import pytest
from avito_parser.pow import AvitoPoWSolver


def test_pow_solve_hash():
    challenge_id = "test-challenge-12345"
    complexity = 3

    nonce, elapsed = AvitoPoWSolver.solve_hash(challenge_id, complexity)
    assert isinstance(nonce, int)
    assert nonce >= 0
    assert elapsed >= 0

    # Verify solution
    h = hashlib.sha256(f"{challenge_id}:{nonce}".encode("ascii")).hexdigest()
    assert h.startswith("000")


def test_pow_solve_hash_higher_complexity():
    challenge_id = "9dd849d4-039e-cc48-db7c-faa497d0f96d"
    complexity = 4

    nonce, elapsed = AvitoPoWSolver.solve_hash(challenge_id, complexity)
    h = hashlib.sha256(f"{challenge_id}:{nonce}".encode("ascii")).hexdigest()
    assert h.startswith("0000")


def test_is_challenge_response():
    assert AvitoPoWSolver.is_challenge_response(439, "anything") is True
    assert AvitoPoWSolver.is_challenge_response(200, "<html>firewallPow/get</html>") is True
    assert AvitoPoWSolver.is_challenge_response(200, "Доступ ограничен: проверка безопасности") is True
    assert AvitoPoWSolver.is_challenge_response(200, "<html><title>Normal Page</title></html>") is False
