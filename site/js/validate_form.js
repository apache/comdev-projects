/* validate the fields of the "make_doap" form */
function validate_form ( )
{
    valid = true;

    if ( document.make_doap.std_title.value != "" && document.make_doap.std_id.value == "" )
    {
        alert ( "Please fill in the Implemented Standard 'ID' field." );
        document.make_doap.std_id.placeholder="<required if title provided>";
        document.make_doap.std_id.focus();
        valid = false;
    }

    return valid;
}
