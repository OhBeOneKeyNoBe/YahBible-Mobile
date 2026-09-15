r"""YAHBIBLE_BOOT — bring the FULL desktop engine to life inside the phone.

Called from Java (YahBridge.startEngine) after YAHBIBLE_BASE / YAHBIBLE_NO_D /
YAHBIBLE_ANDROID are set. Imports the real O'Tav'iel server and serves it on
127.0.0.1:41537 in a daemon thread; returns True once the port answers.
"""
from __future__ import annotations

import os
import socket
import threading
import time

_STARTED = {"t": None}


def start():
    os.environ.setdefault("YAHBIBLE_NO_D", "1")
    os.environ.setdefault("YAHBIBLE_ANDROID", "1")
    if _STARTED["t"] is None or not _STARTED["t"].is_alive():
        import o_taviel_server as S

        def run():
            try:
                S.main()
            except Exception:
                pass
        t = threading.Thread(target=run, daemon=True, name="otaviel-server")
        t.start()
        _STARTED["t"] = t
    for _ in range(240):
        try:
            socket.create_connection(("127.0.0.1", 41537), 1).close()
            return True
        except Exception:
            time.sleep(0.5)
    return False
