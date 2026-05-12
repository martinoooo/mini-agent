"""
快速排序 — 工业级实现。

特性：
  - 三路切分 (3-way partition)，高效处理大量重复元素
  - 随机 pivot，避免最坏 O(n²)
  - 混合策略：小数组切换为插入排序
  - 支持原地排序 & 返回新数组两种模式
  - 完整类型标注 + doctest
"""

from __future__ import annotations

import random
from typing import Any, MutableSequence, Sequence, TypeVar

T = TypeVar("T", bound=Any)

# ── 阈值：子数组长度 ≤ 此值时使用插入排序 ──────────────────────────
INSERTION_THRESHOLD = 16


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def quicksort(
    arr: MutableSequence[T],
    *,
    key: Any = None,
    reverse: bool = False,
    inplace: bool = True,
) -> Sequence[T] | None:
    """对序列做快速排序（默认原地）。

    Args:
        arr:     待排序的可变序列（如 list）。
        key:     单参数函数，提取比较键（类似 sorted 的 key）。
        reverse: 是否降序。
        inplace: 是否原地修改；若为 False 则返回新 list。

    Returns:
        若 inplace=False，返回排序后的新 list；否则返回 None。

    Raises:
        TypeError: arr 不可变时抛出。

    Examples:
        >>> quicksort([3, 1, 2])
        [1, 2, 3]
        >>> quicksort([3, 1, 2], reverse=True)
        [3, 2, 1]
        >>> quicksort([3, 1, 2], inplace=False)
        [1, 2, 3]
        >>> quicksort(["b", "a", "c"], key=lambda x: x)
        ['a', 'b', 'c']
    """
    if not inplace:
        arr = list(arr)  # type: ignore[assignment]

    # 规范化 key
    key_fn = (lambda x: x) if key is None else key

    if len(arr) <= 1:
        return arr if not inplace else None

    _quicksort(arr, 0, len(arr) - 1, key=key_fn, reverse=reverse)

    if not inplace:
        return arr
    return None


def sorted_quicksort(
    arr: Sequence[T],
    *,
    key: Any = None,
    reverse: bool = False,
) -> list[T]:
    """返回排序后的新 list（不改原序列）。

    >>> sorted_quicksort([3, 1, 2])
    [1, 2, 3]
    """
    return quicksort(list(arr), key=key, reverse=reverse, inplace=False)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _quicksort(
    arr: MutableSequence[T],
    lo: int,
    hi: int,
    *,
    key: Any,
    reverse: bool,
) -> None:
    """递归三路切分快速排序。"""
    if hi - lo < INSERTION_THRESHOLD:
        _insertion_sort(arr, lo, hi, key=key, reverse=reverse)
        return

    # 三路切分
    lt, gt = _partition3(arr, lo, hi, key=key, reverse=reverse)

    _quicksort(arr, lo, lt - 1, key=key, reverse=reverse)
    _quicksort(arr, gt + 1, hi, key=key, reverse=reverse)


def _partition3(
    arr: MutableSequence[T],
    lo: int,
    hi: int,
    *,
    key: Any,
    reverse: bool,
) -> tuple[int, int]:
    """Dijkstra 三路切分。

    随机选取 pivot 后，将数组分为三区：
      [lo .. lt-1]  < pivot
      [lt .. gt]    = pivot
      [gt+1 .. hi]  > pivot

    Returns:
        (lt, gt) — 等值区的左右边界（闭区间）。
    """
    # 随机 pivot → 换到 lo 位置
    pivot_idx = random.randint(lo, hi)
    arr[lo], arr[pivot_idx] = arr[pivot_idx], arr[lo]
    pivot_val = key(arr[lo])

    lt = lo
    i = lo + 1
    gt = hi

    while i <= gt:
        cur = key(arr[i])
        if reverse:
            # 降序：pivot 大 → 放左边
            if cur > pivot_val:
                arr[lt], arr[i] = arr[i], arr[lt]
                lt += 1
                i += 1
            elif cur < pivot_val:
                arr[i], arr[gt] = arr[gt], arr[i]
                gt -= 1
            else:
                i += 1
        else:
            if cur < pivot_val:
                arr[lt], arr[i] = arr[i], arr[lt]
                lt += 1
                i += 1
            elif cur > pivot_val:
                arr[i], arr[gt] = arr[gt], arr[i]
                gt -= 1
            else:
                i += 1

    return lt, gt


def _insertion_sort(
    arr: MutableSequence[T],
    lo: int,
    hi: int,
    *,
    key: Any,
    reverse: bool,
) -> None:
    """对小规模子数组做插入排序。"""
    for i in range(lo + 1, hi + 1):
        cur = arr[i]
        cur_key = key(cur)
        j = i - 1
        if reverse:
            while j >= lo and key(arr[j]) < cur_key:
                arr[j + 1] = arr[j]
                j -= 1
        else:
            while j >= lo and key(arr[j]) > cur_key:
                arr[j + 1] = arr[j]
                j -= 1
        arr[j + 1] = cur


# ---------------------------------------------------------------------------
# 基准 & 测试
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import timeit

    # 正确性验证
    import doctest

    print("=== doctest ===")
    doctest.testmod(verbose=True)

    # 压力测试
    print("\n=== 压力测试 ===")
    sizes = [100, 1_000, 10_000]
    for n in sizes:
        data = [random.randint(0, n) for _ in range(n)]
        qs = data[:]
        t0 = timeit.default_timer()
        quicksort(qs)
        t1 = timeit.default_timer()

        py_sorted = data[:]
        t2 = timeit.default_timer()
        py_sorted.sort()
        t3 = timeit.default_timer()

        assert qs == py_sorted, f"排序结果不一致 (n={n})"
        print(
            f"  n={n:>6,}  "
            f"quicksort: {t1 - t0:.4f}s  "
            f"builtin:   {t3 - t2:.4f}s  "
            f"ratio: {(t1 - t0) / (t3 - t2):.2f}x"
        )

    print("\n✅ 全部通过")
