var current_playing_index = null;

var sound = null;

function play(subsonic) {
  console.log("foo");
  if (current_playing_index == null) {
    current_playing_index = 0;
    file_id = document.getElementById(
      "recording" + current_playing_index,
    ).value;

    url =
      subsonic.host +
      ":" +
      subsonic.port +
      "/rest/stream?id=" +
      file_id +
      "&" +
      subsonic.args;
    console.log(url);
    sound = new Howl({
      src: [url],
      html5: true,
    });
    sound.play();
  }
  return true;
}
