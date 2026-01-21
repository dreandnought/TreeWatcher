The issue is in the `parse_line` method of `treewatcher.py`. Specifically, the logic that handles indentation chunks incorrectly consumes the start of the file name when a tree connector (like `├`) appears inside a 4-character chunk but doesn't occupy the entire chunk (e.g., ` ├─m` in `│  │      │  ├─models`).

In the current implementation:
1. The code reads 4 characters at a time.
2. For the chunk ` ├─m` (space, connector, dash, 'm'), it detects the connector `├`.
3. It assumes the entire 4-character chunk is part of the tree structure (`safe_len = 4`) and skips it.
4. This causes the character `m` to be skipped, resulting in `odels`.

**Plan:**
1.  Create a reproduction script `reproduce_issue.py` containing the `parse_line` logic and the problematic input lines to confirm the bug and verify the fix.
2.  Modify `treewatcher.py`:
    *   Update the loop in `parse_line` (lines 208-212) to treat a found connector as the start of the name/prefix block.
    *   Instead of consuming the full 4 characters (`safe_len = 4`), set `safe_len` to the index of the connector and set `found_name_char = True`.
    *   This will stop the indentation parsing at the connector, leaving the connector and the following text (e.g., `├─models`) to be handled by the prefix stripping logic, which is already capable of removing `├─`.
3.  Run the reproduction script again to verify the fix works for `models` and `trackers` as well as standard lines.
4.  Run the full application to ensure no regressions.

**Verification:**
The reproduction script will output the parsed names. `models` should appear as `models` (not `odels`) and `trackers` as `trackers` (not `rackers`).
