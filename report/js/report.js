$description = $(".description");
$notification = -1;
$modal_isopen = false;
$test_chart = null;
$sick_chart = null;
$recv_chart = null;
$dead_chart = null;

$(document).ready(function(){
    /* Hack for ZZZ hosting */
    /*
        <div style="text-align:center;font-size:11px;font-family:arial;background-color:black;color:white">
            Ця сторінка розміщена безкоштовно на
            <a style="color:grey" rel="nofollow" href="https://www.zzz.com.ua/">
                zzz.com.ua
            </a>,
            якщо Ви власник цієї сторінки, Ви можете прибрати це повідомлення та отримати доступ до безлічі додаткових послуг та переваг при покращенні Вашого хостингу до PRO або VIP усього за 41.60 UAH.
        </div>
    */
    divs = document.body.getElementsByTagName("div")
    if (divs[0] && divs[0].getElementsByTagName("a").length > 0) {
        document.body.removeChild(divs[0]);
    }

    cbalinks = document.body.getElementsByClassName("cbalink")
    if (cbalinks[0]) {
        document.body.removeChild(cbalinks[0]);
    }

    /* Initialize total data */
    country_changed('ukr');

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

        $('#rd_name').attr('text', $(this).attr('title'));
        $('#rd_test').attr('text', $(this).attr('tested'));
        $('#rd_sick').attr('text', $(this).attr('sick'));
        $('#rd_recv').attr('text', $(this).attr('recovered'));
        $('#rd_dead').attr('text', $(this).attr('dead'));

        $('#rd_sick').attr('delta', $(this).attr('d_sick'));
    },
    function() {
        $description.removeClass('active');
        $('#rd_name').html($('#total').attr('title'))
        $('#rd_test').html($('#total').attr('tested'))
        $('#rd_sick').html($('#total').attr('sick'))
        $('#rd_recv').html($('#total').attr('recovered'))
        $('#rd_dead').html($('#total').attr('dead'))

        $('#rd_name').attr('text', $('#total').attr('title'));
        $('#rd_test').attr('text', $('#total').attr('tested'));
        $('#rd_sick').attr('text', $('#total').attr('sick'));
        $('#rd_recv').attr('text', $('#total').attr('recovered'));
        $('#rd_dead').attr('text', $('#total').attr('dead'));

        $('#rd_sick').attr('delta', $('#total').attr('d_sick'));
});

$('.delta').hover(
    function() {
        /* Delta direction for positive and negative parameters: 1 - positive, 0 - negative */
        delta_dir = parseInt($(this).attr('d_dir'));

        delta = parseInt($(this).attr('delta'));
        if (delta > 0) {
            if (delta_dir == 0) {
                $(this).css("background-color", "lightcoral");
            } else {
                $(this).css("background-color", "lightgreen");
            }
        } else {
            if (delta_dir == 1) {
                $(this).css("background-color", "lightcoral");
            } else {
                $(this).css("background-color", "lightgreen");
            }
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
        $(this).text("🎄 Вітаємо з Новим Роком 2021 ☃️");
    },
    function() {
        $(this).text("Компанія \"Вирій\" ❄️ 2021");
});

/* Country changed
 * Update total information when user switch between countries
 */
function country_changed(name) {
    node_id = '#total_' + name;

    if ($(node_id).length > 0) {
        /* General information */
        $('#total').attr('title',     $(node_id).attr('title'));
        $('#total').attr('tested',    $(node_id).attr('tested'));
        $('#total').attr('sick',      $(node_id).attr('sick'));
        $('#total').attr('recovered', $(node_id).attr('recovered'));
        $('#total').attr('dead',      $(node_id).attr('dead'));

        /* Delta per day */
        $('#total').attr('peak',        $(node_id).attr('peak'));
        $('#total').attr('d_tested',    $(node_id).attr('d_tested'));
        $('#total').attr('d_sick',      $(node_id).attr('d_sick'));
        $('#total').attr('d_recovered', $(node_id).attr('d_recovered'));
        $('#total').attr('d_dead',      $(node_id).attr('d_dead'));

        /* Data for charts */
        $('#total').data('days', $(node_id).data('days'));
        $('#total').data('test', $(node_id).data('test'));
        $('#total').data('sick', $(node_id).data('sick'));
        $('#total').data('recv', $(node_id).data('recv'));
        $('#total').data('dead', $(node_id).data('dead'));

        /* Data for details */
        $('#total').data('regs', $(node_id).data('regs'));
        $('#total').attr('popl', $(node_id).attr('popl'));
        $('#total').attr('area', $(node_id).attr('area'));
        $('#total').attr('dens', $(node_id).attr('dens'));
        $('#total').attr('desc', $(node_id).attr('desc'));

        /* Data for cure timeline */
        $('#total').attr('cure', $(node_id).attr('cure'));

    } else {
        /* General information */
        $('#total').attr('title',     '—');
        $('#total').attr('tested',    '—');
        $('#total').attr('sick',      '—');
        $('#total').attr('recovered', '—');
        $('#total').attr('dead',      '—');

        /* Delta per day */
        $('#total').attr('peak',        '—');
        $('#total').attr('d_tested',    '—');
        $('#total').attr('d_sick',      '—');
        $('#total').attr('d_recovered', '—');
        $('#total').attr('d_dead',      '—');

        /* Data for charts */
        $('#total').data('days',   '[]');
        $('#total').data('test',   '[]');
        $('#total').data('sick',   '[]');
        $('#total').data('recv',   '[]');
        $('#total').data('dead',   '[]');

        /* Data for details */
        $('#total').data('regs', '[]');
        $('#total').attr('popl', '—');
        $('#total').attr('area', '—');
        $('#total').attr('dens', '—');
        $('#total').attr('desc', '—');

        /* Data for cure timeline */
        $('#total').attr('cure', '0');
    }

    /* Initialize total data */
    $('#rd_name').html($('#total').attr('title'));
    $('#rd_test').html($('#total').attr('tested'));
    $('#rd_sick').html($('#total').attr('sick'));
    $('#rd_recv').html($('#total').attr('recovered'));
    $('#rd_dead').html($('#total').attr('dead'));

    /* Update text attribute */
    $('#rd_test').attr('text', $('#total').attr('tested'));
    $('#rd_sick').attr('text', $('#total').attr('sick'));
    $('#rd_recv').attr('text', $('#total').attr('recovered'));
    $('#rd_dead').attr('text', $('#total').attr('dead'));

    /* Update delta attribute */
    $('#rd_test').attr('delta', $('#total').attr('d_tested'));
    $('#rd_sick').attr('delta', $('#total').attr('d_sick'));
    $('#rd_recv').attr('delta', $('#total').attr('d_recovered'));
    $('#rd_dead').attr('delta', $('#total').attr('d_dead'));

    /* Copy peak value per region */
    $('#rd_peak').html('👨🏻‍⚕️ ' + $('#total').attr('peak'));

    /* Redraw all the charts */
    if ($modal_isopen) {
        redraw_chart('test');
        redraw_chart('sick');
        redraw_chart('recv');
        redraw_chart('dead');
    }

    /* Update region data */
    update_region_details(name);

    /* Update region statistics */
    update_region_stats(name);
}

/* Function gives color for some percentage level
 *
 * percent - actual percentage
 * less_better - flag tells that smaller percent is better
 */
function colorize_percent(percent, less_better=false) {
    var r, g, b = 0;

    percent = percent > 100.0 ? 100.0 : (percent < 0.0 ? 0.0 : percent);

    /* Reverse percent value if less is better */
    if (less_better) {
        percent = 100.0 - percent;
    }

	if(percent < 50) {
		r = 255;
		g = Math.round(5.1 * percent);
	} else {
		g = 255;
		r = Math.round(510 - 5.10 * percent);
	}
	var h = r * 0x10000 + g * 0x100 + b * 0x1;
	return '#' + ('000000' + h.toString(16)).slice(-6);
}

function min_max_level_get(min_v, max_v, range, value)
{
    var step = (max_v - min_v) / range;
    var level = Math.floor((value - min_v) / step);

    level = level < 0 ? 0 : (level >= range ? range - 1 : level);

    return level;
}

function update_region_stats(name)
{
    var i = 0;

    tsiv_tested = (parseInt($('#total').attr('tested')) / parseInt($('#total').attr('popl').replace(/,/g, '')) * 100).toFixed(2);
    $('#tsiv_tested').html(tsiv_tested + ' %');
    // style="width: 13%; background-color: #f63a0f;"
    $('#pb_tested').css('width', tsiv_tested + '%');
    $('#pb_tested').css('background-color', colorize_percent(tsiv_tested));

    tsiv_sick = (parseInt($('#total').attr('sick')) / parseInt($('#total').attr('popl').replace(/,/g, '')) * 100).toFixed(2);
    $('#tsiv_sick').html(tsiv_sick + ' %');
    $('#pb_sick').css('width', tsiv_sick + '%');
    $('#pb_sick').css('background-color', colorize_percent(tsiv_sick, true));

    tsiv_recovered = (parseInt($('#total').attr('recovered')) / parseInt($('#total').attr('sick')) * 100).toFixed(2);
    $('#tsiv_recovered').html(tsiv_recovered + ' %');
    $('#pb_recovered').css('width', tsiv_recovered + '%');
    $('#pb_recovered').css('background-color', colorize_percent(tsiv_recovered));

    tsiv_dead = (parseInt($('#total').attr('dead')) / parseInt($('#total').attr('sick')) * 100).toFixed(2);
    $('#tsiv_dead').html(tsiv_dead + ' %');
    $('#pb_dead').css('width', tsiv_dead + '%');
    $('#pb_dead').css('background-color', colorize_percent(tsiv_dead, true));

    // x = avg(today_sick / yestd_sick for 7 last days)
    sick_data = $("#total").data('sick');
    var sick_delta = new Array(sick_data.length - 1);
    var delta_sum = 0;

    // calculate deltas for last 14 days
    for (i = 1; i < sick_data.length; i++) {
        sick_delta[i - 1] = parseInt(sick_data[i]) - parseInt(sick_data[i - 1]);
    }

    // calculate progressive number of deltas
    for (i = 1; i < sick_delta.length; i++) {
        delta_sum += sick_data[i] / sick_data[i - 1];
    }

    // Spead coeficient
    psm_spread = (delta_sum / (sick_delta.length - 1)).toFixed(2);
    danger_lvl = min_max_level_get(0.8, 1.2, 5, psm_spread);
    $('#psm_spread').html(psm_spread + ' %');
    $('#psi_spread').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    // Death rate = dead / sick
    psm_death = (parseInt($('#total').attr('dead')) / parseInt($('#total').attr('sick')) * 100).toFixed(2);
    danger_lvl = min_max_level_get(0, 20, 5, psm_death);
    $('#psm_death').html(psm_death + ' %');
    $('#psi_death').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    // Affected area = sick * dens
    psm_area = Math.round(parseInt($('#total').attr('sick')) / parseFloat($('#total').attr('dens')));
    danger_lvl = min_max_level_get(0, parseInt($('#total').attr('area').replace(/,/g, '')) * 0.01, 5, psm_area);
    $('#psm_area').html(psm_area + ' км<sup>2</sup>');
    $('#psi_area').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    // Month-sick prognose = sick * spread_coef
    psm_popl = Math.round((parseInt($('#total').attr('sick')) * (parseFloat(psm_spread) * 2 - 1.0)).toFixed(2));
    danger_lvl = min_max_level_get(0, parseInt($('#total').attr('sick')) * 2, 5, psm_popl);
    $('#psm_popl').html(psm_popl + ' людей');
    $('#psi_popl').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    // Sick risk without protection = sick / popl * spread_coef
    psm_infwo = (parseInt($('#total').attr('sick')) / parseInt($('#total').attr('popl').replace(/,/g, '')) * 100 * psm_spread).toFixed(3);
    danger_lvl = min_max_level_get(0, 2, 5, psm_infwo);
    $('#psm_infwo').html(psm_infwo + ' %');
    $('#psi_infwo').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    // Sick risk with protection = sick / popl * spread_coef * protection_coef
    protection_coef = 0.1;  // Masks can decrease speading up to 90%
    psm_infwt = (parseInt($('#total').attr('sick')) / parseInt($('#total').attr('popl').replace(/,/g, '')) * 100 * psm_spread * protection_coef).toFixed(3);
    danger_lvl = min_max_level_get(0, 1, 5, psm_infwt);
    $('#psm_infwt').html(psm_infwt + ' %');
    $('#psi_infwt').attr('class', 'ps_marker dtrr_danger' + danger_lvl);

    /* Update cure development timeline */
    cure_stage = parseInt($('#total').attr('cure'));
    for (i = 1; i < 8; i++) {
        if (i < cure_stage) {
            $('#curedev_s' + i).attr('class', 'is-complete');
        } else if (i == cure_stage) {
            $('#curedev_s' + i).attr('class', 'is-active');
        } else {
            $('#curedev_s' + i).attr('class', '');
        }
    }


}

/* Update region details
 * Update detailed information when country changed
 */
function update_region_details(name) {
    /* Update general information */
    $('#dtr_flag').attr('src', 'flags/flag_' + name + '.jpg');
    $('#dtr_name').html($('#total').attr('title'));
    $('#dtr_popl').html($('#total').attr('popl') + ' осіб');
    $('#dtr_area').html($('#total').attr('area') + ' км<sup>2</sup>');
    $('#dtr_dens').html($('#total').attr('dens') + ' людей/км<sup>2</sup>');
    $('#dtr_desc').html($('#total').attr('desc'));

    /* Update regions table */
    regions_data = $("#total").data('regs');
    dtr_regions = '<p class="dtrh_item">Регіон</p>' +
                  '<p class="dtrh_item">Хворих</p>' +
                  '<p class="dtrh_item">За добу</p>';

    var regions_num = regions_data.length;
    for (var i = 0; i < regions_num; i += 5) {
        dtr_regions += '<p class="dtrr_item ' + regions_data[i+3] + '" style="text-align: left;">' + regions_data[i]   + '</p>' +
                       '<p class="dtrr_item ' + regions_data[i+3] + '">' + regions_data[i+1] + '</p>' +
                       '<p class="dtrr_item ' + regions_data[i+4] + '">' + regions_data[i+2] + '</p>';
    }

    $('#dtr_regions').html(dtr_regions);
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

function copy_info(copy_type='all') {
    data = ' У регіоні "' + $('#rd_name').text() + '" ';
    info = []

    if ($('#rd_test').text() != '—' && (copy_type == 'all' || copy_type == 'test')) {
        info.push('перевірили '  + $('#rd_test').attr('text') + ' осіб ('  + $('#rd_test').attr('delta') + ' за добу)');
    }

    if ($('#rd_sick').text() != '—' && (copy_type == 'all' || copy_type == 'sick')) {
        info.push('захворіли '   + $('#rd_sick').attr('text') + ' осіб ('  + $('#rd_sick').attr('delta') + ' за добу)');
    }

    if ($('#rd_recv').text() != '—' && (copy_type == 'all' || copy_type == 'recv')) {
        info.push('одужали '     + $('#rd_recv').attr('text') + ' осіб ('  + $('#rd_recv').attr('delta') + ' за добу)');
    }

    if ($('#rd_dead').text() != '—' && (copy_type == 'all' || copy_type == 'dead')) {
        info.push('померли '     + $('#rd_dead').attr('text') + ' осіб ('  + $('#rd_dead').attr('delta') + ' за добу)');
    }

    data += info.join(', ') + '.';
    copy2clipboard(data);

    if (copy_type == 'all') {

    } else {

    }

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

/* Draggable plugin */
(function($) {
    $.fn.drags = function(opt) {
        opt = $.extend({ handle:"", cursor:"move" }, opt);

        if(opt.handle === "") {
            var $el = this;
        } else {
            var $el = this.find(opt.handle);
        }

        return $el.css('cursor', opt.cursor).on("mousedown", function(e) {
            if(opt.handle === "") {
                var $drag = $(this).addClass('draggable');
            } else {
                var $drag = $(this).addClass('active-handle').parent().addClass('draggable');
            }
            var z_idx = $drag.css('z-index'),
                drg_h = $drag.outerHeight(),
                drg_w = $drag.outerWidth(),
                pos_y = $drag.offset().top + drg_h - e.pageY,
                pos_x = $drag.offset().left + drg_w - e.pageX;
            $drag.css('z-index', 1000).parents().on("mousemove", function(e) {
                $('.draggable').offset({
                    top:e.pageY + pos_y - drg_h,
                    left:e.pageX + pos_x - drg_w
                }).on("mouseup", function() {
                    $(this).removeClass('draggable').css('z-index', z_idx);
                });
            });
            e.preventDefault(); // disable selection
        }).on("mouseup", function() {
            if(opt.handle === "") {
                $(this).removeClass('draggable');
            } else {
                $(this).removeClass('active-handle').parent().removeClass('draggable');
            }
        });

    }
})(jQuery);

$('#modal').drags();

/* Redraw dynamics chart for country */
function redraw_chart(chart_name) {
    /* Create full name of chart */
    var full_chart_name = chart_name + '_chart';

    if (full_chart_name == 'test_chart' && $test_chart != null) {
        $test_chart.destroy();
    }

    if (full_chart_name == 'sick_chart' && $sick_chart != null) {
        $sick_chart.destroy();
    }

    if (full_chart_name == 'recv_chart' && $recv_chart != null) {
        $recv_chart.destroy();
    }

    if (full_chart_name == 'dead_chart' && $dead_chart != null) {
        $dead_chart.destroy();
    }

    var chart    = document.getElementById(full_chart_name).getContext('2d'),
        gradient = chart.createLinearGradient(0, 0, 0, 450);

    gradient.addColorStop(0, 'rgba(255, 0,0, 0.5)');
    gradient.addColorStop(0.5, 'rgba(255, 0, 0, 0.25)');
    gradient.addColorStop(1, 'rgba(255, 0, 0, 0)');

    var data  = {
        labels: $("#total").data('days'),
        datasets: [{
                label: '',
                backgroundColor: gradient,
                pointBackgroundColor: 'white',
                borderWidth: 1,
                borderColor: '#911215',
                data:  $("#total").data(chart_name)
        }]
    };


    var options = {
        responsive: true,
        maintainAspectRatio: true,
        animation: {
            easing: 'easeInOutQuad',
            duration: 20
        },
        scales: {
            xAxes: [{
                gridLines: {
                    color: 'rgba(200, 200, 200, 0.4)',
                    lineWidth: 1
                }
            }],
            yAxes: [{
                gridLines: {
                    color: 'rgba(200, 200, 200, 1.0)',
                    lineWidth: 1
                }
            }]
        },
        elements: {
            line: {
                tension: 0.4
            }
        },
        legend: {
            display: false
        },
        point: {
            backgroundColor: 'white'
        },
        tooltips: {
            titleFontFamily: 'Play',
            backgroundColor: 'rgba(0, 0, 0, 0.3)',
            titleFontColor: 'white',
            caretSize: 8,
            cornerRadius: 10,
            xPadding: 10,
            yPadding: 10
        }
    };

    var chartInstance = new Chart(chart, {
        type: 'line',
        data: data,
        options: options
    });

    if (full_chart_name == 'test_chart') {
        $test_chart = chartInstance;
    }

    if (full_chart_name == 'sick_chart') {
        $sick_chart = chartInstance;
    }

    if (full_chart_name == 'recv_chart') {
        $recv_chart = chartInstance;
    }

    if (full_chart_name == 'dead_chart') {
        $dead_chart = chartInstance;
    }
}

/* Opens modal window for additional information */
function open_modal(name, content_id) {
    $('#mdl_head').html(name + '<span id="close_mdl" onclick="close_modal()">❌</span>');
    $('#mdl_content').html($('#' + content_id).html());

    $('#modal').removeClass('hide');

    if (content_id == 'storage_dynamics') {
        /* Redraw charts */
        redraw_chart('test');
        redraw_chart('sick');
        redraw_chart('recv');
        redraw_chart('dead');
    }

    $('#modal').addClass('show');

    /* Mark modal is opened */
    $modal_isopen = true;
}

/* Close the modal window */
function close_modal() {
    $('#modal').removeClass('show');

    $('#mdl_content').html('');
    $('#modal').scrollTop(0);

    $('#modal').addClass('hide');
    /* Mark modal is closed */
    $modal_isopen = false;
}
