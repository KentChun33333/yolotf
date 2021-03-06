"""
file: ./ops.py
includes: convl, batchnorm, dense, maxpool, etc
functions that takes input `x`, layer `l` of type layer
defined in ./darknet.py and return the output of the
corresponding layer.
"""
from yolo.train import *

def _shape(tensor):
	if hasattr(tensor, 'shape'): return tensor.shape
	else: return tensor.get_shape()

class tfop(object):
	def __init__(self, l, x, name, feed = None):
		if feed is not None: self.wrap(l, feed, name)
		if 'tfnetoutput' in name: name = 'output'
		
		self.l = l; self.inp_layer = False
		self.inp_layer = x.name[:5] == 'input'
		self.inp_size = x.get_shape()
		self.forward(l, x, name)

	def __call__(self, verbalise = True):
		if verbalise: self.verbalise()
		return self.x

	def wrap(self, layer, feed, name):
		"""
		wraps `layer` into tf variables & placeholder
		"""
		for var in layer.w: # trainable vars
			sig = '{}-{}'.format(name, var)
			layer.w[var] = tf.Variable(layer.w[var],name=sig)
		
		for ph in layer.h: # placeholders
			sig = '{}-{}'.format(name, ph)
			val = layer.h[ph]; s = val['size']
			layer.h[ph] = tf.placeholder(tf.float32,s,sig)
			feed[layer.h[ph]] = val

	def verbalise(self):
		self.detail()
		form = '{:<40} : {}'
		if self.inp_layer:
			print form.format('Input size', self.inp_size)
		print form.format(self.msg, self.x.get_shape())

class conv(tfop):
	def forward(self, l, x, name):
		if l.pad < 0: # figure the pad out
			size = np.int(x.get_shape()[1])
			expect = -(l.pad + 1) * l.stride 
			expect += l.size - size
			padding = [expect / 2, expect - expect / 2]
			if padding[0] < 0: padding[0] = 0
			if padding[1] < 0: padding[1] = 0
		else:
			padding = [l.pad, l.pad]
		x = tf.pad(x, [[0, 0], padding, padding, [0, 0]])
		x = tf.nn.conv2d(x, l.w['kernel'], padding = 'VALID', 
	        name = name,strides=[1, l.stride, l.stride, 1])
		if l.batch_norm: x = self.batchnorm(l, x, name+'-bnorm')
		self.x = tf.nn.bias_add(x, l.w['biases'])
		self.pad = padding

	def batchnorm(self, l, x, name):
		return tf.nn.batch_normalization(
			x = x, mean = l.w['mean'], variance = l.w['var'], 
			offset = None, scale = l.w['scale'], name = name,
			variance_epsilon = 1e-6)

	def detail(self):
		msg = 'conv{}'.format(_shape(self.l.w['kernel']))
		self.msg = '{:<23} pad{}'.format(msg, self.pad)

class full(tfop):
	def forward(self, l, x, name):
		self.x = tf.nn.xw_plus_b(x, l.w['weights'], 
			l.w['biases'], name = name)

	def detail(self):
		self.msg = 'full{}'.format(_shape(self.l.w['weights']))

class flatten(tfop):
	def forward(self, l, x, name):
		x = tf.transpose(x, [0,3,1,2])
		self.x = slim.flatten(x, scope = name)

	def detail(self):
		self.msg = 'flat()'

class maxpool(tfop):
	def forward(self, l, x, name):
		self.x = tf.nn.max_pool(x, padding = 'VALID',
	        ksize = [1,l.size,l.size,1], name = name, 
	        strides = [1,l.stride,l.stride,1])
	
	def verbalise(self): pass

class leaky(tfop):
	def forward(self, l, x, name):
		self.x = tf.maximum(.1*x, x, name = name)

	def verbalise(self): pass

class dropout(tfop):
	def forward(self, l, x, name):
		self.x = tf.nn.dropout(x, l.h['pdrop'], name = name)

	def verbalise(self): pass

op_types = {
	'convolutional': conv,
	'connected': full,
	'maxpool': maxpool,
	'leaky': leaky,
	'dropout': dropout,
	'flatten': flatten
}

def op_create(*args):
	layer_type = list(args)[0].type
	return op_types[layer_type](*args)