#!/usr/bin/env bash

cd scripts/cronjobs

python3 podlings.py
python3 parsecommitters.py
python3 parsereleases.py
python3 parsecommitteeinfo.py
python3 parseprojects.py
python3 generaterepos.py
