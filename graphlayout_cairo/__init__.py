#!/usr/bin/env python3

import cairocffi as cairo
import math


class Operation:

    def __init__(self):
        self._z = 0

    def z(self, val):
        self._z = val
        return self


class RoundedRect(Operation):

    def __init__(self, rgba, radius):
        self.rgba = rgba
        self.radius = radius

    def draw(self, context, x, y, w, h):
        degrees = math.pi / 180

        context.save()
        context.new_sub_path()
        context.arc(x + w - self.radius, y + self.radius,
                    self.radius, -90 * degrees, 0 * degrees)
        context.arc(x + w - self.radius, y + h - self.radius,
                    self.radius, 0 * degrees, 90 * degrees)
        context.arc(x + self.radius, y + h - self.radius,
                    self.radius, 90 * degrees, 180 * degrees)
        context.arc(x + self.radius, y + self.radius,
                    self.radius, 180 * degrees, 270 * degrees)
        context.close_path()
        context.set_source_rgba(*self.rgba)
        context.fill()

    def __repr__(self):
        return "{cls}(rgba={self.rgba!r}, radius={self.radius!r})".format(cls=self.__class__.__name__, self=self)
        context.restore()


class Blur(Operation):

    def __init__(self, blur, inset=0):
        self.blur = blur
        self.other = None
        self.inset = inset

    def __ror__(self, other):
        self.other = other
        return self

    def draw(self, context, x, y, w, h):
        surface_width = int(w + self.blur * 2)
        surface_height = int(h + self.blur * 2)

        src_surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, surface_width, surface_height)
        src_context = cairo.Context(src_surface)
        src_stride = src_surface.get_stride()

        dst_surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, surface_width, surface_height)
        dst_context = cairo.Context(dst_surface)
        dst_stride = src_surface.get_stride()

        self.other.draw(src_context, self.blur, self.blur, w, h)

        src_surface.flush()
        src_data = src_surface.get_data()

        dst_surface.flush()
        dst_data = dst_surface.get_data()

        for _y in range(surface_height):
            for _x in range(surface_width * 4):
                out = 0
                divisor = 0
                if self.blur + self.inset <= _y < surface_height - self.blur - self.inset and self.blur + self.inset <= _x // 4 < surface_width - self.blur - self.inset:
                    continue
                for b_y in range(_y - self.blur, _y + self.blur):
                    for b_x in range(_x - self.blur * 4, _x + self.blur * 4, 4):
                        if 0 <= b_y < surface_height and 0 <= b_x < surface_width * 4:
                            out += ord(src_data[b_y * src_stride + b_x])
                            divisor += 1

                if divisor:
                    dst_data[_y * dst_stride + _x] = bytes((out // divisor,))

        src_surface.mark_dirty()
        dst_surface.mark_dirty()

        # draw blurred image
        context.save()
        context.translate(x - self.blur, y - self.blur)
        context.set_source_surface(dst_surface)
        context.paint()
        context.restore()

    def __repr__(self):
        return "{self.other!r} | {cls}(blur={self.blur!r})".format(cls=self.__class__.__name__, self=self)


class Shadow(Operation):

    def __init__(self, rgba, radius):
        self.radius = radius
        self.rgba = rgba
        self.rgba_clear = tuple(rgba[:3]) + (0,)

        self.linear = cairo.LinearGradient(0, 1, 0, -1)
        self.linear.add_color_stop_rgba(0, *self.rgba)
        self.linear.add_color_stop_rgba(1, *self.rgba_clear)

        self.radial = cairo.RadialGradient(0, 0, 0, 0, 0, self.radius * 2)
        self.radial.add_color_stop_rgba(0, *self.rgba)
        self.radial.add_color_stop_rgba(1, *self.rgba_clear)

    def draw_glow(self, context, x1, y1, x2, y2):
        mag = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        angle = math.atan2(y2 - y1, x2 - x1)
        context.save()
        context.translate(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
        context.rotate(angle)
        context.scale(mag - self.radius * 2, self.radius)
        context.set_source(self.linear)
        context.rectangle(-0.5, 1, 1, -2)
        context.fill()
        context.restore()

    def draw_corner(self, context, x, y, v_x, v_y):
        angle = math.atan2(v_y, v_x)
        context.save()
        context.translate(x - v_x * self.radius, y - v_y * self.radius)
        context.move_to(0, 0)
        context.arc(0, 0, self.radius * 2, angle -
                    math.pi / 4, angle + math.pi / 4)
        context.close_path()
        context.set_source(self.radial)
        context.fill()
        context.restore()

    def draw(self, context, x, y, w, h):
        context.save()
        self.draw_glow(context, x, y, x + w, y)
        self.draw_glow(context, x, y + h, x, y)
        self.draw_glow(context, x + w, y, x + w, y + h)
        self.draw_glow(context, x + w, y + h, x, y + h)

        self.draw_corner(context, x + 0, y + 0, -1, -1)
        self.draw_corner(context, x + w, y + 0, 1, -1)
        self.draw_corner(context, x + w, y + h, 1, 1)
        self.draw_corner(context, x + 0, y + h, -1, 1)

        context.set_source_rgba(*self.rgba)
        context.rectangle(x + self.radius, y + self.radius,
                          w - self.radius * 2, h - self.radius * 2)
        context.fill()

        context.restore()

    def __repr__(self):
        return "{cls}(rgba={self.rgba!r}, radius={self.radius!r})".format(cls=self.__class__.__name__, self=self)


class DropShadow(Operation):

    def __init__(self, z):
        self.z = z
        self.other = None

    def __ror__(self, other):
        self.other = other
        return self

    def z(self, *args, **kwargs):
        return self.other.z(*args, **kwargs)

    def draw(self, context, x, y, w, h):
        if self.z > 0:
            Shadow(rgba=(0.0, 0.0, 0.0, 1.0 / (self.z / 5 + 1)),
                   radius=self.z).draw(context, x, y + self.z, w, h)
        self.other.draw(context, x, y, w, h)


def __repr__(self):
    return "{self.other!r} | {cls}(z={self.z!r})".format(cls=self.__class__.__name__, self=self)


class Rect(Operation):

    def __init__(self, rgba):
        self.rgba = rgba

    def draw(self, context, x, y, w, h):
        context.save()
        context.set_source_rgba(*self.rgba)
        context.rectangle(x, y, w, h)
        context.fill()
        context.restore()

    def __repr__(self):
        return "{cls}(rgba={self.rgba!r})".format(cls=self.__class__.__name__, self=self)


class GradientRect(Operation):

    def __init__(self, rgba_start, rgba_end=None, vertical=False, flipped=False):
        if rgba_end is None:
            rgba_end = tuple(rgba_start[:3]) + (0,)
        self.vertical = vertical
        self.flipped = flipped
        if vertical:
            self.linear = cairo.LinearGradient(0, -0.5, 0, 0.5)
        else:
            self.linear = cairo.LinearGradient(-0.5, 0, 0.5, 0)
        self.linear.add_color_stop_rgba(0, *rgba_start)
        self.linear.add_color_stop_rgba(1, *rgba_end)

    def draw(self, context, x, y, w, h):
        context.save()
        context.translate(x + w / 2, y + h / 2)
        context.scale(w if not self.flipped else -w,
                      h if not self.flipped else -h)
        context.set_source(self.linear)
        context.rectangle(-0.5, -0.5, 1, 1)
        context.fill()
        context.restore()


class Image(Operation):

    def __init__(self, src):
        self.src = src
        self.surface = cairo.ImageSurface.create_from_png(src)
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()

    def draw(self, context, x, y, w, h):
        context.save()
        context.set_source_surface(self.surface)
        context.paint()
        context.restore()

    def __repr__(self):
        return "{cls}(src={self.src!r})".format(cls=self.__class__.__name__, self=self)


class Text(Operation):

    def __init__(self, text, context, family, size, rgba, weight=cairo.FONT_WEIGHT_NORMAL, slant=cairo.FONT_SLANT_NORMAL):
        self.text = text
        self.size = size
        self.rgba = rgba
        self.face = cairo.ToyFontFace(family, weight=weight, slant=slant)
        context.save()
        self.set_font_on_context(context)
        self.x_bearing, self.y_bearing, self.width, self.height, _, _ = context.text_extents(
            text)
        context.restore()

    def set_font_on_context(self, context):
        context.set_font_face(self.face)
        context.set_source_rgba(*self.rgba)
        context.set_font_size(self.size)

    def draw(self, context, x, y, w, h):
        context.save()
        self.set_font_on_context(context)
        # TODO
        context.move_to(x, y + self.height / 2 - self.y_bearing / 2)
        context.show_text(self.text)
        context.restore()

    def __repr__(self):
        return "{cls}(text={self.text!r})".format(cls=self.__class__.__name__, self=self)


class Drawer:

    def __init__(self, context):
        self.context = context
        self.cmds = []

    def __call__(self, obj, x, y, w, h):
        if hasattr(obj, 'draw'):
            self.cmds.append(((obj), (x, y, w, h)))

    def flush(self):
        self.cmds.sort(key=lambda cmd: cmd[
                       0]._z if hasattr(cmd[0], '_z') else 0)
        for obj, args in self.cmds:
            obj.draw(context, *args)
        self.cmds.clear()
