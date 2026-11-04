#!/bin/bash
cd "$(dirname "$0")"
mkdir -p out
python3 ev.py GA UT WA VA >/dev/null
python3 clarity.py CO IA >/dev/null
for m in hawaii nc fl pa inn nv ct md la ny de vt; do python3 $m.py >/dev/null || echo "FAIL $m"; done
python3 civix.py NE SD MT NM >/dev/null
python3 tally.py AR >/dev/null
python3 orv.py >/dev/null
for m in $EXTRA; do python3 $m.py >/dev/null || echo "FAIL $m"; done
rm -rf build/results; python3 assemble.py build/results
