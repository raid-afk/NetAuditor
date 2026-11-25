"""Run a reproducible inventory against two disposable local TCP services."""
import argparse
from contextlib import ExitStack
import socketserver
from threading import Thread
from main import main


class Greeting(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(b"NetAudit demo service 1.0\r\n")


class Quiet(socketserver.BaseRequestHandler):
    def handle(self):
        # A listener can accept a connection and offer no greeting.
        self.request.recv(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="report.html")
    args = parser.parse_args()
    with ExitStack() as stack:
        ports = []
        for handler in (Greeting, Quiet):
            server = stack.enter_context(socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            stack.callback(server.shutdown)
            ports.append(str(server.server_address[1]))
        raise SystemExit(main(["127.0.0.1", "-p", ",".join(ports), "-o", args.output]))
