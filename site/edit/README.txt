NOTIE: this feature has been disabled

This directory needs to be sealed off with LDAP auth for committers only. That
way, edit.py will reflect who makes which changes and send the info to the
mailing list.

save.py needs to be enabled as a CGI script in httpd for this to work, and have
write-access to both the site/json/foundation and the site/json/projects
directories in order to save and compile data.