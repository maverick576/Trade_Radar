"""Network resilience utilities providing secure DNS resolution and DoH fallback."""

import asyncio
import socket
import ssl
import time
from typing import Any

import httpx

from traderadar.core.logging import get_logger

logger = get_logger("traderadar.network")

_DNS_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300.0  # 5 minutes

# Known poisoned/blocking IPs from Indonesian/local ISPs
_POISONED_IPS = {
    "202.3.218.137",  # Telkomsel Internet Positif
    "118.98.44.100",  # Telkom Internet Positif
    "127.0.0.1",
    "0.0.0.0",
}


def resolve_host_sync(hostname: str) -> str:
    """Resolve hostname using system DNS, falling back to DoH (1.1.1.1) if poisoned."""
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, expire_at = _DNS_CACHE[hostname]
        if now < expire_at:
            return ip

    # Try standard system resolution first
    try:
        ip = socket.gethostbyname(hostname)
        if ip not in _POISONED_IPS:
            _DNS_CACHE[hostname] = (ip, now + _CACHE_TTL)
            return ip
        logger.warning("dns_poisoning_detected", host=hostname, poisoned_ip=ip)
    except Exception as exc:
        logger.debug("system_dns_failed", host=hostname, error=str(exc))

    # DoH Fallback via Cloudflare 1.1.1.1
    for doh_url in [
        f"https://1.1.1.1/dns-query?name={hostname}&type=A",
        f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A",
    ]:
        try:
            with httpx.Client(timeout=3.0, verify=False) as client:
                resp = client.get(doh_url, headers={"accept": "application/dns-json"})
                if resp.status_code == 200:
                    data = resp.json()
                    answers = data.get("Answer", [])
                    for ans in answers:
                        if ans.get("type") == 1:  # Type A
                            resolved = str(ans.get("data"))
                            _DNS_CACHE[hostname] = (resolved, now + _CACHE_TTL)
                            logger.info("doh_resolved", host=hostname, ip=resolved)
                            return resolved
        except Exception as doh_err:
            logger.debug("doh_query_failed", url=doh_url, error=str(doh_err))

    return hostname


async def resolve_host(hostname: str) -> str:
    """Asynchronously resolve hostname."""
    return await asyncio.to_thread(resolve_host_sync, hostname)


_ORIG_GETADDRINFO = socket.getaddrinfo


def enable_dns_fallback_patch() -> None:
    """Monkeypatch socket.getaddrinfo to intercept and fix poisoned Binance domains."""

    def patched_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(host, str) and ("binance" in host or "alternative.me" in host):
            resolved = resolve_host_sync(host)
            return _ORIG_GETADDRINFO(resolved, port, *args, **kwargs)
        return _ORIG_GETADDRINFO(host, port, *args, **kwargs)

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("dns_fallback_patch_enabled")


def create_ssl_context() -> ssl.SSLContext:
    """Create a permissive SSL context for websockets when connecting behind proxies."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
