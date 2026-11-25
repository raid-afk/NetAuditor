"""Optional Nmap TCP connect backend for Nmap-authorized targets."""
import subprocess
import xml.etree.ElementTree as ET
from scanner import finding


def scan_nmap(ip, spec, threads):
    args = ["nmap", "-sT", "-Pn", "-n", "--max-parallelism", str(threads),
            "-p", spec, "-oX", "-"]
    if ":" in ip:
        args.append("-6")
    try:
        proc = subprocess.run(args + [ip], capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise ValueError("Install Nmap and add it to PATH for --via-nmap.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(exc.stderr.decode(errors="replace").strip() or "Nmap failed.") from exc
    root = ET.fromstring(proc.stdout)
    host = root.find("host")
    if host is None or host.find("ports") is None:
        raise ValueError("Nmap returned no port inventory.")
    counts, rows = {}, []
    # Nmap compresses repeated states (such as closed) into extraports.
    for group in host.findall("ports/extraports"):
        counts[group.get("state")] = int(group.get("count"))
    for port in host.findall("ports/port"):
        state = port.find("state").get("state")
        counts[state] = counts.get(state, 0) + 1
        if state == "open":
            rows.append(finding(int(port.get("portid"))))
    return counts, sorted(rows, key=lambda row: row["port"])
