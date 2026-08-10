# Local hosts lists

Put custom `.txt` or `.hosts` lists in this directory. Both common formats are accepted:

```text
127.0.0.1 blocked.example
0.0.0.0 ads.example
plain-domain.example
```

Run `python blocker.py block` as administrator after changing a local list.

Downloaded lists are stored in the ignored `cache/` subdirectory by `python blocker.py updatehosts`.
