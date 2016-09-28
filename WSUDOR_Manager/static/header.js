// route autocomplete
// $(function() {
//   if (!localStorage.getItem("pageSearch")) { 
//     $.getJSON("/ouroboros/routeIndexer",function(data) { 
//     // Set to localStorage for easy retrieval
//     localStorage.setItem("pageSearch", JSON.stringify(data));
//     });
//   } 
 
//   var availablePages = JSON.parse(localStorage.getItem("pageSearch"));
//   var selected_item = "";

//   $(".autocomplete").autocomplete({
//       source: availablePages
//     }).data("ui-autocomplete")._renderItem = function (ul, item) {
//       selected_item = item;
//       return $("<li></li>")
//           .data("item.autocomplete", item)
//           .append('<div><button><a class="ac-item-a" href="//' + item.url + '" target="_blank">' + item.label + '</a></button></div>')
//           .appendTo(ul);

//   };

//   $(".page_searcher").keypress(function(e) {
//     if(e.which == 13) {
//       window.location = '//' + selected_item.url;
//     } //enter key
//   }) //keypress
// });