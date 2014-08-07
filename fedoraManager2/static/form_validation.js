$(document).ready(function() {
	$('#form').bootstrapValidator({
		// To use feedback icons, ensure that you use Bootstrap v3.1.0 or later
		feedbackIcons: {
			valid: 'glyphicon glyphicon-ok',
			invalid: 'glyphicon glyphicon-remove',
			validating: 'glyphicon glyphicon-refresh'
		},
		fields: {
			dsID: {
				validators: {
					notEmpty: {
						message: 'You must select a datastream'
					}
				}
			},
			altIDs: {
				validators: {
					notEmpty: {
						message: 'You must give the datastream an alternate ID'
					}
				}
			},
			dsLabel: {
				validators: {
					notEmpty: {
						message: 'You must give the datastream a label'
					}
				}
			},
			MIMEType: {
				validators: {
					notEmpty: {
						message: 'You must give the datastream a MIME-Type'
					}
				}
			},
			dsLocation: {
				validators: {
					uri: {
						allowlocal: true,
						message: 'The website address is not valid'
					}
				}
			},
			dataType: {
				validators: {
					notEmpty: {
						message: 'You must give select where your data is coming from'
					}
				}
			},
			startDT: {
				validators: {
					regexp: {
						regexp: /^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]{2,3}Z/,
						message: 'Not valid format'
					}
				}
			},
			endDT: {
				validators: {
					regexp: {
						regexp: /^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]{2,3}Z/,
						message: 'Not valid format'
					}
				}
			},
			logMessage: {
				validators: {
					regexp: {
						regexp: /^.{0,100}$/,
						message: 'exceeded the log message length allowed'
					}
				}
			},
			force: {
				validators: {
					regexp: {
						regexp: /true$|false$/i,
						message: 'enter in either true or false'
					}
				}
			},
		}
	});
});

$(document).ready(function() {
$( ".dataType" ).change(function() {
	$(".dataTypes").hide();
	$("#" + $(this).val()).show();
	});
});