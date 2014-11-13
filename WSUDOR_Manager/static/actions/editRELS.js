// js file for editRELS action

// modify relationship
function modifyRel(self){
	console.log("About to modify...");
	var new_predicate = self.parent().siblings('td.predicate').children('input').val();
	var old_predicate = self.parent().siblings('td.predicate').children('input').attr('name');
	var new_object = self.parent().siblings('td.object').children('input').val();
	var old_object = self.parent().siblings('td.object').children('input').attr('name');	

	// create and submit form (results in redirect)
	var url = "/fireTask/editRELS_modify_worker";

	var form = $('<form action="' + url + '" method="POST">' +
	'<input type="hidden" name="new_predicate" value="' + new_predicate + '" />' +
	'<input type="hidden" name="old_predicate" value="' + old_predicate + '" />' +
	'<input type="hidden" name="new_object" value="' + new_object + '" />' +
	'<input type="hidden" name="old_object" value="' + old_object + '" />' +
	'</form>');
	
	// submit
	form.submit();	
}


// purge relationship
function removeRel(predicate,object){
	console.log("About to purge...");
	console.log(predicate,object);

	// create and submit form (results in redirect)
	var url = "/fireTask/editRELS_purge_worker";

	var form = $('<form action="' + url + '" method="POST">' +
	'<input type="hidden" name="predicate" value="' + predicate + '" />' +
	'<input type="hidden" name="object" value="' + object + '" />' +	
	'</form>');
	
	// submit
	form.submit();

}
