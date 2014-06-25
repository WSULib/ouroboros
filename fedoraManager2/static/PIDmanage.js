// JS for creating tables based on user selectedPIDs

var table_handle = "";

function paintTable(username){

	table_handle = $('#PIDtable').DataTable( {		
	    "serverSide": true,			    	    
		"ajax": 'http://162.243.93.130/cgi-bin/php_simple.php',		
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
		    	"name":"status",
		    	"visible":false
		    },
		    { 	"searchable": true, 
		    	"name":"group"		    	    	
		    },
		    {
		    	"name":"actions",
		    	"title":"actions",		    	
		    	"render":function (data,type,row){		    				    		
		    		return "<a href='#' onclick='del_row("+row[0]+"); return false;'>remove</a>";
		    	}		    	
		    }	    
		  ],
		searchCols: [
	        null,
	        null,	        
	        { sSearch: username },
	        null,
	        null,
	        null
	    ],	    
		"rowCallback": function( row, data, displayIndex ) {
            if ( data[3] == "selected" ) {            	
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

	


 
    // $('#button').click( function () {
    //     alert( table.rows('.selected').data().length +' row(s) selected' );
    // } );

	// don't need, but might be worth saving
	// var cpage = table_handle.page();
	// console.log(cpage);
	// table_handle.draw();
	// $("a.paginate_button.current").click();					

	// LEAVE FOR REFERENCE, searchCols WORKING ABOVE PER BUG FIX IN DATATABLES
	// filter only the user
	// https://datatables.net/forums/discussion/comment/61834#Comment_61834
	// table_handle.columns(2).search(username).draw();	
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








