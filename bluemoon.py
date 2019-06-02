#!/usr/bin/env python3
import sys
import glob
import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from mutagen import File as mp3
from gi.repository import Gtk, Gst
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

    def on_filelist_treeview_row_activated(self, widget, row, col):
        self.widget.select_song()
        self.widget.update_song_state(self.widget.current_song)
        self.widget.change_song()

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
            self.widget.generate_liststore(dialog.get_filename())
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

            self.filelist_tree = builder.get_object("filelist_treeview")
            self.filelist_select = builder.get_object("filelist_treeselection")
            self.slider = builder.get_object("progress_scale")
            self.volume = builder.get_object("volume_button")
            self.slider_handler_id = self.slider.connect("button-release-event", self.on_slider_seek)
            self.slider_handler_id = self.slider.connect("button-press-event", self.on_slider_press)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file('unknown-image.png')
            self.set_image(pixbuf, "")

            self.playlist = []
            self.generate_liststore("/home/blacksky/Music")
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
        columns = ["Title",
                   "Artist",
                   "Album",
                   "Duration"]
        for i, column in enumerate(columns):
            cell = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(column, cell, text=i)
            col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
            col.set_resizable(True)
            col.set_expand(True)
            self.filelist_tree.append_column(col)

    def generate_liststore(self, folder):
        self.create_playlist(folder)

        filelist_store = Gtk.ListStore(str, str, str, str)
        for i in range(len(self.playlist)):
            filelist_store.append(self.playlist[i][2])
        self.filelist_tree.set_model(filelist_store)

    def create_playlist(self, folder):
        songlist = glob.glob(folder + "/*.mp3")

        for i, song in enumerate(songlist, len(self.playlist)):
            songinfo= self.parse_mp3_tag(song)
            tmp = [i, song, songinfo]
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

    def parse_coverart(self):
        image = None
        tags = mp3(self.current_song[1])
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

    def select_song(self):
        (model, iter) = self.filelist_select.get_selected()
        for i in self.playlist:
            if model[iter][0] in i[2]:
                self.current_song = i

    def play_next(self):
        if self.current_song is None:
            self.select_song()
            self.update_song_state(self.current_song)

        if self.next_song is not None:
            self.update_song_state(self.next_song)
            self.change_song()

    def play_prev(self):
        if self.current_song is None:
            self.select_song()
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
        self.filelist_tree.set_cursor(self.current_song[0])
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
        image = self.parse_coverart()
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
