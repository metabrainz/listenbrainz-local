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
var interval_id = null;

function on_end() {
  enter_event(EVENT_NEXT);
}

function on_play() {
  update_button_states();
}

function on_error(song_id, error_code) {
  if (song_id == null)
    return;
  if (Number.isInteger(error_code)) {
    if (error_code == 4) {
      msg = "Cannot play track. Are the credentials for this service correct?";
    } 
    else if (error_code == 3) {
      msg = "Cannot play track due to some audio or audio file format issue.";
    } 
    else {
      msg = "Cannot play track due to a network error.";
    } 
  } else {
    msg = error_code + " This error may happen if your credentials for the services are incorrect.";
  }
  update_button_states();
  document.getElementById("playback-errors").style.display = "block"
  document.getElementById("playback-errors").textContent = msg;
}

function init_player(_subsonic_info) {
  console.log(_subsonic_info);
  subsonic_info = _subsonic_info;
  update_button_states();
}

function enter_event(event, arg = null) {
  for (let trans of transition_table) {
    if (current_state == trans[0] && event == trans[1]) {
      current_state = trans[2];
      if (trans[2] == STATE_PLAYING) {
        play_pause();
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

function update_button_states() {
  playlist = document.getElementById("playlist-table");
  if (playlist)
    num_tracks_loaded = playlist.rows.length - 1; // skip header row
  else num_tracks_loaded = 0;

  if (!document.getElementById("prev-button")) return;

  document.getElementById("prev-button").disabled = !(
    current_playing_index != null && current_playing_index > 0
  );
  document.getElementById("stop-button").disabled = !(
    sound != null && current_playing_index != null
  );
  document.getElementById("play-button").disabled = num_tracks_loaded == 0;
  document.getElementById("next-button").disabled = !(
    current_playing_index != null &&
    current_playing_index < num_tracks_loaded - 1
  );
  document.getElementById("save-playlist").disabled = num_tracks_loaded == 0;

  play_pause_button = document.getElementById("play-pause-icon");
  if (current_playing_index != null && sound != null && sound.playing()) {
    play_pause_button.classList.add("fa-pause");
    play_pause_button.classList.remove("fa-play");
  } else {
    play_pause_button.classList.remove("fa-pause");
    play_pause_button.classList.add("fa-play");
  }
}

function play_pause() {
  if (sound != null) {
    if (sound.playing()) pause();
    else sound.play();
    update_button_states();
    return;
  }
  if (current_playing_index == null) {
    current_playing_index = 0;
  } else clear_playing_now_row(current_playing_index);
  file_id = document.getElementById("recording" + current_playing_index).value;
  file_source = document.getElementById("recording" + current_playing_index + "_source").value;

  set_playing_now_row(current_playing_index);
  play_track(file_id, file_source);
  update_button_states();
}

function pause() {
  if (sound != null) {
    sound.pause();
    update_button_states();
    return;
  }
}
function stop() {
  clear_playing_now_row(current_playing_index);
  current_playing_index = null;
  stop_playing();
  update_button_states();
  update_progress_bar();
}

function prev() {
  if (current_playing_index == null) {
    return;
  }
  clear_playing_now_row(current_playing_index);
  if (current_playing_index == 0) {
    enter_event(EVENT_STOP);
    return;
  }

  current_playing_index -= 1;
  file_id = document.getElementById("recording" + current_playing_index).value;
  if (file_id != null) {
    stop_playing();
    enter_event(EVENT_PLAY);
  } else {
    enter_event(EVENT_STOP);
  }
}

function next() {
  if (current_playing_index == null) {
    return;
  }
  clear_playing_now_row(current_playing_index);

  current_playing_index += 1;
  file_id = document.getElementById("recording" + current_playing_index).value;

  if (file_id != null) {
    stop_playing();
    enter_event(EVENT_PLAY);
  } else {
    enter_event(EVENT_STOP);
  }
}

function jump(index) {
  if (current_playing_index) {
    clear_playing_now_row(current_playing_index);
  }

  current_playing_index = index;
  file_id = document.getElementById("recording" + current_playing_index).value;
  if (file_id != null) {
    stop_playing();
    enter_event(EVENT_PLAY);
  } else {
    enter_event(EVENT_STOP);
  }
}

function play_track(file_id, file_source) {
  //For testing with only short tracks...
  //file_id = "cf22184021802f7ebbf0e461d11fc42d";
  url =
    subsonic_info[file_source].url +
    "/rest/stream?id=" +
    file_id +
    "&" +
    "u=" +
    subsonic_info[file_source].username +
    "&s=" +
    subsonic_info[file_source].salt +
    "&t=" +
    subsonic_info[file_source].token +
    "&v=1.14.0&c=lb-local";
  stop_playing();
  sound = new Howl({
    src: [url],
    html5: true,
    onend: on_end,
    onplay: on_play,
    onloaderror: on_error,
  });
  sound.play();
  interval_id = setInterval(timer_update, 100);
}

function timer_update() {
  update_progress_bar();
}

function update_progress_bar() {
  if (sound != null) {
    pos = (sound.seek() * 100) / sound.duration();
  } else {
    pos = 0;
  }
  pbar = document.getElementById("progress-bar");
  if (pbar) {
    pbar.setAttribute("aria-valuenow", pos.toString());
    pbar.setAttribute("style", "width: " + pos + "%");
  }
}

function seek(ev) {
  if (sound == null) return;

  pbar = document.getElementById("progress-bar-div");
  brect = pbar.getBoundingClientRect();
  width = brect.right - brect.left;
  x = ev.x - brect.left;
  percent = x / width;
  pos = percent * sound.duration();
  sound.seek(pos);
}

function stop_playing() {
  if (sound != null) {
    sound.unload();
    sound = null;
  }
  clearInterval(interval_id);
  interval_id = null;
}

function set_playing_now_row(index) {
  var element = document.getElementById("row" + index);
  if (element != null) {
    element.classList.add("table-active");
  }
}

function clear_playing_now_row(index) {
  var element = document.getElementById("row" + index);
  if (element != null) {
    element.classList.remove("table-active");
  }
}
