import argparse
import csv
import json
import os
import subprocess
import socket
import sys
from dataclasses import dataclass, asdict
from datetime import datetime

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DEFAULT_PORT = 5201
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


@dataclass
class TestResult:
    timestamp: str = ""
    direction: str = ""
    protocol: str = "TCP"
    mean_mbps: float = 0.0
    min_mbps: float = 0.0
    max_mbps: float = 0.0
    jitter_ms: float = 0.0
    lost_percent: float = 0.0
    retransmits: int = 0
    duration_s: float = 0.0
    parallel: int = 1
    bandwidth_mbps: float = 0.0


def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            if info[0] == socket.AF_INET:
                ips.append(info[4][0])
    except socket.gaierror:
        pass
    if not ips:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    return sorted(set(ips))


def parse_bits_per_second(bps):
    return float(bps) / 1_000_000.0


def _min_max_from_intervals(data, key):
    vals = []
    for interval in data.get("intervals", []):
        s = interval.get("sum")
        if s and s.get(key):
            vals.append(parse_bits_per_second(s[key]))
    if not vals:
        return 0.0, 0.0
    return min(vals), max(vals)


def run_iperf_command(cmd):
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        print("  [오류] iPerf3 실행 시간 초과")
        return None
    except FileNotFoundError:
        print("[오류] iperf3 실행 파일을 찾을 수 없습니다. 'choco install iperf3' 로 설치하세요.")
        sys.exit(1)

    if proc.returncode != 0:
        if proc.returncode == 1 and "unable to connect" in proc.stderr:
            print(f"  [오류] 서버에 연결할 수 없습니다. 상대 PC에서 서버 모드를 실행했는지 확인하세요.")
        else:
            print(f"  [오류] iPerf3 실패 (코드 {proc.returncode})")
            for line in proc.stderr.splitlines():
                print(f"    {line.strip()}")
        return None

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("  [오류] iPerf3 출력 파싱 실패")
        return None


def run_tcp_test(host, port, duration, parallel, reverse):
    cmd = ["iperf3", "-c", host, "-p", str(port), "-t", str(duration), "-J"]
    if parallel > 1:
        cmd += ["-P", str(parallel)]
    if reverse:
        cmd += ["-R"]
    data = run_iperf_command(cmd)
    if not data:
        return None

    end = data.get("end", {})
    sum_recv = end.get("sum_received", {})
    sum_sent = end.get("sum_sent", {})

    direction = ""
    mean_bps = 0.0
    if reverse:
        direction = "upload (client->server)"
        mean_bps = sum_sent.get("bits_per_second", 0.0)
    else:
        direction = "download (server->client)"
        mean_bps = sum_recv.get("bits_per_second", 0.0)

    retrans = 0
    if not reverse:
        retrans = sum_sent.get("retransmits", 0)

    result = TestResult(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        direction=direction,
        protocol="TCP",
        mean_mbps=parse_bits_per_second(mean_bps),
        retransmits=int(retrans),
        duration_s=float(end.get("sum_sent", {}).get("seconds", duration)),
        parallel=parallel,
    )
    result.min_mbps, result.max_mbps = _min_max_from_intervals(data, "bits_per_second")
    return result


def run_udp_test(host, port, duration, bandwidth, parallel, reverse):
    cmd = ["iperf3", "-c", host, "-p", str(port), "-t", str(duration), "-u", "-b", bandwidth, "-J"]
    if parallel > 1:
        cmd += ["-P", str(parallel)]
    if reverse:
        cmd += ["-R"]
    data = run_iperf_command(cmd)
    if not data:
        return None

    end = data.get("end", {})
    if reverse:
        direction = "download (server->client)"
        total = end.get("sum_received") or end.get("sum") or {}
    else:
        direction = "upload (client->server)"
        total = end.get("sum") or {}

    result = TestResult(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        direction=direction,
        protocol="UDP",
        mean_mbps=parse_bits_per_second(total.get("bits_per_second", 0.0)),
        jitter_ms=float(total.get("jitter_ms", 0.0)),
        lost_percent=float(total.get("lost_percent", 0.0)),
        duration_s=float(data.get("start", {}).get("test_start", {}).get("duration", duration)),
        parallel=parallel,
    )
    result.min_mbps, result.max_mbps = _min_max_from_intervals(data, "bits_per_second")
    return result


def run_server(port):
    print(f"[서버 모드] iPerf3 서버 시작 (포트 {port}) ...")
    print("[서버 모드] 종료하려면 Ctrl+C 를 누르세요.")
    print("[서버 모드] 현재 PC IP:")
    for ip in get_local_ips():
        print(f"    - {ip}")
    cmd = ["iperf3", "-s", "-p", str(port)]
    try:
        hidden = 0
        if os.name == "nt":
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            hidden = info
        proc = subprocess.Popen(cmd, startupinfo=hidden if hidden else None)
        proc.wait()
    except KeyboardInterrupt:
        print("\n[서버 모드] 종료되었습니다.")
        if "proc" in locals():
            proc.terminate()


def pretty_mbps(value):
    return f"{value:.2f}"


def print_results(results):
    width = 13
    header = f"+{'-' * (16 + width)}+{'-' * (width + 2)}+{'-' * (width + 2)}+{'-' * (width + 2)}+{'-' * width}+{'-' * width}+"
    print()
    print(header)
    print(f"| {'측정 항목':<14} | {'평균 Mbps':>{width}} | {'최소 Mbps':>{width}} | {'최대 Mbps':>{width}} | {'지터 ms':>{width}} | {'손실 %':>{width}} |")
    print(header)
    for r in results:
        proto = "UDP" if r.protocol == "UDP" else "TCP"
        label = f"{proto} {r.direction}"
        jitter = f"{r.jitter_ms:.3f}" if r.protocol == "UDP" else "-"
        lost = f"{r.lost_percent:.2f}" if r.protocol == "UDP" else "-"
        print(
            f"| {label:<14} | {pretty_mbps(r.mean_mbps):>{width}} | {pretty_mbps(r.min_mbps):>{width}} "
            f"| {pretty_mbps(r.max_mbps):>{width}} | {jitter:>{width}} | {lost:>{width}} |"
        )
    print(header)

    tcp_results = [r for r in results if r.protocol == "TCP"]
    if tcp_results:
        retrans = sum(r.retransmits for r in tcp_results)
        print(f"TCP 재전송 패킷 수 (업로드 제외 누계): {retrans}")


def save_csv(results, path):
    if not results:
        return
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    headers = [
        "timestamp",
        "direction",
        "protocol",
        "mean_mbps",
        "min_mbps",
        "max_mbps",
        "jitter_ms",
        "lost_percent",
        "retransmits",
        "duration_s",
        "parallel",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row.pop("bandwidth_mbps", None)
            writer.writerow({k: row.get(k, "") for k in headers})
    print(f"\n결과가 저장되었습니다: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="허브/공유기 통해 연결된 2대의 PC 간 네트워크 속도 측정 도구 (iPerf3 기반)"
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="서버 모드로 실행 (수신 대기). 클라이언트 모드보다 먼저 실행하세요.",
    )
    parser.add_argument("--client", metavar="HOST", help="클라이언트 모드. 상대 PC의 IP 주소")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"포트 번호 (기본: {DEFAULT_PORT})")
    parser.add_argument("--duration", type=int, default=10, help="테스트 시간(초) (기본: 10)")
    parser.add_argument("--parallel", type=int, default=1, help="병렬 스트림 수 (기본: 1)")
    parser.add_argument("--udp", action="store_true", help="UDP 테스트 실행 (지터/패킷 손실 측정)")
    parser.add_argument("--bandwidth", default="100M", help="UDP 타깃 대역폭 (기본: 100M, K/M/G 접두사 지원)")
    parser.add_argument("--times", type=int, default=1, help="테스트 반복 횟수 (기본: 1)")
    parser.add_argument("--direction", choices=["download", "upload", "both"], default="both", help="TCP 방향 선택 (기본: both)")
    parser.add_argument("--output", metavar="CSV", help="결과를 CSV 파일로 저장")
    parser.add_argument("--show-ip", action="store_true", help="현재 PC의 IP 주소 목록 표시 후 종료")

    args = parser.parse_args()

    if args.show_ip:
        print("현재 PC IP 주소:")
        for ip in get_local_ips():
            print(f"    - {ip}")
        return

    if args.server:
        run_server(args.port)
        return

    if not args.client:
        parser.print_help()
        return

    print(f"대상 호스트: {args.client}:{args.port}")
    results = []

    for i in range(args.times):
        if args.times > 1:
            print(f"\n========== [반복 {i + 1}/{args.times}] ==========")

        if args.udp:
            for r in range(args.parallel):
                pass
            print(f"\n[UDP 테스트] {args.duration}초, 대역폭 {args.bandwidth}, 병렬 {args.parallel}")
            r = run_udp_test(args.client, args.port, args.duration, args.bandwidth, args.parallel, reverse=False)
            if r:
                r.parallel = args.parallel
                results.append(r)
        else:
            dirs = []
            if args.direction in ("download", "both"):
                dirs.append((False, "download"))
            if args.direction in ("upload", "both"):
                dirs.append((True, "upload"))

            for reverse, label in dirs:
                dir_label = "TCP 다운로드 (server->client)" if not reverse else "TCP 업로드 (client->server)"
                print(f"\n[{dir_label}] {args.duration}초, 병렬 {args.parallel}")
                r = run_tcp_test(args.client, args.port, args.duration, args.parallel, reverse)
                if r:
                    results.append(r)

    print_results(results)

    if args.output:
        save_csv(results, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")