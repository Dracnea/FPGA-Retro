from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TransportStats:
    chunks: int = 0
    bytes: int = 0
    waits: int = 0           # reads that returned nothing


class Transport:
    """A byte source for the FRM1 parser.

    open()      acquire the device / file / generator
    read()      return the next chunk of stream bytes, b"" if nothing is
                available right now (never blocks for long)
    close()     release
    stats       TransportStats
    """
    def __init__(self):
        self.stats = TransportStats()

    @property
    def eof(self) -> bool:
        """True once the source can never deliver more (a replay file at its end)."""
        return False

    def open(self) -> None: ...
    def read(self) -> bytes: raise NotImplementedError
    def close(self) -> None: ...

    def __enter__(self):
        self.open(); return self

    def __exit__(self, *a):
        self.close()


class Recorder(Transport):
    """Wraps a transport and appends every chunk to a file for later replay."""
    def __init__(self, inner: Transport, path: str):
        super().__init__()
        self.inner, self.path, self._f = inner, path, None

    def open(self):
        self.inner.open()
        self._f = open(self.path, "wb")

    @property
    def eof(self) -> bool:
        return self.inner.eof

    def read(self) -> bytes:
        d = self.inner.read()
        if d:
            self._f.write(d)
            self.stats.chunks += 1; self.stats.bytes += len(d)
        else:
            self.stats.waits += 1
        return d

    def close(self):
        if self._f:
            self._f.close(); self._f = None
        self.inner.close()
