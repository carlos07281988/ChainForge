"""Add Apache 2.0 license header to all Python files in chainforge/ and tests/."""

import os

HEADER = """# Copyright 2024 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""

COPYRIGHT_CHECK = "# Copyright "  # skip files that already have a copyright line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

count = 0
skipped = 0

for dirname in ("chainforge", "tests"):
    base = os.path.join(ROOT, dirname)
    for root, _dirs, files in os.walk(base):
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as f:
                content = f.read()

            # Skip if already has a copyright notice
            if COPYRIGHT_CHECK in content[:500]:
                skipped += 1
                print(f"  SKIP {os.path.relpath(fpath, ROOT)} (has copyright)")
                continue

            # Insert header before the first line
            # If file starts with """ (docstring), insert before it
            stripped = content.lstrip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Find the actual first non-whitespace line
                lines = content.splitlines(keepends=True)
                indent = len(content) - len(content.lstrip())
                prefix = content[:indent]
                new_content = prefix + HEADER.rstrip("\n") + "\n" + content[indent:]
            else:
                new_content = HEADER + content

            with open(fpath, "w") as f:
                f.write(new_content)
            count += 1
            print(f"  ADD  {os.path.relpath(fpath, ROOT)}")

print(f"\nDone: {count} files updated, {skipped} files skipped (already had copyright).")
