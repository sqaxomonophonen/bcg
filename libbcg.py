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
	def __init__(self, deg=0, axis="Z", rad=None):
		# TODO special case when (deg%90) == 0
		if rad is not None:
			self.rad = rad
		else:
			self.rad = (deg/180.0) * math.pi
		if isinstance(axis, tuple) or isinstance(axis, list):
			self.axis = Vector(axis)
		self.axis = axis
		self.name = "Rotate(rad=%f,axis=%s)" % (self.rad, axis)

	def _tx(self):
		return Matrix.Rotation(self.rad, 4, self.axis)

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

# TODO .. at least convex minkowski sum should be easy... non-convex requires
# decomposition into convex sub-polyhedra and then pairwise doing convex
# minkowski sum on them
"""
class Minkowski(_Group):
	pass
"""


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

def cube(sx=1.0, sy=1.0, sz=1.0, center=False):
	dx=0.0;dy=0.0;dz=0.0
	if center:
		dx=-sx/2.0
		dy=-sy/2.0
		dz=-sz/2.0

	vertices = []
	for z in range(2):
		for y in range(2):
			for x in range(2):
				vertices.append((
					x*sx+dx,
					y*sy+dy,
					z*sz+dz))
	# vertices are now indexed by an xyz bit pattern e.g. for x+y-z- it's
	# 001 (1), and x-y+z+ is 110 (6), etc

	faces = []
	for normal_axis in range(3):
		for sign in [0,1]:
			# face normals must always point away from the cube
			# center. and blender is right handed, so...
			#     finger0 x finger1 = finger2
			# meaning if finger0 and finger1 are edges in a
			# polygon, then its winding must be clockwise when seen
			# from front
			#   x+: y+z- -> y-z- -> y-z+ -> y+z+
			#   y+: z+x- -> z-x- -> z-x+ -> z+x+
			#   z+: x+y- -> x-y- -> x-y+ -> x+y+ -> ...
			# so the pattern is:
			#   00110011001100110 for (axis+1)%3
			#   01100110011001100 for (axis+2)%3
			# played from left to right for normal-positive faces
			# and from right to left for normal-negative faces
			# so:
			faces.append([
				  (sign << normal_axis)
				+ ((((i+sign*2) >> 1) & 1) << ((normal_axis+1)%3))
				+ ((((i+1)      >> 1) & 1) << ((normal_axis+2)%3))
				for i in range(4)
			])
	polyhedron(vertices, faces, name="cube")

def cylinder_segments(segments, loop=False, fn=32):
	assert(len(segments)>=2)

	vertices = []
	seginfo = []
	for z,r in segments:
		seginfo.append((len(vertices), r==0))
		if r != 0:
			for i in range(fn):
				phi = (i/float(fn)) * 2 * math.pi
				x = r * math.cos(phi)
				y = r * math.sin(phi)
				vertices.append((x,y,z))
		else:
			vertices.append((0,0,z))

	faces = []
	n = len(segments)
	ns = n-1
	if loop: ns += 1
	for i0 in range(ns):
		i0 = i0%n
		i1 = (i0+1)%n
		s0offset, s0singular = seginfo[i0]
		s1offset, s1singular = seginfo[i1]
		if s0singular and s1singular: continue # segment would be a line; don't render it

		for j in range(fn):
			j0 = j % fn
			j1 = (j0+1) % fn
			face = []
			if s0singular:
				face.append(s0offset)
			else:
				face.append(s0offset + j0)
				face.append(s0offset + j1)
			if s1singular:
				face.append(s1offset)
			else:
				face.append(s1offset + j1)
				face.append(s1offset + j0)
			faces.append(face)

	if not loop:
		if not seginfo[0][1]: faces.append([i + seginfo[0][0] for i in range(fn-1,-1,-1)])
		if not seginfo[-1][1]: faces.append([i + seginfo[-1][0] for i in range(fn)])

	polyhedron(vertices, faces, name="cylinder_segments")


def sphere(r=1.0, fs=20, fn=32):
	segments = []
	for i in range(fs+1):
		if i == 0:
			segments.append((-r,0))
		elif i == fs:
			segments.append((r,0))
		else:
			phi = math.pi * (i/float(fs))
			z = r * -math.cos(phi)
			rs = r * math.sin(phi)
			segments.append((z,rs))
	cylinder_segments(segments=segments, fn=fn)

def cylinder(r1=1.0, r2=1.0, h=1.0, fn=32, r=None):
	if r is not None:
		r1 = r
		r2 = r
	cylinder_segments(segments = [(0,r1), (h,r2)], fn=fn)

def torus(r1=1.0, r2=0.2, fs=20, fn=32):
	segments = []
	for i in range(fs):
		phi = 2.0*math.pi * (i/float(fs))
		z = r2 * math.sin(phi)
		rs = r1 + r2 * math.cos(phi)
		segments.append((z,rs))
	cylinder_segments(segments=segments, loop=True, fn=fn)

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

			with _Timer("PASS cg for %s" % pname):
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
