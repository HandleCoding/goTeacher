from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from goteacher.katago.protocol import Query, parse_response_line


class EngineError(RuntimeError):
    pass


@dataclass(slots=True)
class EngineConfig:
    binary: str
    config_path: str
    model_path: str
    human_model_path: str | None = None
    startup_timeout: float = 15.0
    query_timeout: float = 120.0
    stderr_lines: int = 100


class KataGoEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_tail: deque[str] = deque(maxlen=config.stderr_lines)
        self._stderr_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._process is not None:
            return
        args = [
            self.config.binary,
            "analysis",
            "-config",
            self.config.config_path,
            "-model",
            self.config.model_path,
        ]
        if self.config.human_model_path:
            args.extend(["-human-model", self.config.human_model_path])
        self._process = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=4 * 1024 * 1024,
            ),
            timeout=self.config.startup_timeout,
        )
        self._stderr_task = asyncio.create_task(self._collect_stderr())

    async def analyze(self, query: Query) -> dict[str, Any]:
        await self.start()
        assert self._process is not None
        if self._process.stdin is None or self._process.stdout is None:
            raise EngineError("KataGo pipes were not created")
        num_turns = len(query.analyze_turns) if query.analyze_turns else 1
        async with self._lock:
            try:
                self._process.stdin.write(query.to_json_line())
                await self._process.stdin.drain()
                if num_turns == 1:
                    line = await asyncio.wait_for(self._process.stdout.readline(), timeout=self.config.query_timeout)
                    if not line:
                        code = await self._process.wait()
                        raise EngineError(f"KataGo exited with code {code}; stderr tail: {self.stderr_tail()}")
                    response = parse_response_line(line)
                else:
                    parts: list[dict[str, Any]] = []
                    for _ in range(num_turns):
                        line = await asyncio.wait_for(self._process.stdout.readline(), timeout=self.config.query_timeout)
                        if not line:
                            code = await self._process.wait()
                            raise EngineError(f"KataGo exited with code {code}; stderr tail: {self.stderr_tail()}")
                        parts.append(parse_response_line(line))
                    response = {"id": parts[0].get("id"), "results": [{"turn": p.get("turnNumber", i), "analysis": p} for i, p in enumerate(parts)]}
            except EngineError:
                raise
            except Exception as exc:
                raise EngineError(f"KataGo query failed: {exc}; stderr tail: {self.stderr_tail()}") from exc
        response_id = response.get("id")
        if response_id and response_id != query.id:
            raise EngineError(f"KataGo response id mismatch: expected {query.id}, got {response_id}")
        return response

    async def close(self) -> None:
        if self._process is None:
            return
        process = self._process
        self._process = None
        if process.stdin:
            process.stdin.close()
            await process.stdin.wait_closed()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None

    def stderr_tail(self) -> str:
        return "\n".join(self._stderr_tail)

    async def _collect_stderr(self) -> None:
        assert self._process is not None
        if self._process.stderr is None:
            return
        while True:
            line = await self._process.stderr.readline()
            if not line:
                return
            self._stderr_tail.append(line.decode("utf-8", errors="replace").rstrip())


def require_files(*paths: str | None) -> None:
    for item in paths:
        if item and not Path(item).expanduser().exists():
            raise FileNotFoundError(item)
