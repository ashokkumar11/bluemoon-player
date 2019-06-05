#!/usr/bin/env python3
import sys
import glob
import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from mutagen import File as mp3
from gi.repository import Gtk, Gst, Gdk
from gi.repository import GdkPixbuf, GdkX11, GLib
Gst.init(None)
Gst.init_check(None)

# settings = Gtk.Settings.get_default()
# settings.set_property("gtk-theme-name", "Android-master")

class Handler():
    def __init__(self, widget):
        self.widget = widget

    def on_top_destroy(self, win):
        Gtk.main_quit()

    def on_next_button_clicked(self, key):
        self.widget.play_next()

    def on_prev_button_clicked(self, key):
        self.widget.play_prev()

    def on_play_pause_toggle_button_toggled(self, button):
        if self.widget.playpause_button.get_active():
            img = Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PAUSE,Gtk.IconSize.BUTTON)
            button.set_property("image", img)
            self.widget.play()
        else:
            img = Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PLAY,Gtk.IconSize.BUTTON)
            button.set_property("image", img)
            self.widget.pause()

    def on_volume_button_value_changed(self, volume, value):
        self.widget.player.set_property('volume', value)

    def on_folder_button_clicked(self, button):
        dialog = Gtk.FileChooserDialog("Please choose a folder", self.widget.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             "Select", Gtk.ResponseType.OK))
        dialog.set_default_size(800, 400)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.widget.create_playlist(dialog.get_filename())
            self.widget.populate_treeview()
            if self.widget.current_song is not None:
                self.widget.update_song_state(self.widget.current_song)

        dialog.destroy()

    def on_song_image_button_press_event(self):
        print('hello')

class Player():
    def __init__(self):
        try:
            super().__init__()
            builder = Gtk.Builder()
            builder.add_from_file("player.glade")

            builder.connect_signals(Handler(self))

            self.window = builder.get_object("top_window")
            self.window.set_title ("Blue Moon")
            self.window.set_decorated(True)
            self.window.set_border_width(10)

            self.play_area = builder.get_object("play_scrolled_window")
            self.playpause_button = builder.get_object("play_pause_toggle_button")
            self.song_image = builder.get_object("song_image")
            self.song_label = builder.get_object("song_label")

            self.playlist_view = builder.get_object("playlist_view")
            self.playlist_view.set_max_children_per_line(4)
            self.playlist_view.set_min_children_per_line(4)
            self.slider = builder.get_object("progress_scale")
            self.volume = builder.get_object("volume_button")
            self.slider_handler_id = self.slider.connect("button-release-event", self.on_slider_seek)
            self.slider_handler_id = self.slider.connect("button-press-event", self.on_slider_press)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file('unknown-image.png')
            self.set_image(pixbuf, "")

            self.playlist = []
            self.create_playlist("/home/blacksky/Music")
            self.populate_treeview()
            self.setup_player()
            self.current_song = None
            self.prev_song = None
            self.next_song = None
            self.is_playing = False
            self.inited = False
            self.skip = False
        except KeyError:
            print("Not Found")

    def populate_treeview(self):
        for element in self.playlist_view.get_children():
                self.playlist_view.remove(element)

        for song in self.playlist:
            eventbox = Gtk.EventBox()
            eventbox.set_size_request(300, 300)
            box1 = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
            eventbox.add(box1)
            image = Gtk.Image()
            pixbuf = song[3].scale_simple(200, 200, GdkPixbuf.InterpType.BILINEAR)
            image.set_from_pixbuf(pixbuf)
            box1.pack_start(image, True, True, padding=1)
            image.show()
            label = Gtk.Label()
            label.set_text(song[2][0])
            box1.pack_start(label, True, True, padding=1)
            eventbox.connect('button-press-event', self.on_button_press, song)
            self.playlist_view.add(eventbox)

        self.playlist_view.show_all()

    def on_button_press(self, widget, event, song):
        if event.button == 1:
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.current_song = song
                self.update_song_state(self.current_song)
                self.change_song()
            if event.type == Gdk.EventType.BUTTON_PRESS:
                if self.current_song is None:
                    self.current_song = song
                    self.update_song_state(self.current_song)


    def create_playlist(self, folder):
        songlist = glob.glob(folder + "/*.mp3")

        for i, song in enumerate(songlist, len(self.playlist)):
            songinfo= self.parse_mp3_tag(song)
            limage = self.parse_coverart(song)
            if limage is not None:
                image = self.create_pixbuf_from_image(limage)
            else:
                image = GdkPixbuf.Pixbuf.new_from_file('unknown-image.png')
            tmp = [i, song, songinfo, image]
            self.playlist.append(tmp)

    def parse_mp3_tag(self, location):
        tags = mp3(location, easy=True)
        info = []

        duration = time.strftime("%M:%S", time.gmtime(tags.info.length))
        for tag in ['title', 'artist', 'album']:
            if tag in tags.keys():
                info.append(tags[tag][0])
            else:
                info.append("UNKNOWN")
        info.append(duration)
        return info

    def update_slider(self):
        if not self.is_playing:
            return False
        else:
            if self.skip is False:
                success, duration = self.player.query_duration(Gst.Format.TIME)
                if duration == 0:
                    self.mult = 0.1
                else:
                    self.mult = 100 / (duration / Gst.SECOND)
                    success, position = self.player.query_position(Gst.Format.TIME)
                    self.slider.handler_block(self.slider_handler_id)
                    self.slider.set_value(float(position) / Gst.SECOND * self.mult)
                    self.slider.handler_unblock(self.slider_handler_id)
            return True

    def on_slider_press(self, widget, scale):
        if not self.is_playing:
            return
        else:
            self.skip = True

    def on_slider_seek(self, widget, scale):
        if not self.is_playing:
            return
        else:
            seek_time = self.slider.get_value()
            self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, seek_time * Gst.SECOND / self.mult)
            self.skip = False

    def parse_coverart(self, image_url):
        image = None
        tags = mp3(image_url)
        for key in tags.keys():
            if key.startswith('APIC:'):
                image = tags[key].data
        return image

    def create_pixbuf_from_image(self, image):
        loader = GdkPixbuf.PixbufLoader()
        loader.write(image)
        loader.close()
        return loader.get_pixbuf()

    def set_image(self, pixbuf, text):
        pixbuf = pixbuf.scale_simple(90, 90, GdkPixbuf.InterpType.BILINEAR)
        self.song_image.set_from_pixbuf(pixbuf)
        self.song_label.set_text(text)

    def play_next(self):
        if self.current_song is None:
            self.update_song_state(self.current_song)

        if self.next_song is not None:
            self.update_song_state(self.next_song)
            self.change_song()

    def play_prev(self):
        if self.current_song is None:
            self.update_song_state(self.current_song)

        if self.prev_song is not None:
            self.update_song_state(self.prev_song)
            self.change_song()

    def update_song_state(self, song):
        self.current_song = song
        self.prev_song = None
        self.next_song = None

        i = song[0]
        if i is 0:
            self.prev_song = self.playlist[len(self.playlist) - 1]
        else:
            self.prev_song = self.playlist[i - 1]
        self.next_song = self.playlist[(i + 1) % len(self.playlist)]

    def play(self):
        if self.current_song == None:
            self.select_song()
            self.update_song_state(self.current_song)

        if not self.inited:
            self.change_uri()
            self.inited = True

        self.player.set_state(Gst.State.PLAYING)
        playlist_view_child = self.playlist_view.get_child_at_index(self.current_song[0])
        self.playlist_view.select_child(playlist_view_child)
        self.is_playing = True
        self.timer = GLib.timeout_add(100, self.update_slider)

    def stop(self):
        self.is_playing = False
        self.playpause_button.set_active(False)
        self.player.set_state(Gst.State.NULL)

    def pause(self):
        self.is_playing = False
        self.player.set_state(Gst.State.PAUSED)

    def change_uri(self):
        self.player.set_property('uri', 'file://' + self.current_song[1])
        image = self.parse_coverart(self.current_song[1])
        if image is not None:
            self.set_image(self.create_pixbuf_from_image(image), self.current_song[2][0])
        else:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file('unknown-image.png')
            self.set_image(pixbuf, self.current_song[2][0])

    def change_song(self):
        self.stop()
        self.change_uri()
        self.inited = True
        self.playpause_button.set_active(True)

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.play_next()
        elif t == Gst.MessageType.ERROR:
            Gtk.main_quit()

    def setup_player(self):
        factory = Gst.Pipeline().get_factory()
        self.player = factory.make('playbin')
        self.player.set_property('volume', 1.0)
        self.volume.set_value(1.0)
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_message)

if __name__ == "__main__":
    ui = Player()
    ui.window.set_default_size(1600, 800)
    ui.window.show_all()
    Gtk.main()
