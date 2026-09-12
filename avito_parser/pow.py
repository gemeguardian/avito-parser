"""
Avito Proof-of-Work (PoW) challenge solver.
Handles dynamic cryptographic challenges issued by Avito's firewall.
"""
import base64
import hashlib
import json
import logging
import re
import time
from typing import Optional, Tuple
import requests

logger = logging.getLogger(__name__)


class AvitoPoWSolver:
    """
    Automated solver for Avito's SHA-256 Proof-of-Work firewall challenge.
    """

    @staticmethod
    def is_challenge_response(status_code: int, html_text: str) -> bool:
        """
        Check if response indicates a firewall PoW challenge.
        """
        if status_code == 439:
            return True
        if "firewallPow" in html_text or "firewall-status" in html_text:
            return True
        if "Доступ ограничен: проверка безопасности" in html_text:
            return True
        return False

    @staticmethod
    def extract_challenge_cookie(session: requests.Session, html_text: str = "") -> Optional[str]:
        """
        Extract the pow_challenge token from session cookies or HTML.
        """
        cookie = session.cookies.get("pow_challenge")
        if cookie:
            return cookie
        # Fallback to searching in HTML
        m = re.search(r'pow_challenge=([^;\"\'\s]+)', html_text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def solve_hash(challenge_id: str, complexity: int, max_iterations: int = 50_000_000) -> Tuple[int, float]:
        """
        Brute-force the nonce integer satisfying:
        sha256(f"{challenge_id}:{nonce}").startswith("0" * complexity)
        """
        prefix = "0" * complexity
        id_bytes = challenge_id.encode("utf-8")
        start_time = time.perf_counter()
        
        nonce = 0
        while nonce < max_iterations:
            data = id_bytes + b":" + str(nonce).encode("ascii")
            h = hashlib.sha256(data).hexdigest()
            if h.startswith(prefix):
                elapsed = time.perf_counter() - start_time
                return nonce, elapsed
            nonce += 1

        raise RuntimeError(f"PoW could not be solved within {max_iterations} iterations.")

    @classmethod
    def solve(
        cls,
        session: requests.Session,
        html_text: str = "",
        base_url: str = "https://www.avito.ru",
        timeout: float = 10.0
    ) -> bool:
        """
        Perform the full PoW verification cycle:
        1. Extract challenge token
        2. Request JWT from /web/3/firewallPow/get
        3. Parse ID and complexity
        4. Solve nonce
        5. Verify solution via /web/3/firewallPow/verify
        6. Set 'pow_solved' cookie
        """
        challenge_token = cls.extract_challenge_cookie(session, html_text)
        if not challenge_token:
            logger.warning("PoW challenge token not found in cookies or response HTML.")
            return False

        get_url = f"{base_url.rstrip('/')}/web/3/firewallPow/get"
        verify_url = f"{base_url.rstrip('/')}/web/3/firewallPow/verify"

        try:
            get_resp = session.post(
                get_url,
                json={"challenge": challenge_token},
                timeout=timeout
            )
            if get_resp.status_code != 200:
                logger.error("Failed to get challenge JWT: HTTP %s (%s)", get_resp.status_code, get_resp.text[:100])
                return False

            get_data = get_resp.json()
            jwt_token = get_data.get("success", {}).get("result", {}).get("challenge_jwt")
            if not jwt_token:
                logger.error("challenge_jwt missing from get response: %s", get_data)
                return False

            # Parse JWT payload without external libraries
            parts = jwt_token.split(".")
            if len(parts) < 2:
                logger.error("Invalid JWT format: %s", jwt_token)
                return False

            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            challenge_id = payload.get("id")
            complexity = payload.get("compl", 4)

            logger.info("Solving PoW: id=%s, complexity=%s...", challenge_id, complexity)
            nonce, elapsed = cls.solve_hash(challenge_id, complexity)
            logger.info("PoW solved in %.3f sec (nonce=%s)", elapsed, nonce)

            verify_resp = session.post(
                verify_url,
                json={"challenge": jwt_token, "nonce": nonce},
                timeout=timeout
            )
            if verify_resp.status_code != 200:
                logger.error("PoW verification request failed: HTTP %s", verify_resp.status_code)
                return False

            verify_data = verify_resp.json()
            success = verify_data.get("success", {}).get("result", {}).get("verified", False)
            if success:
                session.cookies.set("pow_solved", "1", domain=".avito.ru")
                logger.info("PoW verified successfully! Cookie pow_solved=1 set.")
                return True
            else:
                logger.warning("PoW verification returned unsuccessful: %s", verify_data)
                return False

        except Exception as e:
            logger.exception("Error during PoW challenge resolution: %s", e)
            return False
