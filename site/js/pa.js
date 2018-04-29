/* Projects Adverts Javascript */
var request = null;

function createRequestObject() {
  var rqst = null;
  try {
    rqst = new XMLHttpRequest();
  } catch (tryms2) {
    try {
      rqst = new ActiveXObject("Msxml2.XMLHTTP");
    } catch (tryms1) {
      try {
        rqst = new ActiveXObject("Microsoft.XMLHTTP");
      } catch (failed) {
        rqst = null;
      }
    }
  }
  return rqst;
}

evalResponse = function(rq) {
    try {
        return eval('('+rq.responseText+')');
    } catch (e) {}
}

function getAdData()
{
  request = createRequestObject();
  if (request) {
    request.open("GET", "/pa/pa.json");
    request.onreadystatechange = insertAds;
    request.send(null);
  }
}

function insertAds()
{
  if (request.readyState == 4) {
    var json = evalResponse(request);
    if (json) {
      var i;
      for (i = 0; i < json.ads.length; i++) {
        var ad = json.ads[i];
        var div = document.getElementById('ad_' + ad.name);
        if (div) {
          insertAdIntoDiv(div, ad);
        }
      }
    }
  }
}

function insertAdIntoDiv(div, ad)
{
  while (div.firstChild) { div.removeChild(div.firstChild); }
  var a = document.createElement('a');
  a.setAttribute('href', ad.href);
  var img = document.createElement('img');
  img.src = ad.image;
  img.width =ad.width;
  img.height = ad.height;
  img.alt = ad.text;
  img.title = ad.text;
  img.className = 'noborder';
  a.appendChild(img);
  div.appendChild(a);
}

