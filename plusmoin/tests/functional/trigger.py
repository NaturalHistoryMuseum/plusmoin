#!/usr/bin/env python
import os
import sys
import json
tr_name = sys.argv[1]
tr_file = sys.argv[2]
if os.path.exists(tr_file):
    with open(tr_file) as f:
        data = json.loads(f.read())
else:
    data = {}
data[tr_name] = json.loads(sys.stdin.read())
with open(tr_file, 'w') as f:
    f.write(json.dumps(data))
