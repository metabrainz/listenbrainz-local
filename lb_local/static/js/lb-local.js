const STATE_STOPPED = 1;
const STATE_PLAYING = 2;
const STATE_PAUSED = 3;
const STATE_NEXT = 4;
const STATE_PREV = 5;
const STATE_JUMP = 6;

const EVENT_INIT = 0;
const EVENT_PREV = 1;
const EVENT_NEXT = 2;
const EVENT_PLAY = 3;
const EVENT_STOP = 4;
const EVENT_JUMP = 5;

var transition_table = [
    [STATE_STOPPED, EVENT_PLAY, STATE_PLAYING],
    [STATE_STOPPED, EVENT_JUMP, STATE_JUMP],
    [STATE_PLAYING, EVENT_NEXT, STATE_NEXT],
    [STATE_PLAYING, EVENT_PREV, STATE_PREV],
    [STATE_PLAYING, EVENT_STOP, STATE_STOPPED],
    [STATE_PLAYING, EVENT_PLAY, STATE_PAUSED],
    [STATE_PLAYING, EVENT_JUMP, STATE_JUMP],
    [STATE_NEXT, EVENT_PLAY, STATE_PLAYING],
    [STATE_NEXT, EVENT_STOP, STATE_STOPPED],
    [STATE_PREV, EVENT_PLAY, STATE_PLAYING],
    [STATE_PREV, EVENT_STOP, STATE_STOPPED],
    [STATE_PAUSED, EVENT_PLAY, STATE_PLAYING],
    [STATE_PAUSED, EVENT_STOP, STATE_STOPPED],
    [STATE_PAUSED, EVENT_PREV, STATE_PREV],
    [STATE_PAUSED, EVENT_NEXT, STATE_NEXT],
    [STATE_PAUSED, EVENT_JUMP, STATE_JUMP],
    [STATE_JUMP, EVENT_PLAY, STATE_PLAYING],
];

var sound = null;
var current_state = STATE_STOPPED;
var current_playing_index = null;
var subsonic_info = null;

function init_player(subsonic) {
    subsonic_info = subsonic;
}
function enter_event(event, arg = null) {
    console.log("enter event: " + event);
    for (let trans of transition_table) {
        //console.log(trans[0], trans[1], trans[2]);
        if (current_state == trans[0] && event == trans[1]) {
            console.log(trans[0], trans[1], trans[2]);
            current_state = trans[2];
            if (trans[2] == STATE_PLAYING) {
                play();
                return;
            }
            if (trans[2] == STATE_PAUSED) {
                pause();
                return;
            }
            if (trans[2] == STATE_STOPPED) {
                stop();
                return;
            }
            if (trans[2] == STATE_PREV) {
                prev();
                return;
            }
            if (trans[2] == STATE_NEXT) {
                next();
                return;
            }
            if (trans[2] == STATE_JUMP) {
                jump(arg);
                return;
            }
        }
    }
    console.log(
        "Invalid transition " + event + " for current state " + current_state,
    );
}

function play() {
    console.log("play");
    if (sound != null) {
        console.log("play/resume");
        sound.play();
        return;
    }
    if (current_playing_index == null) {
        current_playing_index = 0;
    }

    file_id = document.getElementById(
        "recording" + current_playing_index,
    ).value;

    play_track(file_id);
}

function pause() {
    console.log("pause");
    if (sound != null) {
        sound.pause();
        return;
    }
}
function stop() {
    console.log("stop");
    toggle_playing_now_row(current_playing_index);
    current_playing_index = null;
    if (sound != null) {
        sound.unload();
        sound = null;
    }
}

function prev() {
    console.log("prev");
    if (current_playing_index == null) {
        return;
    }
    toggle_playing_now_row(current_playing_index);
    if (current_playing_index == 0) {
        enter_event(EVENT_STOP);
        return;
    }

    current_playing_index -= 1;
    file_id = document.getElementById(
        "recording" + current_playing_index,
    ).value;
    console.log("file id" + file_id);
    if (file_id != null) {
        if (sound != null) {
            sound.unload();
            sound = null;
        }
        enter_event(EVENT_PLAY);
    } else {
        enter_event(EVENT_STOP);
    }
}

function next() {
    console.log("next");
    if (current_playing_index == null) {
        return;
    }
    toggle_playing_now_row(current_playing_index);

    current_playing_index += 1;
    file_id = document.getElementById(
        "recording" + current_playing_index,
    ).value;

    if (file_id != null) {
        if (sound != null) {
            sound.unload();
            sound = null;
        }
        enter_event(EVENT_PLAY);
    } else {
        enter_event(EVENT_STOP);
    }
}

function jump(index) {
    console.log("jump");
    if (current_playing_index) {
        toggle_playing_now_row(current_playing_index);
    }

    current_playing_index = index;
    file_id = document.getElementById(
        "recording" + current_playing_index,
    ).value;
    console.log("file id" + file_id);
    if (file_id != null) {
        if (sound != null) {
            sound.unload();
            sound = null;
        }
        enter_event(EVENT_PLAY);
    } else {
        enter_event(EVENT_STOP);
    }
}

function play_track(file_id) {
    console.log("play_track");
    //For testing with only short tracks...
    //file_id = "cf22184021802f7ebbf0e461d11fc42d";
    url =
        subsonic_info.host +
        ":" +
        subsonic_info.port +
        "/rest/stream?id=" +
        file_id +
        "&" +
        subsonic_info.args;
    if (sound != null) {
        sound.unload();
        sound = null;
    }
    sound = new Howl({
        src: [url],
        html5: true,
        onend: on_end,
    });
    sound.play();
    toggle_playing_now_row(current_playing_index);
}

function on_end() {
    enter_event(EVENT_NEXT);
}

function toggle_playing_now_row(index) {
    var element = document.getElementById("row" + index);
    element.classList.toggle("table-active");
}
