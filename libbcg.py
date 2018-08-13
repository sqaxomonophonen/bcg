import bpy
from mathutils import Vector, Matrix
import math
import time

bpy.context.user_preferences.view.show_splash = False # don't show splash

_cg = None
_is_hipoly = None
_is_debug_pass = None

class _Timer(object):
	def __init__(self, msg):
		self.msg = msg

	def __enter__(self):
		self.t0 = time.time()

	def __exit__(self,a,b,c):
		dt = time.time() - self.t0
		print("%s (took %.2f s)" % (self.msg, dt))

class _CG(object):
	def __init__(self, name):
		self.name = name
		self.optree = []
		self.stack = [self.optree]

	def enter(self, o):
		children = []
		self.stack[-1].append((o, children))
		self.stack.append(children)

	def exit(self):
		self.stack.pop()
		assert len(self.stack) >= 1

	def emit(self, o):
		self.stack[-1].append(o)

	def construct(self):
		def crec(ns, vis):
			results = []
			for n in ns:
				if type(n) is tuple:
					pvis = vis
					if isinstance(n[0], Debug):
						pvis = True
					results.append(n[0].render(crec(n[1], pvis)))
				elif vis:
					results.append(n.render())
			return results
		vis = not _is_debug_pass
		obj = _join(crec(self.optree, vis))
		obj.name = self.name
		#obj.color = [1,0,0,0.2] # TODO useful for debugging, but requires an "object color material"
		return obj

	def dump(self):
		def drec(ns, depth = 0):
			for n in ns:
				name = None
				if type(n) is tuple:
					name = n[0].name
				else:
					name = n.name
				print(". " * depth + name)
				if type(n) is tuple:
					drec(n[1], depth+1)
		drec(self.optree)



class _Pair(object):
	def __init__(self, a, b):
		self.a = a
		self.b = b

	def __enter__(self):
		global _cg
		self.a.__enter__()
		self.b.__enter__()

	def __exit__(self,a,b,c):
		global _cg
		self.b.__exit__(None,None,None)
		self.a.__exit__(None,None,None)

	def __add__(self, other):
		return _Pair(self, other)


def _join(objs = []):
	nobjs = []
	for obj in objs:
		if len(obj.data.vertices) == 0:
			bpy.data.objects.remove(obj)
		else:
			nobjs.append(obj)
	objs = nobjs

	if len(objs) == 0:
		mesh = bpy.data.meshes.new(name="join")
		mesh.from_pydata([], [], [])
		obj = bpy.data.objects.new("dummy", mesh)
		bpy.context.scene.objects.link(obj)
		return obj
	if len(objs) == 1:
		return objs[0]
	ctx = bpy.context.copy()
	ctx['active_object'] = objs[0]
	ctx['selected_objects'] = objs
	ctx['selected_editable_bases'] = [bpy.context.scene.object_bases[obj.name] for obj in objs]
	bpy.ops.object.join(ctx)
	return objs[0]

class _Group(object):
	def __enter__(self):
		global _cg
		assert _cg is not None
		_cg.enter(self)

	def __exit__(self,a,b,c):
		global _cg
		_cg.exit()

	def __add__(self, other):
		return _Pair(self, other)

	def render(self, args):
		return _join(args)


class _Transform(_Group):
	def render(self, args):
		tx = self._tx()
		for obj in args:
			obj.matrix_world = tx * obj.matrix_world
		return _join(args)

class _Boolean(_Group):
	def render(self, args):
		global _is_debug_pass
		if _is_debug_pass: return _join(args)
		if len(args) <= 1: return _join(args)
		a = args[0]
		b = _join(args[1:])
		bop = a.modifiers.new(type="BOOLEAN", name="bool")
		bop.object = b
		bop.operation = self._op
		bpy.context.scene.objects.active = a
		bpy.ops.object.modifier_apply(apply_as='DATA', modifier='bool')
		bpy.data.objects.remove(b)
		return a


class Group(_Group):
	pass

class Debug(_Group):
	pass # XXX TODO should render subtree in separate object regardless of parent nodes

class Translate(_Transform):
	def __init__(self, x=0, y=0, z=0):
		self.tv = Vector((x,y,z))
		self.name = "Translate(%f,%f,%f)" % (x,y,z)

	def _tx(self):
		return Matrix.Translation(self.tv)

class Rotate(_Transform):
	def __init__(self, a=0, axis="Z"):
		self.angle = a
		if isinstance(axis, tuple) or isinstance(axis, list):
			self.axis = Vector(axis)
		self.axis = axis
		self.name = "Rotate(%f,%s)" % (a, axis)

	def _tx(self):
		return Matrix.Rotation(self.angle, 4, self.axis)

class Union(_Boolean):
	_op = "UNION"
	name = "Union"

class Difference(_Boolean):
	_op = "DIFFERENCE"
	name = "Difference"

class Intersection(_Boolean):
	_op = "INTERSECT"
	name = "Intersection"

class Hull(_Group):
	name = "Hull"
	def render(self, args):
		global _is_debug_pass
		if _is_debug_pass: return _join(args)
		obj = _join(args)
		bpy.context.scene.objects.active = obj
		bpy.ops.object.mode_set(mode = 'EDIT')
		bpy.ops.mesh.convex_hull()
		bpy.ops.object.mode_set(mode = 'OBJECT')
		return obj

class Minkowski(_Group):
	# TODO .. at least convex minkowski sum should be easy... non-convex
	# requires decomposition into convex sub-polyhedra and then pairwise
	# doing convex minkowski sum on them
	pass


# TODO smoothing
class polyhedron(object):
	def __init__(self, vertices, faces, name="tmp"):
		self.vertices = vertices
		self.faces = faces
		self.name = name
		global _cg
		_cg.emit(self)
	def render(self):
		mesh = bpy.data.meshes.new(name=self.name)
		mesh.from_pydata(self.vertices, [], self.faces)
		obj = bpy.data.objects.new(self.name, mesh)
		bpy.context.scene.objects.link(obj)
		return obj

# TODO sphere and cylinder can be generalized as cylinder_segments() that takes
# z/r-pairs + fn (and it would be useful for other stuff)


def sphere(r=1.0, fs=20, fn=32):
	vertices = []

	vertices.append((0,0,r))
	vertices.append((0,0,-r))
	for i in range(1,fs):
		pho = math.pi * (i/float(fs))
		z = r * math.cos(pho)
		r2 = r * math.sin(pho)
		for j in range(fn):
			phi = (j/float(fn)) * 2 * math.pi
			x = r2 * math.cos(phi)
			y = r2 * math.sin(phi)
			vertices.append((x,y,z))

	gv = lambda i,j: 2 + (j%fn) + i*fn
	faces = []
	for i in range(fs):
		for j in range(fn):
			if i == 0:
				faces.append([0,gv(i,j),gv(i,j+1)])
			elif i == fs-1:
				faces.append([1,gv(i-1,j+1),gv(i-1,j)])
			else:
				faces.append([
					gv(i-1,j),
					gv(i,j),
					gv(i,j+1),
					gv(i-1,j+1),
				])

	polyhedron(vertices, faces, name="sphere")

def cylinder(r=1.0, h=1.0, fn=32):
	vertices = []
	for i in range(fn):
		phi = (i/float(fn)) * 2 * math.pi
		x = r * math.cos(phi)
		y = r * math.sin(phi)
		vertices.append((x,y,0))
		vertices.append((x,y,h))

	faces = []
	for i in range(fn):
		v0 = i * 2
		v1 = ((i+1) % fn) * 2
		faces.append([v0,v1,v1+1,v0+1])
	faces.append([x for x in range(1,fn*2,2)])
	faces.append([x for x in range(fn*2-2,0,-2)])

	polyhedron(vertices, faces, name="cylinder")


# returns True if this is a high polygon pass, otherwise False
def hipoly():
	global _is_hipoly
	assert _is_hipoly is not None
	return _is_hipoly

# returns hipoly_val if hipoly() is True, otherwise lopoly_val
def if_hipoly(hipoly_val, lopoly_val):
	if hipoly():
		return hipoly_val
	else:
		return lopoly_val

# cg: constructive geometry pass: typically called twice for low/high poly; see hipoly()
# prep: mesh preparation; do culling/seaming here
# paint: texture painting...
# instance: (optional) object instancing
# godot_export: material setup, resource binding, etc (TODO there should also
#               be a global export for doing the final preparation stuff...)
def mkobj(name, cg=None, prep=None, paint=None, instance=None, godot_export=None):
	assert(cg is not None)
	global _cg

	# TODO quick preview for either of these? i.e. only render one of them
	passes = [(False, name+".Lo"), (True, name+".Hi")]

	objs = []
	for is_debug in [False, True]:
		for hi, pname in passes:
			global _is_hipoly
			_is_hipoly = hi

			global _is_debug_pass
			_is_debug_pass = is_debug

			if is_debug: pname += ".Debug"

			with _Timer("PASS cg for %s (debug=%s)" % (pname, is_debug)):
				_cg = _CG(pname)
				cg()
				obj = _cg.construct()
				if len(obj.data.vertices) == 0:
					bpy.data.objects.remove(obj)
				objs.append(obj)

			_cg = None
			_is_hipoly = None
			_is_debug_pass = None

def clear():
	for bo in bpy.data.objects:
		bpy.data.objects.remove(bo)

def save_blend(name):
	bpy.ops.wm.save_as_mainfile(filepath = "%s.blend" % name)
