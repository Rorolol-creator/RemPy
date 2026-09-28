import numpy as np

from numba import njit

import heapq
from typing import Any


class PQueue:
    def __init__(self):
        self.heap = []
        self.entry_finder = {}
        self.count = 0

    def push(self, p: float, v: Any):
        if v in self.entry_finder:
            old_entry = self.entry_finder[v]
            old_entry[-1] = None

        entry = [p, self.count, v]
        self.count += 1

        self.entry_finder[v] = entry
        heapq.heappush(self.heap, entry)

    def pop(self) -> tuple[float, Any]:
        while self.heap:
            p, _, v = heapq.heappop(self.heap)
            if v is not None:
                del self.entry_finder[v]
                return p, v
        raise KeyError("pop from an empty priority queue")

    def empty(self) -> bool:
        return not self.entry_finder
