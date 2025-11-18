from typing import Iterable, List, Optional

def find_k_sum_with_reuse(nums: Iterable[int], k: int, target_sum: int) -> Optional[List[int]]:
    """
    Find a multiset of exactly `k` values that sums to `target_sum`,
    where values come from `nums` and **reuse is allowed**.

    Problem definition
    ------------------
    Given:
        - nums: a collection of non-negative integers (can contain duplicates)
        - k:    the number of items we must pick (exactly)
        - target_sum: the required sum of the picked items

    Question:
        Does there exist a multiset {v1, v2, ..., v_k}, where each v_i is taken
        from `nums` (with repetition allowed), such that:

            len(multiset) == k
            sum(multiset) == target_sum

    If such a multiset exists, return *one* example as a list of integers.
    If no such multiset exists, return None.

    Notes on interpretation
    -----------------------
    - "Reuse allowed" means you can use the same numeric value multiple times,
      regardless of how many times it appears in the original `nums`.
      Example: nums = [1, 2, 3], k = 3, target_sum = 6 → [2, 2, 2] is allowed.

    - The function returns a list of values, **not indices** into the original `nums`.
      The order of values in the returned list is not meaningful.

    - For performance and clarity, the function:
        * Filters out values < 0 (they don't match your non-negative assumption).
        * Filters out values > target_sum (they can never be part of a valid sum).
        * Deduplicates the remaining values using `set(...)`.
      This does not change correctness for this problem, because multiplicities
      in `nums` do not matter when reuse is allowed.

    Complexity and typical ranges
    -----------------------------
    This implementation uses dynamic programming over (used_items, current_sum):
        dp[used][s] = is it possible to reach sum `s` using exactly `used` items?

    Time roughly: O(k * target_sum * U),
        where U = number of distinct usable values after preprocessing.

    For your typical ranges (k ∈ {3, 5}, target_sum ≤ 80, values ≤ 80),
    this is extremely fast and suitable to call frequently.

    Parameters
    ----------
    nums : Iterable[int]
        Source values. Can be a list, set, etc. Duplicates are allowed but ignored.
    k : int
        Exact number of items to pick. Must be >= 0.
    target_sum : int
        Required total sum. Must be >= 0.

    Returns
    -------
    Optional[List[int]]
        - A list of `k` integers whose sum is `target_sum`, if a solution exists.
        - None if no such multiset exists.

    Examples
    --------
    >>> find_k_sum_with_reuse([0, 1, 2, 5], 3, 6)
    [1, 0, 5]    # or [2, 2, 2], etc., depending on values available

    >>> find_k_sum_with_reuse([0, 1, 2, 5], 5, 80)
    None
    """
    # Basic sanity checks
    if k < 0:
        raise ValueError("k must be non-negative")
    if target_sum < 0:
        raise ValueError("target_sum must be non-negative")

    # Preprocessing step 1: filter out values that can never be used.
    # - Negative values are outside your defined domain.
    # - Any value > target_sum cannot contribute to a sum of target_sum
    #   when all values are non-negative.
    usable_values = [v for v in nums if 0 <= v <= target_sum]

    # If we have no usable values:
    # - If k == 0 and target_sum == 0, the "empty multiset" is a valid solution.
    # - Otherwise, it's impossible.
    if not usable_values:
        if k == 0 and target_sum == 0:
            return []  # pick nothing
        return None

    # Preprocessing step 2: deduplicate values.
    # Since reuse is allowed, we only care which distinct numeric values
    # are available, not how many times each appears.
    vals = sorted(set(usable_values))

    # Edge case: k == 0
    # - sum of zero items is 0; only valid if target_sum == 0.
    if k == 0:
        return [] if target_sum == 0 else None

    # Create a DP table:
    # dp[used][s] is True if we can reach sum `s` using exactly `used` items.
    # used ranges from 0..k, s ranges from 0..target_sum.
    dp = [[False] * (target_sum + 1) for _ in range(k + 1)]

    # Parent pointers for reconstruction:
    # parent[used][s] = (prev_used, prev_sum, value_used_to_get_here)
    # If dp[used][s] is True and parent[used][s] is not None,
    # then dp[prev_used][prev_sum] must have been True, and
    # s = prev_sum + value_used_to_get_here, used = prev_used + 1.
    parent = [[None] * (target_sum + 1) for _ in range(k + 1)]

    # Base case: using 0 items, we can only achieve sum 0.
    dp[0][0] = True

    # Fill the DP table.
    # For each number of used items from 0 up to k-1,
    # we try to add one more value to reach new states.
    for used in range(k):
        for s in range(target_sum + 1):
            # If this state is not reachable, skip it.
            if not dp[used][s]:
                continue

            # From (used, s), we can choose any value v in vals
            # and move to (used + 1, s + v), as long as s + v <= target_sum.
            for v in vals:
                new_sum = s + v
                if new_sum > target_sum:
                    # Since vals is sorted ascending, if v is too big,
                    # all larger v will also be too big; we can break early.
                    break

                if not dp[used + 1][new_sum]:
                    dp[used + 1][new_sum] = True
                    parent[used + 1][new_sum] = (used, s, v)

    # If dp[k][target_sum] is False, no solution exists.
    if not dp[k][target_sum]:
        return None

    # Reconstruct one valid multiset by walking back through the parent table.
    result: List[int] = []
    used = k
    s = target_sum

    while used > 0:
        prev_state = parent[used][s]
        # Sanity check: parent must exist if dp[used][s] is True and used > 0.
        if prev_state is None:
            # This should not happen if the DP logic is correct,
            # but we guard against it to avoid a crash in weird cases.
            return None
        prev_used, prev_sum, value_used = prev_state

        result.append(value_used)
        used, s = prev_used, prev_sum

    # We reconstructed in reverse order; reverse again to get forward order.
    result.reverse()
    return result
