// $(document).ready(function () {


//     // make buttons appear on hover
//     // $(document).on('mouseenter', '.problemImg', function () {
//     //     $(this).find(":button").show();
//     // }).on('mouseleave', '.problemImg', function () {
//     //     $(this).find(":button").hide();
//     // });


//     // add to workspace and remove object button actions
//     $(function(APP_HOST)
//     {
//         $(document).on('click', '.btn', function(e)
//         {
//             e.preventDefault();
//             button = this.id;
//             var pid = $(this).closest("div").attr("id");
//             console.log(pid);
//             console.log(button);
//             if (button == "removeButton") {
//                 var action="removeObj";
//             }
//             console.log(action);
//             console.log(action);
//             $.ajax({
//                 url: "/"+APP_PREFIX+"/"+action,
//                 type: "POST"
//             }).done(function(response) { console.log(response); alert("Selected PIDs removed.") });

//             });

//     //         var controlForm = $('.controls form:first'),
//     //             currentEntry = $(this).parents('.entry:first'),
//     //             newEntry = $(currentEntry.clone()).appendTo(controlForm);

//     //         newEntry.find('input').val('');
//     //         controlForm.find('.entry:not(:last) .btn-add')
//     //             .removeClass('btn-add').addClass('btn-remove')
//     //             .removeClass('btn-success').addClass('btn-danger')
//     //             .html('<span class="glyphicon glyphicon-minus"></span>');
//     //     }).on('click', '.btn-remove', function(e)
//     //     {
//     //      $(this).parents('.entry:first').remove();

//          return false;
//      });
//     });


