import signal
import sys
import time


def handle_sigterm(signum, frame):
    # frame: execution context
    # signum: signal number: 9, 15
    print(f"Received SIGTERM, shutting down cleanly {signum}...", flush=True)
    sys.exit(0)


def sig_handle_case():
    # SIGTERM: Interuption Signal i.e ctrl+c
    signal.signal(signal.SIGTERM, handle_sigterm)
    print("Waiting for signal...", flush=True)

    while True:
        time.sleep(1)


def sig_ignore_case():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("Waiting for signal...", flush=True)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    # sig_handle_case()
    sig_ignore_case()
