$(function() {
  if (!localStorage.getItem("pageSearch")) { 
    $.getJSON("/ouroboros/routeIndexer",function(data) { 
    // Set to localStorage for easy retrieval
    localStorage.setItem("pageSearch", JSON.stringify(data));
    });
  } 
 
  var availablePages = JSON.parse(localStorage.getItem("pageSearch"));

  $(".autocomplete").autocomplete({
    source: availablePages
  }).data("ui-autocomplete")._renderItem = function (ul, item) {
    return $("<li></li>")
        .data("item.autocomplete", item)
        .append('<div><button><a class="ac-item-a" href="//' + item.url + '" target="_blank">' + item.label + '</a></button></div>')
        .appendTo(ul);

};

$(".page_searcher").keypress(function(e) {
  if(e.which == 13) {
    console.log("yeppers");
  $(".autocomplete").autocomplete({
        source: availablePages
      }).data("ui-autocomplete")._renderItem = function (ul, item) {
    return $("<li></li>")
        .data("item.autocomplete", item)
        .append('<div><button><a class="ac-item-a" href="//' + item.url + '" target="_blank">' + item.label + '</a></button></div>')
        .appendTo(ul);
      }
  } //enter key
}) //keypress


});