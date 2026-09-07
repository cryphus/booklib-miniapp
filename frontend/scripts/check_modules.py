#!/usr/bin/env python3
"""Static check of the frontend's ES-module graph.

The app has no build step (see README), so a broken relative import or a named import
that doesn't exist in its target module would otherwise only surface at runtime in a
browser. This walks every `src/**/*.js` file and verifies:

  1. every `from './relative/path.js'` resolves to a file that actually exists;
  2. every named import (`import { foo } from '...'`) is actually exported by that file.

Run from the `frontend/` directory:

    python scripts/check_modules.py

Exits non-zero (with the offending imports listed) if anything doesn't resolve, so CI can
use it as a gate. This is deliberately a regex-based check, not a real JS parser — it
covers the two ways this codebase has actually broken (typo'd path, renamed export) without
pulling in a JS toolchain for a project that otherwise has none.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

IMPORT_PATH_RE = re.compile(r"from\s+'(\.[^']+)'")
NAMED_IMPORT_RE = re.compile(r"import\s*\{([^}]*)\}\s*from\s*'(\.[^']+)'", re.S)
EXPORT_DECL_RE = re.compile(r"export\s+(?:async\s+)?(?:function|const|class|let)\s+(\w+)")
EXPORT_LIST_RE = re.compile(r"export\s*\{([^}]*)\}")


def collect_exports(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    names = {m.group(1) for m in EXPORT_DECL_RE.finditer(source)}
    for match in EXPORT_LIST_RE.finditer(source):
        for part in match.group(1).split(","):
            part = part.strip().split(" as ")[-1].strip()
            if part:
                names.add(part)
    return names


def main() -> int:
    files = sorted(SRC.rglob("*.js"))
    if not files:
        print(f"no .js files found under {SRC}", file=sys.stderr)
        return 1

    exports_by_file = {f.resolve(): collect_exports(f) for f in files}

    missing_files: list[str] = []
    bad_named_imports: list[str] = []

    for path in files:
        source = path.read_text(encoding="utf-8")

        for match in IMPORT_PATH_RE.finditer(source):
            target = (path.parent / match.group(1)).resolve()
            if not target.exists():
                missing_files.append(f"{path.relative_to(SRC.parent)} -> {match.group(1)}")

        for match in NAMED_IMPORT_RE.finditer(source):
            target = (path.parent / match.group(2)).resolve()
            if target not in exports_by_file:
                continue
            for part in match.group(1).split(","):
                name = part.strip().split(" as ")[0].strip()
                if name and name not in exports_by_file[target]:
                    bad_named_imports.append(
                        f"{path.relative_to(SRC.parent)}: '{name}' not exported by {match.group(2)}"
                    )

    print(f"проверено модулей: {len(files)}")

    if missing_files:
        print(f"\nБИТЫЕ ПУТИ ИМПОРТА ({len(missing_files)}):")
        for entry in missing_files:
            print(f"  {entry}")

    if bad_named_imports:
        print(f"\nНЕСУЩЕСТВУЮЩИЕ ИМЕНОВАННЫЕ ЭКСПОРТЫ ({len(bad_named_imports)}):")
        for entry in bad_named_imports:
            print(f"  {entry}")

    if missing_files or bad_named_imports:
        return 1

    print("граф импортов в порядке")
    return 0


if __name__ == "__main__":
    sys.exit(main())
