import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from mutagen import File as mp3
from gi.repository import Gtk, Gst
from gi.repository import GdkPixbuf, GdkX11, GLib
Gst.init(None)
Gst.init_check(None)

class Handler():
    def __init__(self, widget):
        self.widget = widget

    def on_top_destroy(self, win):
        Gtk.main_quit()

    def on_next_button_clicked(self, key):
        pass

    def on_prev_button_clicked(self, key):
        pass

    def on_play_pause_toggle_button_toggled(self, button):
        if self.widget.playpause_button.get_active():
            img = Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PLAY,Gtk.IconSize.BUTTON)
            button.set_property("image", img)
            self.widget.pause()
        else:
            img = Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PAUSE,Gtk.IconSize.BUTTON)
            button.set_property("image", img)
            self.widget.play()

class Player():
    def __init__(self, location):
        try:
            super().__init__()
            builder = Gtk.Builder()
            builder.add_from_file("player.glade")

            builder.connect_signals(Handler(self))

            self.window = builder.get_object("top_window")
            self.window.set_title ("Blue Moon")

            self.play_area = builder.get_object("play_scrolled_window")
            self.playpause_button = builder.get_object("play_pause_toggle_button")
            self.slider = builder.get_object("progress_scale")
            self.slider_handler_id = self.slider.connect("value-changed", self.on_slider_seek)
            
            self.window.connect('realize', self.setup_player)
            self.location = location
            self.is_playing = False
        except KeyError:
            print("Not Found")

    def update_slider(self):
        if not self.is_playing:
            return False
        else:
            success, duration = self.player.query_duration(Gst.Format.TIME)

            self.mult = 100 / (duration / Gst.SECOND)
            if not success:
                raise GenericException("Couldn't fetch duration")
            
            success, position = self.player.query_position(Gst.Format.TIME)
            if not success:
                raise GenericException("Couldn't fetch current position to update slider")

            self.slider.handler_block(self.slider_handler_id)

            self.slider.set_value(float(position) / Gst.SECOND * self.mult)

            self.slider.handler_unblock(self.slider_handler_id)
        return True
    
    def on_slider_seek(self, scale):
        seek_time = self.slider.get_value()
        self.player.seek_simple(Gst.Format.TIME,  Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, seek_time * Gst.SECOND / self.mult)

    def parse_coverart(self):
        tags = mp3(self.location)
        for key in tags.keys():
            if key.startswith('APIC:'):
                image = tags[key].data
        return image

    def set_image(self, image):
        ximage = Gtk.Image()
        loader = GdkPixbuf.PixbufLoader()
        loader.write(image)
        loader.close()
        pixbuf = loader.get_pixbuf()
        ximage.set_from_pixbuf(pixbuf)
        self.play_area.add(ximage)
        self.play_area.show_all()

    def play(self):
        self.is_playing = True
        self.player.set_state(Gst.State.PLAYING)
        GLib.timeout_add(1000, self.update_slider)

    def pause(self):
        self.is_playing = False
        self.player.set_state(Gst.State.PAUSED)

    def stop(self):
        self.is_playing = False
        self.player.set_state(Gst.State.NULL)
        self.playpause_button.set_active(True)

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.stop()
        elif t == Gst.MessageType.ERROR:
            Gtk.main_quit()
            
    def setup_player(self, widget):
        self.player = Gst.Pipeline()
        factory = self.player.get_factory()
        playbin = factory.make('playbin')

        self.player.add(playbin)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)
        
        playbin.set_property('uri', 'file://' + self.location)

        if '.mp3' in self.location:
            self.set_image(self.parse_coverart())
        else:
            videosink = factory.make('gtksink')
            playbin.set_property('video-sink', videosink)
            self.play_area.add(videosink.props.widget)
            videosink.props.widget.show()
        self.play()

if __name__ == "__main__":        
    ui = Player(sys.argv[1])
    ui.window.set_default_size(1600, 800)
    ui.window.show_all()
    Gtk.main()
