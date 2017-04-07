function version(APP_PREFIX) {
	$.get("/"+APP_PREFIX+"/version", function(data) {
		$("#dev-header").append(data);
	});
}