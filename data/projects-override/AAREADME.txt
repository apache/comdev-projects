This directory contains copies of DOAPs from retired projects.

It's awkward for Attic people to get temporary access to change the DOAPs to mark them as
retired, and the original project committers are usually unavailable.

So a simpler solution is to take a copy here, and update that (all committers have access)
The projects.xml file can then be updated to point to the override file.

If necessary, the original DOAP can be updated at a later data, and the override dropped.

Note that PMCs can have multiple DOAPs, so the files are prefixed with the PMC name.

How to update the DOAP:
- add a comment <!-- Copied from URL -->
- update <asfext:pmc rdf:resource="http://attic.apache.org" />
- add <category rdf:resource="http://projects.apache.org/category/retired" />

Update project.xml:
- comment the original DOAP import, e.g.
  <!-- retired: location>https://svn.apache.org/repos/asf/falcon/trunk/falcon.rdf</location -->
- add the new DOAP URL:
  <location>https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects-override/falcon.rdf</location>

Now commit the changes
