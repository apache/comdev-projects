#!/usr/bin/env bash

cd scripts/cronjobs

python3 podlings.py
python3 parsecommitters.py
python3 parsereleases.py
python3 parsecommitteeinfo.py # slow
python3 parseprojects.py # slow
python3 generaterepos.py
