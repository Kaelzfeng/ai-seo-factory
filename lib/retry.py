"""共享重试 / 退避助手。LLM 调用与 WordPress 调用都走它。

call_with_retry(fn, *, should_retry=None, on_retry=None,
                attempts=4, base_delay=1.0, max_delay=30.0,
                jitter=0.25, retry_on=(ConnectionError, OSError))

运行 fn()；遇到可重试异常时做指数退避 + 抖动后重试。
- should_retry(exc) 为 True 才重试；未提供则回退 isinstance(exc, retry_on)。
- 若异常带 .retry_after 属性，sleep 不小于它（尊重服务端 Retry-After）。
- 每次 sleep 前调用 on_retry(n, exc, sleep)（n 从 1 起计）。
- 重试 attempts 次仍失败则抛出最后一个异常。

签名同时满足 run.py(用 fn/should_retry/on_retry/attempts) 与
lib/wp_publish.py(用 attempts/base_delay/max_delay/jitter/retry_on/should_retry/on_retry)。
"""
import random
import time

DEFAULT_RETRY_ON = (ConnectionError, OSError)


def call_with_retry(fn, *, should_retry=None, on_retry=None,
                    attempts=4, base_delay=1.0, max_delay=30.0,
                    jitter=0.25, retry_on=DEFAULT_RETRY_ON):
    last = None
    for n in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 是否重试由 should_retry/retry_on 决定
            last = exc
            ok = should_retry(exc) if should_retry else isinstance(exc, retry_on)
            if not ok or n >= attempts:
                raise
            sleep = min(max_delay, base_delay * (2 ** (n - 1)))
            if jitter:
                sleep += sleep * jitter * (random.random() * 2 - 1)
            sleep = max(0.0, sleep)
            # 异常若携带 Retry-After，优先尊重它
            retry_after = getattr(exc, "retry_after", None)
            if retry_after is not None:
                try:
                    sleep = max(sleep, float(retry_after))
                except (TypeError, ValueError):
                    pass
            if on_retry:
                on_retry(n, exc, sleep)
            time.sleep(sleep)
    if last is not None:
        raise last
