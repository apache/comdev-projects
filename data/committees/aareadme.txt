The files in this directory are PMC descriptor files

When adding files to this directory, please ensure that the list in the file
  ../committees.xml
is also updated.

All the files in this directory must have the extension '.rdf' and the file name must be the same
as the committee name. [This may not be the same as the website host name initial component.] 
The file stem must match the asfext:pmc tag, for example:
The file abcd.rdf must contain the tag: 
  <asfext:pmc rdf:about="abcd">

The PMC descriptor files in this directory can be referenced in a project DOAP using the shorthand:
    <asfext:pmc rdf:resource="http://httpd.apache.org/"/>
rather than needing to use the full URL.

Note: PMC descriptor files can alternatively be stored elsewhere. If so, the name can be anything.
However the extension must be '.rdf' and the asfext:pmc tag must be the committee name.

In this case please ensure that the 'rdf:resource' attribute in the DOAP contains the full URL of the PMC rdf file

For example:

The PMC descriptor file for the HTTPD project is currently stored in this directory (see ../committees.xml).
There are currently two DOAPs for HTTPD (see ../projects.xml):
http://svn.apache.org/repos/asf/httpd/site/trunk/content/doap.rdf
http://svn.apache.org/repos/asf/httpd/site/trunk/content/mod_ftp/doap.rdf
These DOAPs contain the shorthand entry:
    <asfext:pmc rdf:resource="http://httpd.apache.org" />

By contrast, the PMC descriptor file for Flex is stored at:
http://flex.apache.org/pmc_Flex.rdf
There is a project DOAP at
http://flex.apache.org/doap_Flex.rdf
This contains the entry:
    <asfext:pmc rdf:resource="http://flex.apache.org/pmc_Flex.rdf" />

N.B. These files were previously stored under
https://svn.apache.org/repos/asf/infrastructure/site-tools/trunk/projects/data_files
and were listed in
https://svn.apache.org/repos/asf/infrastructure/site-tools/trunk/projects/pmc_list.xml