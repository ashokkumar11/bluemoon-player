import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from mutagen import File as mp3
from gi.repository import Gtk, Gst
from gi.repository import GdkPixbuf
Gst.init(None)
Gst.init_check(None)

class Handler():
    def __init__(self, widget):
        self.widget = widget

    def onDestroy(self, win):
        Gtk.main_quit()

    def on_next_clicked(self, key):
        pass

    def on_prev_clicked(self, key):
        pass

    def on_pause_clicked(self, key):
        self.widget.pipeline.set_state(Gst.State.PAUSE)

    def on_play_clicked(self, key):
        self.widget.pipeline.set_state(Gst.State.PLAYING)
        if self.widget.videosink is not None:
            self.widget.videosink.props.widget.show()


class GstWidget():
    def __init__(self, location):
        try:
            super().__init__()
            self.builder = Gtk.Builder()
            self.builder.add_from_file("player.glade")

            self.builder.connect_signals(Handler(self))

            self.window = self.builder.get_object("top")
            self.window.set_title ("Blue Moon")

            self.window_view = self.builder.get_object("window_view")
            self.window_img = self.builder.get_object("window_img")
            self.window.connect('realize', self._on_realize)
            self.location = location
            self.videosink = None
        except KeyError:
            print("Not Found")

    def parse_coverart(self):
        tags = mp3(self.location)
        for key in tags.keys():
            if key.startswith('APIC:'):
                image = tags[key].data
        return image

    def set_image(self, image):
        loader = GdkPixbuf.PixbufLoader()
        loader.write(image)
        loader.close()
        pixbuf = loader.get_pixbuf()
        self.window_img.set_from_pixbuf(pixbuf)

        if self.videosink is not None:
            self.videosink.hide()

        self.window.show_all()

    def _on_realize(self, widget):
        self.pipeline = Gst.Pipeline()
        factory = self.pipeline.get_factory()
        playbin = factory.make('playbin')

        self.pipeline.add(playbin)
        playbin.set_property('uri', 'file://' + self.location)

        if '.mp3' in self.location:
            self.set_image(self.parse_coverart())
        else:
            self.videosink = factory.make('gtksink')
            playbin.set_property('video-sink', self.videosink)
            self.window_img.hide()
            self.window_view.add(self.videosink.props.widget)

ui = GstWidget(sys.argv[1])
ui.window.show_all()


Gtk.main()
