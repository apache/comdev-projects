#!/bin/sh
# This is a simple data verification script which checks that the files
# in committees/ are the same, in number, as those referenced in
# committeex.xml  It would be nice to also verify that they are the
# *same* files.

echo 1: How many files in committees/ directory?
ls committees/*.rdf | grep -v template.rdf | wc -l

echo 2: And how many in committes.xml?
grep location committees.xml | grep -v Retired | wc -l

echo 3: Except that some of those entries are external sources
grep location committees.xml | grep -v Retired | grep "location>http" | wc -l

echo Verify: Item 1 should be item 2 plus item 3
