"""Re-run the MCP Guardian paper's Section 4 checks against weather_server.py over stdio.

    uv run --with "mcp>=2" python -m detectors.mcp_guardian.examples.reproduce_paper [--calls 300]

1. Security (Sec. 4.1): missing/invalid token, destructive arguments, 100 rapid calls.
2. Tool metadata (our adaptation): filter_tools on the server's tools/list result.
3. Overhead (Sec. 4.2, Table 1): round-trip latency with and without Guardian.
"""

import argparse
import asyncio
import statistics
import sys
import tempfile
import time
from pathlib import Path

from mcp import Client, StdioServerParameters

from detectors.mcp_guardian import MCPGuardian

SERVER = "detectors.mcp_guardian.examples.weather_server"
REPO_ROOT = Path(__file__).resolve().parents[3]
TOKEN = "mysecrettoken123"


def server(log_dir: str, **env: str) -> StdioServerParameters:
    env.setdefault("GUARDIAN_LOG", str(Path(log_dir) / "mcp_guardian.log"))
    return StdioServerParameters(command=sys.executable, args=["-m", SERVER], env=env, cwd=REPO_ROOT)


async def call(client: Client, arguments: dict) -> str:
    result = await client.call_tool("get_forecast", arguments)
    text = result.content[0].text
    return f"ERROR {text}" if result.is_error else text


async def security(log_dir: str) -> None:
    print("== Security (paper Sec. 4.1) ==")
    async with Client(server(log_dir, GUARDIAN_MAX_REQUESTS="5")) as client:
        await client.list_tools()
        print("no token        ->", await call(client, {"city": "LA"}))
        print("invalid token   ->", await call(client, {"city": "LA", "guardian_token": "nope"}))
        print("rm -rf /        ->", await call(client, {"city": "LA; rm -rf /", "guardian_token": TOKEN}))
        print(
            "drop table      ->",
            await call(client, {"city": "x'; DROP TABLE users;--", "guardian_token": "anotherValidToken456"}),
        )

    async with Client(server(log_dir, GUARDIAN_MAX_REQUESTS="5")) as client:
        await client.list_tools()
        outcomes = [await call(client, {"city": "LA", "guardian_token": TOKEN}) for _ in range(100)]
        limited = sum(o == "ERROR 429 Too Many Requests" for o in outcomes)
        print(f"100 rapid calls -> {100 - limited} served, {limited} rejected with 429 (limit 5/min)")


async def tool_metadata(log_dir: str) -> None:
    print("\n== Tool metadata via filter_tools (our adaptation) ==")
    async with Client(server(log_dir, GUARDIAN_DISABLED="1")) as client:
        tools = (await client.list_tools()).tools
    guardian = MCPGuardian(valid_tokens=[], logfile_path=None)
    for tool in tools:
        scan = guardian.scan_tool(tool)
        verdict = "BLOCK " + ", ".join(scan.rules) if scan.blocked else "allow"
        print(f"{tool.name:13} {verdict}")


async def latency(log_dir: str, calls: int) -> None:
    print(f"\n== Overhead (paper Sec. 4.2), {calls} calls each ==")
    results = {}
    for label, env in [
        ("baseline", {"GUARDIAN_DISABLED": "1"}),
        ("guardian", {"GUARDIAN_MAX_REQUESTS": str(calls * 10)}),
    ]:
        async with Client(server(log_dir, **env)) as client:
            await client.list_tools()
            for _ in range(20):  # warm-up
                await call(client, {"city": "LA", "guardian_token": TOKEN})
            samples = []
            for _ in range(calls):
                started = time.perf_counter()
                text = await call(client, {"city": "LA", "guardian_token": TOKEN})
                samples.append((time.perf_counter() - started) * 1000)
                assert not text.startswith("ERROR"), text
        p95 = statistics.quantiles(samples, n=20)[-1]
        results[label] = (statistics.median(samples), p95)
        print(f"{label:9} median {results[label][0]:6.2f} ms   p95 {p95:6.2f} ms")
    (base_med, base_p95), (g_med, g_p95) = results["baseline"], results["guardian"]
    print(f"overhead  median {g_med - base_med:+6.2f} ms   p95 {g_p95 - base_p95:+6.2f} ms")
    print("paper     median  +3.80 ms   p95  +4.30 ms  (25.1 -> 28.9, 32.4 -> 36.7)")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calls", type=int, default=300)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as log_dir:
        await security(log_dir)
        await tool_metadata(log_dir)
        await latency(log_dir, args.calls)


if __name__ == "__main__":
    asyncio.run(main())
