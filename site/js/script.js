( function( $ ) {
$( document ).ready(function() {
$('#cssmenu').prepend('<div id="bg-one"></div><div id="bg-two"></div><div id="bg-three"></div><div id="bg-four"></div>');

// Load shared nav
$.get('/nav.html', function(html) {
   $('#cssmenu').append(html);
   // Highlight the active page
   var page = location.pathname.split('/').pop() || 'index.html';
   // Map pages to their nav label
   var navMap = {
      'index.html':             'Home',
      '':                       'Home',
      'committees.html':        'Committees',
      'committee.html':         'Committees',
      'projects.html':          'Projects',
      'project.html':           'Projects',
      'datatables.html':        'Projects',
      'releases.html':          'Releases',
      'timelines.html':         'Timelines',
      'about.html':             'About',
      'doap.html':              'About',
      'doapfaq.html':           'About',
      'create.html':            'About',
      'guidelines.html':        'About',
      'pmc_rdf.html':           'About'
   };
   var active = navMap[page];
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
