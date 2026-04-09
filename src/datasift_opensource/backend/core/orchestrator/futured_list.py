from typing import Annotated, Any, Self

from prefect.futures import PrefectFuture
from pydantic import BaseModel, Field


class _CountedTaskFuture(BaseModel):
    _future: PrefectFuture[Any] | None
    _count: Annotated[int, Field(ge=0)]

    def __init__(self, future, count):
        self._future = None  # predeclare attributes
        self._count = 0
        self.set(future, count)

    def get_future(self):
        if self._future is not None and self._count > 0:
            result = self._future
            self._count -= 1
            if self._count == 0:
                self._future = None
            return result
        return None

    def set(self, future, count):
        self._future = future
        self._count = count

    def __repr__(self):
        return f"CountedTaskFuture(value={self._future}, count={self._count})"


class FuturedList:
    def __init__(self, items_with_counts):
        self.items = [_CountedTaskFuture(future, count) for future, count in items_with_counts]

    @classmethod
    def from_size(cls, size: int) -> Self:
        """
        Create an empty CountedList with `size` entries, each initialized to (None, 0).
        """
        return cls(items_with_counts=[(None, 0) for _ in range(size)])

    def get_future(self, index):
        if 0 <= index < len(self.items):
            return self.items[index].get_future()
        else:
            raise IndexError("Index out of range, given {index=} the list size is {len(self)}")

    def set_entry(self, index, future, count):
        if 0 <= index < len(self.items):
            self.items[index].set(future, count)
        else:
            # we don't allow appending
            raise IndexError("Index out of range")

    def __repr__(self):
        return f"FuturedList({self.items})"

    def __len__(self):
        return len(self.items)
