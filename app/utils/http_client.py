# app/utils/http_client.py
from __future__ import annotations
import asyncio, time
from typing import Any, Mapping, Literal
import httpx

Method = Literal["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"]
Parse = Literal["json","text","bytes","response"]
RETRY_STATUSES = (429, 500, 502, 503, 504)

def _build_headers(headers: Mapping[str,str] | None, bearer: str | None) -> dict[str,str]:
    out = dict(headers or {})
    if bearer:
        out.setdefault("Authorization", f"Bearer {bearer}")
    return out

def _full_url(base_url: str | None, path_or_url: str) -> str:
    if base_url and not path_or_url.startswith(("http://","https://")):
        return f"{base_url.rstrip('/')}/{path_or_url.lstrip('/')}"
    return path_or_url

def _parse(resp: httpx.Response, parse: Parse):
    if parse == "response":
        return resp
    if parse == "json":
        return resp.json()
    if parse == "text":
        return resp.text
    if parse == "bytes":
        return resp.content
    return resp

# ----------------- S Y N C -----------------
class SyncHTTP:
    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0,
                 retries: int = 2, backoff: float = 0.5, follow_redirects: bool = True):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.follow_redirects = follow_redirects
        self._client: httpx.Client | None = None

    def __enter__(self):
        self._client = httpx.Client(timeout=self.timeout, follow_redirects=self.follow_redirects)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._client:
            self._client.close()

    def request(self, method: Method, path_or_url: str, *,
                headers: Mapping[str,str] | None = None,
                params: Mapping[str, Any] | None = None,
                json: Any | None = None, data: Any | None = None,
                bearer: str | None = None, parse: Parse = "json",
                raise_on_4xx_5xx: bool = True) -> Any:
        if json is not None and data is not None:
            raise ValueError("Use 'json' or 'data', not both.")
        if self._client is None:
            # quick usage without context manager
            with self as s:
                return s.request(method, path_or_url, headers=headers, params=params,
                                 json=json, data=data, bearer=bearer,
                                 parse=parse, raise_on_4xx_5xx=raise_on_4xx_5xx)

        url = _full_url(self.base_url, path_or_url)
        hdrs = _build_headers(headers, bearer)

        for attempt in range(self.retries + 1):
            try:
                r = self._client.request(method, url, headers=hdrs, params=params, json=json, data=data)
                if raise_on_4xx_5xx:
                    r.raise_for_status()
                return _parse(r, parse)
            except httpx.HTTPStatusError as e:
                if attempt < self.retries and e.response.status_code in RETRY_STATUSES:
                    time.sleep(self.backoff * (2 ** attempt)); continue
                raise
            except httpx.RequestError:
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt)); continue
                raise

    def get(self, u, **kw):     return self.request("GET", u, **kw)
    def post(self, u, **kw):    return self.request("POST", u, **kw)
    def put(self, u, **kw):     return self.request("PUT", u, **kw)
    def patch(self, u, **kw):   return self.request("PATCH", u, **kw)
    def delete(self, u, **kw):  return self.request("DELETE", u, **kw)
    def options(self, u, **kw): return self.request("OPTIONS", u, **kw)
    def head(self, u, **kw):    return self.request("HEAD", u, **kw)

# ----------------- A S Y N C -----------------
class AsyncHTTP:
    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0,
                 retries: int = 2, backoff: float = 0.5, follow_redirects: bool = True):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.follow_redirects = follow_redirects
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=self.follow_redirects)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            await self._client.aclose()

    async def request(self, method: Method, path_or_url: str, *,
                      headers: Mapping[str,str] | None = None,
                      params: Mapping[str, Any] | None = None,
                      json: Any | None = None, data: Any | None = None,
                      bearer: str | None = None, parse: Parse = "json",
                      raise_on_4xx_5xx: bool = True) -> Any:
        if json is not None and data is not None:
            raise ValueError("Use 'json' or 'data', not both.")
        if self._client is None:
            async with self as s:
                return await s.request(method, path_or_url, headers=headers, params=params,
                                       json=json, data=data, bearer=bearer,
                                       parse=parse, raise_on_4xx_5xx=raise_on_4xx_5xx)

        url = _full_url(self.base_url, path_or_url)
        hdrs = _build_headers(headers, bearer)

        for attempt in range(self.retries + 1):
            try:
                r = await self._client.request(method, url, headers=hdrs, params=params, json=json, data=data)
                if raise_on_4xx_5xx:
                    r.raise_for_status()
                return _parse(r, parse)
            except httpx.HTTPStatusError as e:
                if attempt < self.retries and e.response.status_code in RETRY_STATUSES:
                    await asyncio.sleep(self.backoff * (2 ** attempt)); continue
                raise
            except (httpx.RequestError, asyncio.TimeoutError):
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (2 ** attempt)); continue
                raise

    async def get(self, u, **kw):     return await self.request("GET", u, **kw)
    async def post(self, u, **kw):    return await self.request("POST", u, **kw)
    async def put(self, u, **kw):     return await self.request("PUT", u, **kw)
    async def patch(self, u, **kw):   return await self.request("PATCH", u, **kw)
    async def delete(self, u, **kw):  return await self.request("DELETE", u, **kw)
    async def options(self, u, **kw): return await self.request("OPTIONS", u, **kw)
    async def head(self, u, **kw):    return await self.request("HEAD", u, **kw)
