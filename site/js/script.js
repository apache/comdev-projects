// ---- Dark mode -----------------------------------------------------------
// Saved choice ('light' / 'dark') in localStorage, else the system setting.
// Set as early as possible (script.js loads in <head>) to avoid a flash.
(function () {
   var t = null;
   try { t = localStorage.getItem('theme'); } catch (e) {}
   if (t !== 'light' && t !== 'dark') {
      t = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
   }
   document.documentElement.setAttribute('data-theme', t);
})();
function toggleTheme() {
   var t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
   document.documentElement.setAttribute('data-theme', t);
   try { localStorage.setItem('theme', t); } catch (e) {}
   var b = document.getElementById('theme-toggle');
   if (b) b.textContent = t === 'dark' ? '\u2600\uFE0F' : '\u{1F319}';
}

( function( $ ) {
$( document ).ready(function() {
$('#cssmenu').prepend('<div id="bg-one"></div><div id="bg-two"></div><div id="bg-three"></div><div id="bg-four"></div>');

// Hamburger toggle for mobile nav
$('#cssmenu').append('<button id="nav-toggle" aria-label="Menu"><span></span></button>');
$('#nav-toggle').on('click', function(e) {
   e.stopPropagation();
   $('#cssmenu').toggleClass('nav-open');
});
$(document).on('click', function() { $('#cssmenu').removeClass('nav-open'); });

// Load shared nav
$.get('/nav.html', function(html) {
   $('#cssmenu').append(html);
   // dark mode toggle at the right of the menu bar
   var dark = document.documentElement.getAttribute('data-theme') === 'dark';
   $('#cssmenu > ul').append('<li class="theme-li" style="float: right;"><button id="theme-toggle" type="button" ' +
      'title="Switch between light and dark" aria-label="Switch between light and dark">' +
      (dark ? '\u2600\uFE0F' : '\u{1F319}') + '</button></li>');
   $('#theme-toggle').on('click', function (e) { e.stopPropagation(); toggleTheme(); });
   // Highlight the active page
   var page = location.pathname.split('/').pop() || 'index.html';
   // Map pages to their nav label
   var navMap = {
      'index.html':             'Home',
      '':                       'Home',
      'chooser.html':           'Choose a project',
      'committees.html':        'Committees',
      'committee.html':         'Committees',
      'projects.html':          'Projects',
      'project.html':           'Projects',
      'datatables.html':        'Projects',
      'releases.html':          'Releases',
      'graphs.html':            'Graphs',
      'timelines.html':         'Graphs',
      'validation-report.html': 'About',
      'about.html':             'About',
      'doap.html':              'About',
      'doapfaq.html':           'About',
      'create.html':            'About',
      'guidelines.html':        'About',
      'pmc_rdf.html':           'About'
   };
   var active = navMap[page];
   if (location.pathname.indexOf('/metrics') === 0) active = 'Metrics';   // comdev-metrics pages
   if (active) {
      $('#cssmenu ul li a span').each(function() {
         if ($(this).text() === active) {
            $(this).closest('li').addClass('active');
         }
      });
   }
});
});
} )( jQuery );

// Fallback for the menu bar's search box on pages that don't load
// projects.js (chooser.html, the /metrics/ pages): send the search to
// the projects list. Pages that do load projects.js replace this with
// its own checkKeyPress, which searches in place.
function checkKeyPress(e, txt) {
   if (!e) e = window.event;
   var keyCode = e.keyCode || e.which;
   if (keyCode == 13 && txt.value) {
      location.href = '/projects.html?search=' + encodeURIComponent(txt.value);
   }
}
