"""Command-line entry point for NetAudit-CLI."""
import argparse
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from nmap_backend import scan_nmap
from reporter import write_report
from scanner import parse_ports, scan


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inventory TCP ports on one authorized host.")
    parser.add_argument("target", help="Hostname or IP address")
    parser.add_argument("-p", "--ports", default="22,80,443", help="Ports or inclusive ranges")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Concurrency limit (1-32)")
    parser.add_argument("-o", "--output", type=Path, default=Path("report.html"))
    parser.add_argument("--via-nmap", action="store_true", help="Use installed Nmap for TCP checks")
    args = parser.parse_args(argv)
    if not 1 <= args.threads <= 32:
        parser.error("--threads must be between 1 and 32")
    if args.output.suffix.lower() not in {".csv", ".json", ".html"}:
        parser.error("--output must end in .html, .json or .csv")
    try:
        ports = parse_ports(args.ports)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.target or any(not c.isprintable() or c.isspace() for c in args.target):
        parser.error("Supply one IP address or hostname.")
    start = monotonic()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        # Pin one address once so every connection checks the same endpoint.
        endpoint = socket.getaddrinfo(args.target, 0, type=socket.SOCK_STREAM)[0]
        ip = socket.getnameinfo(endpoint[4], socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)[0]
        engine = "Nmap" if args.via_nmap else "Python"
        print(f"NetAudit-CLI  |  TCP inventory\n{args.target}  [{ip}]  |  {engine}"
              f"  |  {len(ports)} ports\nStarted {timestamp}", flush=True)
        last = -1.0

        def progress(done, total, opened):
            nonlocal last
            now = monotonic()
            if done == total or now - last >= 0.15:
                filled = 24 * done // total
                bar = "#" * filled + "-" * (24 - filled)
                print(f"[{bar}] {done}/{total} checked  |  {opened} open",
                      end="\r" if sys.stdout.isatty() and done < total else "\n", flush=True)
                last = now

        if args.via_nmap:
            print("Nmap TCP connect scan running...", flush=True)
            counts, rows = scan_nmap(ip, args.ports.replace(" ", ""), args.threads)
            progress(sum(counts.values()), len(ports), len(rows))
        else:
            counts, rows = scan(endpoint, ports, args.threads, progress)
        elapsed = round(monotonic() - start, 3)
        print("\nPORT/TCP  EXPECTED SERVICE   PRIORITY  OBSERVED GREETING")
        for row in rows:
            print(f'{row["port"]:<10}{row["service"]:<19}{row["priority"]:<10}{row["banner"] or "-"}')
        if not rows:
            print("No open TCP ports observed.")
        print("  |  ".join(f"{k}: {v}" for k, v in counts.items() if v))
        report = dict(target=args.target, ip=ip, started_utc=timestamp, engine=engine,
                      tested=len(ports), duration_s=elapsed, states=counts, ports=rows)
        write_report(args.output, report)
        print(f"Completed in {elapsed:.3f} s  |  {args.output}")
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"NetAudit-CLI: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nScan interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
