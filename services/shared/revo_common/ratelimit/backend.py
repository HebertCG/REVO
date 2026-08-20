"""
backend.py — Contador de ventana deslizante sobre Redis.

Por que ventana deslizante y no un contador de ventana fija: con ventana
fija un alumno puede gastar el cupo entero al final de un minuto y otra vez
al principio del siguiente, doblando el pico real justo en el momento en que
toda el aula envia respuestas a la vez.

Coste por peticion: UNA ida y vuelta a Redis (pipeline MULTI/EXEC con cuatro
comandos). No se usa EVALSHA para no depender de que el Redis gestionado
permita cargar scripts.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Callable

from revo_common.ratelimit.policy import RateLimitPolicy, RequestContext, resolve_bucket

logger = logging.getLogger("revo.ratelimit")

# Cuando Redis no responde, cada worker cuenta por su cuenta. Como hay varios
# workers, el techo local se relaja por este factor para no bloquear a un aula
# legitima por un fallo de infraestructura; sigue frenando un flood real.
DEGRADED_BURST_FACTOR = 5

# Techo de buckets que el respaldo en memoria guarda a la vez. Sin este limite
# un atacante con IPs rotativas hace crecer el diccionario sin fin.
MEMORY_MAX_BUCKETS = 10_000


@dataclass(frozen=True)
class RateLimitResult:
    """Veredicto de una comprobacion, listo para volcarse en cabeceras HTTP."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    policy: str
    #: True si se resolvio sin Redis (respaldo local). Sirve para alertar.
    degraded: bool = False


class _MemoryWindow:
    """
    Respaldo local para cuando Redis no esta disponible.

    Deliberadamente simple y acotado en memoria: no pretende sustituir a
    Redis, solo evitar que la caida de Redis deje el servicio sin ningun
    freno frente a un flood.
    """

    def __init__(self, max_buckets: int = MEMORY_MAX_BUCKETS):
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_buckets = max_buckets
        self._lock = threading.Lock()

    def hit(self, bucket: str, limit: int, window_seconds: int, now: float) -> bool:
        with self._lock:
            marcas = self._buckets.get(bucket)
            if marcas is None:
                marcas = deque()
                self._buckets[bucket] = marcas
            self._buckets.move_to_end(bucket)

            corte = now - window_seconds
            while marcas and marcas[0] <= corte:
                marcas.popleft()

            if len(marcas) >= limit:
                return False

            marcas.append(now)

            while len(self._buckets) > self._max_buckets:
                self._buckets.popitem(last=False)

            return True


class RateLimiter:
    """
    Aplica una politica de cupo a una peticion.

    El cliente de Redis y el reloj se inyectan para poder probar el
    comportamiento temporal sin sleep() y sin un Redis real.
    """

    def __init__(
        self,
        redis_client=None,
        clock: Callable[[], float] = time.time,
        memory_fallback: _MemoryWindow | None = None,
    ):
        self._redis = redis_client
        self._clock = clock
        self._memory = memory_fallback or _MemoryWindow()

    # ── API publica ──────────────────────────────────────────
    def check(self, policy: RateLimitPolicy, context: RequestContext) -> RateLimitResult:
        bucket = resolve_bucket(policy, context)
        now = self._clock()

        if self._redis is None:
            return self._degraded(policy, bucket, now)

        try:
            return self._check_redis(policy, bucket, now)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de red degrada
            logger.warning(
                "Rate limit degradado a memoria: Redis no respondio (%s: %s)",
                type(exc).__name__,
                exc,
            )
            return self._degraded(policy, bucket, now)

    # ── Camino normal ────────────────────────────────────────
    def _check_redis(self, policy: RateLimitPolicy, bucket: str, now: float) -> RateLimitResult:
        inicio_ventana = now - policy.window_seconds
        marca = f"{now:.6f}-{uuid.uuid4().hex[:8]}"

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(bucket, 0, inicio_ventana)
        pipe.zadd(bucket, {marca: now})
        pipe.zcard(bucket)
        # +1 segundo de colchon para que la llave no muera antes que su
        # ultima marca por un desfase de reloj entre proceso y servidor.
        pipe.expire(bucket, policy.window_seconds + 1)
        _, _, usados, _ = pipe.execute()

        if usados > policy.limit:
            # Un rechazo NO debe consumir cupo: si contara, un cliente en
            # bucle mantendria la ventana llena para siempre y el alumno
            # legitimo nunca saldria del bloqueo.
            self._redis.zrem(bucket, marca)
            return RateLimitResult(
                allowed=False,
                limit=policy.limit,
                remaining=0,
                retry_after=self._segundos_hasta_liberar(bucket, policy, now),
                policy=policy.name,
            )

        return RateLimitResult(
            allowed=True,
            limit=policy.limit,
            remaining=max(0, policy.limit - int(usados)),
            retry_after=0,
            policy=policy.name,
        )

    def _segundos_hasta_liberar(self, bucket: str, policy: RateLimitPolicy, now: float) -> int:
        """Cuanto falta para que la marca mas antigua salga de la ventana."""
        try:
            mas_antigua = self._redis.zrange(bucket, 0, 0, withscores=True)
        except Exception:  # noqa: BLE001
            return policy.window_seconds

        if not mas_antigua:
            return 1

        _, score = mas_antigua[0]
        restante = (float(score) + policy.window_seconds) - now
        return max(1, int(restante + 0.999))

    # ── Camino degradado ─────────────────────────────────────
    def _degraded(self, policy: RateLimitPolicy, bucket: str, now: float) -> RateLimitResult:
        if not policy.fail_open:
            # Rutas de alto valor: sin Redis no hay control fiable, se cierra.
            return RateLimitResult(
                allowed=False,
                limit=policy.limit,
                remaining=0,
                retry_after=policy.window_seconds,
                policy=policy.name,
                degraded=True,
            )

        techo_local = policy.limit * DEGRADED_BURST_FACTOR
        permitido = self._memory.hit(bucket, techo_local, policy.window_seconds, now)

        return RateLimitResult(
            allowed=permitido,
            limit=policy.limit,
            remaining=0 if not permitido else policy.limit,
            retry_after=0 if permitido else policy.window_seconds,
            policy=policy.name,
            degraded=True,
        )
