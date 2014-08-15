// JS for creating tables based on user selectedPIDs

var table_handle = "";

function paintTable(username,DT_target){

	table_handle = $('#PIDtable').DataTable( {		
	    "serverSide": true,			    	    
		"ajax": DT_target,		
		"columns": [
			{ 	"searchable": true, 
				"name":"id" 
			},
			{ 	"searchable": true, 
				"name":"PID" 
			},
		    { 	"searchable": true, 
		    	"name":"username",
		    	"visible":false	    	
		    },		    
		    {
		    	"searchable": true,
		    	"name":"status",
		    	"visible":true		    	
		    },
		    { 	"searchable": true, 
		    	"name":"group"		    	    	
		    },
		    {
		    	"name":"actions",
		    	"title":"actions",		    	
		    	"render":function (data,type,row){		    				    		
		    		return "<a href='#' onclick='del_row("+row[0]+"); return false;'>remove</a>";
		    	},
		    	"visible":false    	
		    }	    
		  ],
		searchCols: [
	        null,
	        null,
	        { sSearch: username },	        
	        { sSearch: 1 }, // 1 represents "True" in MySQL, i.e. Selected	        
	        null,
	        null
	    ],	    
		"rowCallback": function( row, data, displayIndex ) {
            if ( data[3] == 1 ) {            	
                $(row).addClass('selected');
            }
        },
        start:1
	} );
	

	// row select toggle
	$('#PIDtable tbody').on('click', 'tr', function () {
	    var id = $(this).children()[0].innerHTML;	    
		$.ajax({
			url: "/PIDRowUpdate/"+id+"/update_status/toggle",			
			}).done(function() {
			$(this).toggleClass('selected');
			table_handle.draw( false ); // false parameter keeps current page
		});
	} );

}

function PIDmanageAction(action){


	if (action == "group_toggle"){		
		data = {"group_name":$("#group_name").val()}
		console.log(data);
		$.ajax({
			url: "/PIDmanageAction/"+action,		
			type:"POST",
			data:data			
			})
		.done(function(response) {
			console.log(response);		
			table_handle.draw( false );			
		});
	}
	
	else {
		$.ajax({
			url: "/PIDmanageAction/"+action,					
			})
		.done(function(response) {
			console.log(response);		
			table_handle.draw( false );			
		});
	}
	
	
}

// delete row
function del_row(id){	
	$.ajax({
		url: "/PIDRowUpdate/"+id+"/delete/delete",			
		}).done(function() {
			$(this).toggleClass('selected');
			table_handle.draw();			
		});
}	

// filter by gruop
function filterGroup(){
	table_handle.column(4).search($("#group_filter").val()).draw(false);
}








