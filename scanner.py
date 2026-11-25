"""Single-host TCP inventory. Service labels are conventional port assignments."""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

SERVICES = {
    21: ("FTP", "High"), 22: ("SSH", "Review"), 23: ("Telnet", "High"),
    25: ("SMTP", "Review"), 53: ("DNS", "Review"), 80: ("HTTP", "Review"),
    110: ("POP3", "Review"), 143: ("IMAP", "Review"), 443: ("HTTPS", "Info"),
    445: ("SMB", "High"), 587: ("Submission", "Review"), 993: ("IMAPS", "Info"),
    3306: ("MySQL", "High"), 3389: ("RDP", "High"), 5432: ("PostgreSQL", "High"),
    6379: ("Redis", "High"), 8080: ("HTTP-alt", "Review"),
}


def parse_ports(spec):
    """Accept comma-separated ports and inclusive ranges, removing duplicates."""
    ports = set()
    for token in spec.split(","):
        bounds = token.strip().split("-")
        if len(bounds) > 2 or not all(b.isascii() and b.isdecimal() for b in bounds):
            raise ValueError("Use ports such as 22,80,443 or 1-1024.")
        first, last = int(bounds[0]), int(bounds[-1])
        if not 1 <= first <= last <= 65535:
            raise ValueError("Ports must form ascending ranges within 1-65535.")
        ports.update(range(first, last + 1))
    return sorted(ports)


def finding(port, banner=""):
    service, priority = SERVICES.get(port, ("Unknown", "Review"))
    return dict(port=port, service=service, priority=priority, banner=banner)


def probe(endpoint, port):
    family, _, _, _, address = endpoint
    # Preserve IPv6 flow and scope fields when substituting the port.
    with socket.socket(family, socket.SOCK_STREAM) as client:
        client.settimeout(1.5)
        try:
            client.connect((address[0], port, *address[2:]))
        except ConnectionRefusedError:
            return "refused", None
        except (TimeoutError, socket.timeout):
            return "timeout", None
        except OSError:
            return "error", None

        # A quiet service is still open. Read one greeting without sending data.
        client.settimeout(0.4)
        try:
            data = client.recv(256)
        except OSError:
            data = b""
        # Binary handshakes and terminal control sequences are untrusted input.
        line = data.splitlines()[0] if data.splitlines() else b""
        banner = line.decode("ascii") if line and all(32 <= b < 127 for b in line) else ""
        return "open", finding(port, banner)


def scan(endpoint, ports, threads, progress):
    counts = dict(open=0, refused=0, timeout=0, error=0)
    rows = []
    completed = 0
    with ThreadPoolExecutor(max_workers=threads) as pool:
        # Bound the queue so long ranges also remain cheap to interrupt.
        for start in range(0, len(ports), threads * 2):
            batch = ports[start:start + threads * 2]
            futures = [pool.submit(probe, endpoint, p) for p in batch]
            for future in as_completed(futures):
                state, row = future.result()
                counts[state] += 1
                if row:
                    rows.append(row)
                completed += 1
                progress(completed, len(ports), counts["open"])
    return counts, sorted(rows, key=lambda row: row["port"])
