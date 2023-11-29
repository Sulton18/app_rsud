// static/js/author.js
$(document).ready(function() {
    $('#submitBtn').on('click', function() {
        $.ajax({
            type: 'POST',
            url: '/add_blog',
            data: $('#blogForm').serialize(),
            success: function(response) {
                alert('Blog successfully added!');
            },
            error: function(error) {
                console.log(error);
            }
        });
    });
});
