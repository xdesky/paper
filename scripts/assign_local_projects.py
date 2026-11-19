#!/usr/bin/env python3
"""Explicitly assign pre-account local projects to a registered account."""
import argparse,sqlite3
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--data-dir',type=Path,default=Path('.data'))
p.add_argument('--email',required=True)
p.add_argument('--apply',action='store_true',help='Apply assignment; otherwise preview only')
a=p.parse_args()
dbpath=a.data_dir/'studio.sqlite3'
if not dbpath.exists():p.error('Database does not exist')
with sqlite3.connect(dbpath) as db:
    db.execute('BEGIN IMMEDIATE')
    account=db.execute('SELECT id FROM accounts WHERE email=?',(a.email.strip().lower(),)).fetchone()
    if not account:p.error('Register this account first')
    rows=db.execute('SELECT id,name FROM projects WHERE owner_id IS NULL').fetchall()
    for pid,name in rows:print(pid,name)
    print(f'{len(rows)} unassigned projects -> {a.email}')
    if a.apply:
        db.execute('UPDATE projects SET owner_id=? WHERE owner_id IS NULL',(account[0],))
        print('Assignment saved. Existing owned projects were not changed.')
    else:print('Preview only. Add --apply to save this assignment.')
