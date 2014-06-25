// javascript for /PIDSolr data tables

// table handle
var table_handle = "";

// paint table
function paintTable(json_output){
	table_handle = $('#PIDtable').DataTable({
		"data":json_output,
		"columns": [
			{ 	"searchable": true, 
				"name":"PID" 
			},
			{ 	"searchable": true, 
				"name":"dc_title",
				"render":function (data,type,row){		    				    		
		    		return "<a target='_blank' href='http://digital.library.wayne.edu/digitalcollections/item?id="+row[0]+"'>"+row[1]+"</a>";
		    	} 
			}
		  ]
	});	

	// selects row
	$('#PIDtable tbody').on('click', 'tr', function () {
	    var PID = $(this).children()[0].innerHTML;	    
	    console.log(PID);
	    $(this).toggleClass('selected');
	});

	// updates
	$('#sendSelPIDs').click( function () {
        // aggregate selected PIDs in list
        var srows = table_handle.rows('.selected').data();
        var PIDs_list = [];
        for (var i=0; i<srows.length; i++){
        	PID = srows[i][0];
        	PIDs_list.push(PID);
        }     
        
        // create json to send
        json_package = JSON.stringify(PIDs_list);
        console.log(json_package);

        // send PIDs to SQL for user
        $.ajax({
			url: "/updatePIDsfromSolr/add",
			type: "POST",
			data: {"json_package":json_package,"group_name":$("#group_name").val()}
		}).done(function(response) { console.log(response); alert("Selected PIDs sent.") });
	});


	$('#sendAllPIDs').click( function () {
        // select all PIDs
        var srows = table_handle.rows().data();
        var PIDs_list = [];
        for (var i=0; i<srows.length; i++){
        	PID = srows[i][0];
        	PIDs_list.push(PID);
        }     
        
        // create json to send
        json_package = JSON.stringify(PIDs_list);        

        // send PIDs to SQL for user
        $.ajax({
			url: "/updatePIDsfromSolr/add",
			type: "POST",
			data: {"json_package":json_package,"group_name":$("#group_name").val()}
		}).done(function(response) { console.log(response); alert("All PIDs sent.") });
	});


	$('#removeSelPIDs').click( function () {
        // aggregate selected PIDs in list
        var srows = table_handle.rows('.selected').data();
        var PIDs_list = [];
        for (var i=0; i<srows.length; i++){
        	PID = srows[i][0];
        	PIDs_list.push(PID);
        }     
        
        // create json to send
        json_package = JSON.stringify(PIDs_list);

        // send PIDs to SQL for user
        $.ajax({
			url: "/updatePIDsfromSolr/remove",
			type: "POST",
			data: {"json_package":json_package,"group_name":$("#group_name").val()}
		}).done(function(response) { console.log(response); alert("Selected PIDs removed.") });
	});


	$('#removeAllPIDs').click( function () {
        // select all PIDs
        var srows = table_handle.rows().data();
        var PIDs_list = [];
        for (var i=0; i<srows.length; i++){
        	PID = srows[i][0];
        	PIDs_list.push(PID);
        }     
        
        // create json to send
        json_package = JSON.stringify(PIDs_list);

        // send PIDs to SQL for user
        $.ajax({
			url: "/updatePIDsfromSolr/remove",
			type: "POST",
			data: {"json_package":json_package,"group_name":$("#group_name").val()}
		}).always(function(response) { 
			console.log(response);
			alert("All PIDs removed."); 
		});
	});



} // close paintTable



