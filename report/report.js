$description = $(".description");
$notification = -1;

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

    /* Welcome message */
    msg = 'Вітаємо!<br>На цій сторінці ви можете отримати коротку інформацію про поширення вірусу SARS-nCov-2 на теренах України та Ізраїлю.<br><br>👉 Щоб отримати інформацію про певний регіон, наведіть на нього вказівник.<br><br>👉 Щоб скопіювати дані, натисність на регіон чи на панель даних.<br><br>Гарного вам дня!';
    nofity(msg, 15000);

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
        left: e.pageX,
        top:  e.pageY - 90
    });
});

$('#footer_content').hover(
    function() {
        $(this).text("🦠👑 навіть тут був коронавірус 👑🦠");
    },
    function() {
        console.log('out');
        $(this).text("😱 ти крейзі? мерщій вдягай маску! 😷");
});

/* Country changed
 * Update total information when user switch between countries
 */
function country_changed(name) {
    switch(name) {
        case 'ukr':
            $('#total').attr('title',     $('#total_ukr').attr('title'));
            $('#total').attr('tested',    $('#total_ukr').attr('tested'));
            $('#total').attr('sick',      $('#total_ukr').attr('sick'));
            $('#total').attr('recovered', $('#total_ukr').attr('recovered'));
            $('#total').attr('dead',      $('#total_ukr').attr('dead'));
            break;

        case 'isr':
            $('#total').attr('title', $('#total_isr').attr('title'));
            $('#total').attr('tested', $('#total_isr').attr('tested'));
            $('#total').attr('sick', $('#total_isr').attr('sick'));
            $('#total').attr('recovered', $('#total_isr').attr('recovered'));
            $('#total').attr('dead', $('#total_isr').attr('dead'));
            break;

        default:
            $('#total').attr('title',     '—');
            $('#total').attr('tested',    '—');
            $('#total').attr('sick',      '—');
            $('#total').attr('recovered', '—');
            $('#total').attr('dead',      '—');
    }

    /* Initialize total data */
    $('#rd_name').html($('#total').attr('title'))
    $('#rd_test').html($('#total').attr('tested'))
    $('#rd_sick').html($('#total').attr('sick'))
    $('#rd_recv').html($('#total').attr('recovered'))
    $('#rd_dead').html($('#total').attr('dead'))
}

/* Copy current region to clipboard.
 * Enable user to copy important info into buffer.
 */
function copy2clipboard(text) {
    var $temp = $("<input>");
    $("body").append($temp);
    $temp.val(text).select();
    document.execCommand("copy");
    $temp.remove();
}

function copy_info() {
    data = '[' + $('#rd_name').text() + ' / ' +
           'перевірені: ' + $('#rd_test').text() + ' / ' +
           'хворі: '      + $('#rd_sick').text() + ' / ' +
           'одужали: '    + $('#rd_recv').text() + ' / ' +
           'померли: '    + $('#rd_dead').text() + ']';

    copy2clipboard(data);
    msg = 'Дані про регіон \"' + $('#rd_name').text() + '\" скопійовано в буфер.';
    nofity(msg, 3000);
}

/* Notification.
 * Create notification to user.
 */
function nofity(text, time) {
    if ($notification != -1) {
        clearTimeout($notification);
    }
    $("#notification").css('display', 'block');
    $("#notification").css('opacity', '1');
    $("#ntf_content").html(text);

    $notification = setTimeout(function(){
        $("#notification").css('opacity', '0');
        $("#notification").css('display', 'none');
        $notification = -1;
    }, time);
}

/* Close notification manually.
 * Allow user to close notification forcefully.
 */
function close_ntf() {
    $("#notification").css('opacity', '0');
    $("#notification").css('display', 'none');
}
