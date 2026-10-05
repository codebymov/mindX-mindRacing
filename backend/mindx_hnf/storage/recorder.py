"""Non-blocking artifact recorder.

A background-thread consumer behind a bounded queue. The hot path calls
`offer(...)` which never blocks: if the queue is full, the *oldest persistence
item is dropped*, never the live feedback. Persistence loss is logged but never
allowed to stall neuromodulation.

The actual writers (BIDS, DataLad commit, Postgres insert, Cloudflare-R2-style
blob upload) are stubs to be implemented; the concurrency contract around them
is what this scaffold pins down.

Todo:
    * Implement ``ArtifactRecorder._write`` dispatch: "raw" -> BIDS fNIRS
      append (SNIRF/BIDS), "ins" -> versioned time series (DataLad/NAS),
      "feedback" -> time series + game params, "meta" -> Postgres insert
      (pseudonymized); stamp the provenance on everything.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RunProvenance:
    """Stamped onto every artifact for reproducibility (CLAUDE.md §4).

    Attributes:
        git_sha: Commit of the code that produced the artifact.
        config_hash: Hash of the run config YAML.
        dyad_id: Pseudonymized dyad id.
        session_label: Label of the session plan.
    """

    git_sha: str
    config_hash: str
    dyad_id: str
    session_label: str


class ArtifactRecorder:
    """Persists pipeline artifacts on a background thread, never blocking the loop.

    Attributes:
        provenance: Stamped onto every persisted artifact.
    """

    def __init__(self, provenance: RunProvenance, max_queue: int = 4096) -> None:
        """Create the recorder; call ``start`` to launch the writer thread.

        Args:
            provenance: Stamped onto every persisted artifact.
            max_queue: Queue capacity; beyond it the oldest items are dropped.
        """
        self.provenance = provenance
        self._q: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="recorder")
        self._dropped = 0

    def start(self) -> None:
        """Start the background writer thread."""
        self._thread.start()

    def offer(self, kind: str, payload: Any) -> None:
        """Enqueue an item for persistence without blocking.

        On overflow the oldest queued item is dropped; the caller is never
        blocked.

        Args:
            kind: Artifact kind ("raw", "ins", "feedback" or "meta").
            payload: The object to persist.
        """
        try:
            self._q.put_nowait((kind, payload))
        except queue.Full:
            try:
                self._q.get_nowait()  # drop oldest
                self._dropped += 1
            except queue.Empty:
                pass
            try:
                self._q.put_nowait((kind, payload))
            except queue.Full:
                self._dropped += 1

    def _run(self) -> None:
        """Drain the queue until stopped; a failed write is logged, never raised."""
        while not self._stop.is_set() or not self._q.empty():
            try:
                kind, payload = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self._write(kind, payload)
            except Exception:  # noqa: BLE001 - never crash the recorder thread
                logger.exception("Artifact write failed for kind=%s", kind)

    def _write(self, kind: str, payload: Any) -> None:
        """Persist one item (currently a stub that only logs).

        Args:
            kind: Artifact kind ("raw", "ins", "feedback" or "meta").
            payload: The object to persist.
        """
        # TODO(claude-code): dispatch by kind:
        #   "raw"     -> BIDS-format fNIRS append (snirf/BIDS)
        #   "ins"     -> time series to versioned store (DataLad/NAS)
        #   "feedback"-> time series + game params
        #   "meta"    -> Postgres insert (pseudonymized)
        # Stamp self.provenance on everything.
        logger.debug("persist kind=%s sha=%s", kind, self.provenance.git_sha)

    def stop(self) -> None:
        """Signal the writer to finish the queue and wait up to 5 s for it."""
        self._stop.set()
        self._thread.join(timeout=5.0)
        if self._dropped:
            logger.warning("Recorder dropped %d items under load.", self._dropped)
