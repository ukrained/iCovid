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

    $('#rd_test').attr('text', $('#total').attr('tested'))
    $('#rd_sick').attr('text', $('#total').attr('sick'))
    $('#rd_recv').attr('text', $('#total').attr('recovered'))
    $('#rd_dead').attr('text', $('#total').attr('dead'))

    $('#rd_test').attr('delta', $('#total').attr('d_tested'))
    $('#rd_sick').attr('delta', $('#total').attr('d_sick'))
    $('#rd_recv').attr('delta', $('#total').attr('d_recovered'))
    $('#rd_dead').attr('delta', $('#total').attr('d_dead'))

    /* Welcome message */
    msg = 'Вітаємо!<br>На цій сторінці ви можете отримати коротку інформацію про поширення вірусу SARS-nCov-2 на теренах України та країн світу.<br><br>👉 Щоб отримати інформацію про певний регіон, наведіть на нього вказівник.<br><br>👉 Щоб побачити зміну кількості осіб відносно попередньої доби, наведіть на значення потрібного критерію.<br><br>👉 Щоб скопіювати дані, натисність на регіон чи на його назву у панелі даних.<br><br>Гарного вам дня!';
    notify(msg, 15000);

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

$('.delta').hover(
    function() {
        delta = parseInt($(this).attr('delta'));
        if (delta > 0) {
            $(this).css("background-color", "lightcoral");
        } else {
            $(this).css("background-color", "lightgreen");
        }

        sign = delta > 0 ? '🔼 ' : '🔽 ';
        num = delta > 0 ? delta : -delta;
        $(this).text(sign + num);
    },
    function() {
        $(this).css("background-color", "white");
        $(this).text($(this).attr('text'));
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
        $(this).text("😱 ти крейзі? мерщій вдягай маску! 😷");
});

/* Country changed
 * Update total information when user switch between countries
 */
function country_changed(name) {
    node_id = '#total_' + name;

    if ($(node_id).length > 0) {
        $('#total').attr('title',     $(node_id).attr('title'));
        $('#total').attr('tested',    $(node_id).attr('tested'));
        $('#total').attr('sick',      $(node_id).attr('sick'));
        $('#total').attr('recovered', $(node_id).attr('recovered'));
        $('#total').attr('dead',      $(node_id).attr('dead'));

        $('#total').attr('d_tested',    $(node_id).attr('d_tested'));
        $('#total').attr('d_sick',      $(node_id).attr('d_sick'));
        $('#total').attr('d_recovered', $(node_id).attr('d_recovered'));
        $('#total').attr('d_dead',      $(node_id).attr('d_dead'));
    } else {
        $('#total').attr('title',     '—');
        $('#total').attr('tested',    '—');
        $('#total').attr('sick',      '—');
        $('#total').attr('recovered', '—');
        $('#total').attr('dead',      '—');

        $('#total').attr('d_tested',    '—');
        $('#total').attr('d_sick',      '—');
        $('#total').attr('d_recovered', '—');
        $('#total').attr('d_dead',      '—');
    }

    /* Initialize total data */
    $('#rd_name').html($('#total').attr('title'));
    $('#rd_test').html($('#total').attr('tested'));
    $('#rd_sick').html($('#total').attr('sick'));
    $('#rd_recv').html($('#total').attr('recovered'));
    $('#rd_dead').html($('#total').attr('dead'));

    $('#rd_test').attr('delta', $('#total').attr('d_tested'));
    $('#rd_sick').attr('delta', $('#total').attr('d_sick'));
    $('#rd_recv').attr('delta', $('#total').attr('d_recovered'));
    $('#rd_dead').attr('delta', $('#total').attr('d_dead'));
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
    data = ' У регіоні "' + $('#rd_name').text() + '" ' +
           'перевірили '  + $('#rd_test').text() + ' осіб, ' +
           'захворіли '   + $('#rd_sick').text() + ' осіб, ' +
           'одужали '     + $('#rd_recv').text() + ' осіб та ' +
           'померли '     + $('#rd_dead').text() + ' осіб. ';

    copy2clipboard(data);
    msg = 'Дані про регіон \"' + $('#rd_name').text() + '\" скопійовано в буфер.';
    notify(msg, 3000);
}

/* Notification.
 * Create notification to user.
 */
function notify(text, time) {
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
