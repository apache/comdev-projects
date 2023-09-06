/* validate the fields of the "make_doap" form */
function validate_form ( )
{
    valid = true;

    if ( document.make_doap.name.value == "" )
    {
        alert ( "Please fill in the project name field." );
        document.make_doap.name.focus();
        valid = false;
    }

    if ( document.make_doap.pmc.value == "" )
    {
        alert ( "Please fill in the PMC name field." );
        document.make_doap.pmc.focus();
        valid = false;
    }

    if ( document.make_doap.sdesc.value == "" )
    {
        alert ( "Please fill in the short description field." );
        document.make_doap.sdesc.focus();
        valid = false;
    }

    if ( document.make_doap.ldesc.value == "" )
    {
        alert ( "Please fill in the long description field." );
        document.make_doap.ldesc.focus();
        valid = false;
    }

    if ( document.make_doap.std_title.value != "" && document.make_doap.std_id.value == "" )
    {
        alert ( "Please fill in the Implemented Standard 'ID' field." );
        document.make_doap.std_id.placeholder="<required if title provided>";
        document.make_doap.std_id.focus();
        valid = false;
    }

    return valid;
}
