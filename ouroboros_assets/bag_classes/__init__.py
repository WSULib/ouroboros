import os
__all__ = []
for module in os.listdir(os.path.dirname(__file__)):
	# if module == '__init__.py' or module[-3:] != '.py' or module == 'bag_class_template.py':
	if module == '__init__.py' or module[-3:] != '.py': # DEBUG
		continue
	__import__(module[:-3], locals(), globals())
	__all__.append(module.split(".")[0])
del module, os
