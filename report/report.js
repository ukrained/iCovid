
$description = $(".description");

$(document).ready(function(){
    /* Hack for ZZZ hosting */
    divs = document.body.getElementsByTagName("div")
    if (divs[0] && divs[0].childElementCount != 1) {
        document.body.removeChild(divs[0]);
    }

    cbalinks = document.body.getElementsByClassName("cbalink")
    if (cbalinks[0]) {
        document.body.removeChild(cbalinks[0]);
    }

    /* Initialize total data */
    $('#rd_name').html($('#total').attr('title'))
    $('#rd_test').html($('#total').attr('tested'))
    $('#rd_sick').html($('#total').attr('sick'))
    $('#rd_recv').html($('#total').attr('recovered'))
    $('#rd_dead').html($('#total').attr('dead'))
});

$('.enabled').hover(
    function() {
        $(this).attr("class", "land enabled");
        $description.addClass('active');
        $description.html($(this).attr('title'));

        $('#rd_name').html($(this).attr('title'))
        $('#rd_test').html($(this).attr('tested'))
        $('#rd_sick').html($(this).attr('sick'))
        $('#rd_recv').html($(this).attr('recovered'))
        $('#rd_dead').html($(this).attr('dead'))
    },
    function() {
        $description.removeClass('active');
        $('#rd_name').html($('#total').attr('title'))
        $('#rd_test').html($('#total').attr('tested'))
        $('#rd_sick').html($('#total').attr('sick'))
        $('#rd_recv').html($('#total').attr('recovered'))
        $('#rd_dead').html($('#total').attr('dead'))
    });

$(document).on('mousemove', function(e){
    $description.css({
        left:  e.pageX,
        top:   e.pageY - 90
    });
});

$('.footer').hover(
    function() {
        $('.footer').html("<p>🦠👑 тут був коронавірус 👑🦠</p>");
    },
    function() {
        $('.footer').html("<p>Компанія \"Вирій\" 🦠 2020</p>");
    });
