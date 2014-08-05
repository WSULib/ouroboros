// js file for editRELS action


// modify relationship
function modifyRel(self){
	console.log("About to modify...");
	var new_predicate = self.parent().siblings('td.predicate').children('input').val();
	var old_predicate = self.parent().siblings('td.predicate').children('input').attr('name');
	var new_object = self.parent().siblings('td.object').children('input').val();
	var old_object = self.parent().siblings('td.object').children('input').attr('name');

	// send pred / obj to modify_relationship
    $.ajax({
		url: "/fireTask/editRELS_modify_worker",
		type: "POST",
		data: {
			"new_predicate":new_predicate,
			"old_predicate":old_predicate,
			"new_object":new_object,
			"old_object":old_object
		}
	}).done(function(response) { 
		window.location.href="/userJobs";
	});
}


// purge relationship
function removeRel(predicate,object){
	console.log("About to purge...");
	console.log(predicate,object);

	// send pred / obj to purge_relationship
    $.ajax({
		url: "/fireTask/editRELS_purge_worker",
		type: "POST",
		data: {
			"predicate":predicate,
			"object":object
		}
	}).done(function(response) { 
		window.location.href="/userJobs";
	});

}