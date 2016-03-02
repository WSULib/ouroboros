# Helper Classes and Functions for Ouroboros

import time


# LazyProperty Decorator
class LazyProperty(object):
	'''
	meant to be used for lazy evaluation of an object attribute.
	property should represent non-mutable data, as it replaces itself.
	'''

	def __init__(self,fget):
		self.fget = fget
		self.func_name = fget.__name__


	def __get__(self,obj,cls):
		if obj is None:
			return None
		value = self.fget(obj)
		setattr(obj,self.func_name,value)
		return value


# generic, empty object class
class BlankObject(object):
    pass


# small decorator to time functions
def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        print '%s function took %0.3f ms, %0.3f s' % (f.func_name, (time2-time1)*1000.0, (time2-time1))
        return ret
    return wrap