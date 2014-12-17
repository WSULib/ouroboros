// Add a new repeating section
$(document).ready(function(){
// Add a new repeating section
var attrs = ['for', 'id', 'name'];
function resetAttributeNames(section) {
	console.log(section);

    var tags = section.find('input, label'), idx = $('.datastream').length - 1;
    console.log(idx);
    tags.each(function() {
      var $this = $(this);
      $.each(attrs, function(i, attr) {
        var attr_val = $this.attr(attr);
        if (attr_val) {
            $this.attr(attr, attr_val.replace(/_\d+$/, '_'+(idx + 1)));
        }
      });
    });
}
                   
$('.addDS').click(function(e){
        e.preventDefault();
        var lastRepeatingGroup = $('.datastream').last();
        var cloned = lastRepeatingGroup.clone(true);
        cloned.find("input").val("");
    cloned.find("input:radio").attr("checked", false);
        cloned.insertAfter(lastRepeatingGroup);
        resetAttributeNames(cloned);
    });
                    
// Delete a repeating section
$('.deleteDS').click(function(e){
        e.preventDefault();
        var current = $(this).parent('div');
        var other = current.siblings('.datastream');
        if (other.length === 0) {
            alert("You should at least have one datastream");
            return;
        }
        current.slideUp('slow', function() {
            current.remove();
            
            // reset fight indexes
            other.each(function() {
               resetAttributeNames($(this));
            });
            
        });
                    
    });
});