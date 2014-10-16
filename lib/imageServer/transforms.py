#!/usr/bin/env python

import Image
import ImageFilter
import ImageOps
import logging
import sys

from StringIO import StringIO

class TransformException(Exception):
    pass

class BaseTransform(object):
    command = None
    def execute(self, infile, args, **kwargs):
        args = self.parsePositionals(args)
        logging.debug('Calling %s.execute(%s)' % (self.__class__.__name__, ', '.join(args)))
        return self._execute(infile, *args, **kwargs)

    def parsePositionals(self, rawbuf):
        if not rawbuf:
            return []
        return [p.strip() for p in rawbuf[1:-1].split(',')]

# class for down-sizing to thumbnails
class Thumbnail(BaseTransform):
    command = 'thumbnail'
    def _execute(self, infile, size, **kwargs):     

        # open image
        im = Image.open(infile)
        width, height = im.size #returns tuple                
        if not size:
            size = (64, 64)
        else:
            #creates tuple from image
            size = tuple((int(s) for s in size.split('x')))            
        outfile = StringIO()                                
        im.thumbnail(size,Image.ANTIALIAS)
        im.save(outfile, 'png')
        return outfile.getvalue()        

class AspectResize(BaseTransform):
    command = 'aspectResize'
    def _execute(self, infile, size, **kwargs):        
        # debug
        im = Image.open(infile)
        width, height = im.size #returns tuple                

        if not size:
            size = (200, 200)
        else:
            size = tuple((int(s) for s in size.split('x')))
        outfile = StringIO()        

        # resize proportionally based on orientation
        # landscape
        if width > height : 
            magicRatio = float(size[0]) / float(width)            
            im = im.resize( ( size[0],int(magicRatio*height) ) )
        # portrait
        if height > width : 
            magicRatio = float(size[1]) / float(height)            
            im = im.resize( ( int(magicRatio*width),size[1] ) )     
        
        im.save(outfile, 'png')
        return outfile.getvalue()

class Resize(BaseTransform):
    command = 'resize'
    def _execute(self, infile, size, **kwargs):
        if not size:
            size = (64, 64)
        else:
            size = tuple((int(s) for s in size.split('x')))        
        outfile = StringIO()
        im = Image.open(infile)
        im = im.resize(size)
        im.save(outfile, 'png')
        return outfile.getvalue()        

class Crop(BaseTransform):
    command = 'crop'
    def _execute(self, infile, box, **kwargs):        
        # debug
        im = Image.open(infile)         
        outfile = StringIO()

        # get coords
        box = tuple((int(coord) for coord in box.split('x')))        

        # perform crop        
        im = im.crop(box)                
        
        im.save(outfile, 'png')
        return outfile.getvalue()

class Rotate(BaseTransform):
    command = 'rotate'
    def _execute(self, infile, angle, **kwargs):
        outfile = StringIO()
        im = Image.open(infile)
        im = im.rotate(float(angle), expand=True)
        im.save(outfile, 'png')
        return outfile.getvalue()

class Flip(Rotate):
    command = 'flip'
    def _execute(self, infile, *args, **kwargs):
        return super(Flip, self)._execute(infile, 180, **kwargs)

class Filter(BaseTransform):
    command = 'filter'
    def _execute(self, infile, _filter, **kwargs):
        outfile = StringIO()
        im = Image.open(infile)

        _filter = _filter.upper()
        if hasattr(ImageFilter, _filter):
            im = im.filter(getattr(ImageFilter, _filter))
        im.save(outfile, 'png')
        return outfile.getvalue()

class ImageOpsTransform(BaseTransform):
    def _execute(self, infile, *args, **kwargs):
        outfile = StringIO()
        im = Image.open(infile)
        im = im.convert('RGB')
        im = self.operation(im)
        im.save(outfile, 'png')
        return outfile.getvalue()

class Invert(ImageOpsTransform):
    command = 'invert'
    def operation(self, img):
        return ImageOps.invert(img)

class Grayscale(ImageOpsTransform):
    command = 'grayscale'
    def operation(self, img):
        return ImageOps.grayscale(img)

class Mirror(ImageOpsTransform):
    command = 'mirror'
    def operation(self, img):
        return ImageOps.mirror(img)

def __aggregate():
    module = sys.modules[__name__]
    for name in dir(module):
        attr = getattr(module, name)
        if not isinstance(attr, type):
            continue
        if not issubclass(attr, BaseTransform):
            continue
        if attr == BaseTransform:
            continue
        yield attr

commands = dict(((t.command, t) for t in __aggregate()))

