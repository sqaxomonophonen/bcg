import bpy
from mathutils import Vector, Matrix
import math
import time
import os
import json

bpy.context.user_preferences.view.show_splash = False # don't show splash

_cg = None
_is_hipoly = None

_args = json.loads(os.getenv("BCG_ARGS"))

def v2normal(v):
	return (v[1], -v[0])

def vadd(v0,v1):
	r = []
	for i in range(len(v0)):
		r.append(v0[i]+v1[i])
	return r

def vsub(v0,v1):
	r = []
	for i in range(len(v0)):
		r.append(v0[i]-v1[i])
	return r

def vdot(v0,v1):
	z = 0
	for i in range(len(v0)):
		z += v0[i]*v1[i]
	return z

def _isincos(x, n):
	x = int(x)
	n = int(n)
	x4 = x*4
	if (x4 % n) == 0:
		isin = lambda i: [0,1,0,-1][i%4]
		icos = lambda i: isin(i+1)
		idx = int(x4/n)
		return (isin(idx), icos(idx))
	else:
		phi = (x/float(n)) * 2.0 * math.pi
		return (math.sin(phi), math.cos(phi))

class _Timer(object):
	def __init__(self, msg):
		self.msg = msg

	def __enter__(self):
		self.t0 = time.time()

	def __exit__(self,a,b,c):
		dt = time.time() - self.t0
		print("%s (took %.2f s)" % (self.msg, dt))

def _join(objs = []):
	nobjs = []
	for obj in objs:
		if obj is None:
			continue
		elif len(obj.data.vertices) == 0:
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

def _dupe(src_obj, name = None):
	dst_obj = src_obj.copy()
	dst_obj.data = src_obj.data.copy()
	if name is not None: dst_obj.name = name
	bpy.context.scene.objects.link(dst_obj)
	return dst_obj

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

	def construct(self, debug = False):
		def crec(ns):
			objs = []
			debug_objs = []
			for n in ns:
				if type(n) is tuple:
					robjs, rdebug_objs = crec(n[1])
					obj = n[0].render(robjs)
					objs.append(obj)
					debug_objs += [n[0].debug_render(o) for o in rdebug_objs]
					if isinstance(n[0], Debug):
						dname = self.name + ".Debug"
						if n[0].tag is not None:
							dname += "." + n[0].tag
						debug_objs.append(_dupe(obj, name = dname))
				else:
					objs.append(n.render())
			return (objs, debug_objs)
		objs, debug_objs = crec(self.optree)
		obj = _join(objs)
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

	def debug_render(self, obj):
		return obj


class _Transform(_Group):
	def render(self, args):
		for obj in args:
			obj.matrix_world = self._tx * obj.matrix_world
		return _join(args)

	def debug_render(self, obj):
		return self.render([obj])

class _Boolean(_Group):
	# solver can be 'CARVE' or 'BMESH'
	def __init__(self, solver='CARVE'):
		self.solver = solver

	def render(self, args):
		if len(args) <= 1: return _join(args)
		a = args[0]
		b = _join(args[1:])
		bop = a.modifiers.new(type="BOOLEAN", name="bool")
		bop.object = b
		bop.operation = self._op
		bop.solver = self.solver
		bpy.context.scene.objects.active = a
		bpy.ops.object.modifier_apply(apply_as='DATA', modifier='bool')
		bpy.data.objects.remove(b)
		return a


class Group(_Group):
	pass

class Debug(_Group):
	def __init__(self, tag=None):
		self.tag = tag

class Translate(_Transform):
	def __init__(self, x=0, y=0, z=0):
		self.tv = Vector((x,y,z))
		self.name = "Translate(%f,%f,%f)" % (x,y,z)
		self._tx = Matrix.Translation(self.tv)

class Rotate(_Transform):
	def __init__(self, deg=0, axis="Z", rad=None):
		if isinstance(axis, tuple) or isinstance(axis, list):
			axis = Vector(axis)
		self.axis = axis
		if rad is not None:
			self.rad = rad
		elif (deg%90) == 0 and axis in ["X","Y","Z"]:
			s, c = _isincos(deg, 360)
			if axis == "X":
				self._tx = Matrix((
					(  1,  0,  0,  0),
					(  0,  c, -s,  0),
					(  0,  s,  c,  0),
					(  0,  0,  0,  1)
				))
			elif axis == "Y":
				self._tx = Matrix((
					(  c,  0,  s,  0),
					(  0,  1,  0,  0),
					( -s,  0,  c,  0),
					(  0,  0,  0,  1)
				))
			elif axis == "Z":
				self._tx = Matrix((
					(  c, -s,  0,  0),
					(  s,  c,  0,  0),
					(  0,  0,  1,  0),
					(  0,  0,  0,  1)
				))
			else:
				raise RuntimeError("unexpected axis value %s" % axis)
			self.rad = (deg/180.0) * math.pi
		else:
			self.rad = (deg/180.0) * math.pi
			self._tx = Matrix.Rotation(self.rad, 4, self.axis)

		self.name = "Rotate(rad=%f,axis=%s)" % (self.rad, axis)


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

# segments is an array of (r,z) pairs (radius,z-position)
# if loop is True, the last segment will be connected to the first segment
# decompose_index can be used to extract 
def cylinder_segments(segments, loop=False, fn=32):
	assert(len(segments)>=2)

	vertices = []
	seginfo = []
	for r,z in segments:
		seginfo.append((len(vertices), r==0))
		if r != 0:
			for i in range(fn):
				s, c = _isincos(i, fn)
				x = r * c
				y = r * s
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

def n_hull(v,ctor):
	sz = len(v)
	n = 2**sz
	with Hull():
		for i in range(n):
			dx = 0
			dy = 0
			dz = 0
			if i&1: dx = v[0]
			if i&2: dy = v[1]
			if i&4: dz = v[2]
			with Translate(dx,dy,dz):
				ctor()

def square_hull(sx,sy,ctor):
	n_hull((sx,sy),ctor)

def cube_hull(sx,sy,sz,ctor):
	n_hull((sx,sy,sz),ctor)

# decomposes into convex cylinder segments (useful e.g. if you want a convex
# hull of each convex group)
def decompose_cylinder_segments(segments, epsilon=1.0/16.0):
	groups = []
	group = []
	prev_point = None
	prev_vec = None
	for r,z in segments:
		point = (r,z)
		if prev_point is not None:
			vec = vsub(point, prev_point)
			dr,dz = vec
			veps = (0,epsilon)
			if dz < 0:
				raise RuntimeError("dz must be zero or positive")
			elif dz == 0:
				if len(group) >= 2:
					group.append(vadd(point,veps))
					groups.append(group)
					group = []
				else:
					group = []
			elif prev_vec is not None:
				cross = vdot(v2normal(vec), prev_vec)
				if cross < 0:
					if dr >= 0:
						group += [vadd(prev_point,veps)]
						groups.append(group)
						group = [prev_point]
					else:
						groups.append(group)
						group = [vsub(prev_point,veps),prev_point]
				prev_cross = cross

			prev_vec = vec
		group.append(point)
		prev_point = (r,z)
	if len(group) > 0: groups.append(group)

	return groups


def sphere(r=1.0, fs=20, fn=32):
	segments = []
	for i in range(fs+1):
		if i == 0:
			segments.append((0,-r))
		elif i == fs:
			segments.append((0,r))
		else:
			s, c = _isincos(i, fs*2)
			z = r * -c
			rs = r * s
			segments.append((rs,z))
	cylinder_segments(segments=segments, fn=fn)

def cylinder(r1=1.0, r2=1.0, h=1.0, fn=32, r=None):
	if r is not None:
		r1 = r
		r2 = r
	cylinder_segments(segments = [(r1,0), (r2,h)], fn=fn)

def torus(r1=1.0, r2=0.2, fs=20, fn=32):
	segments = []
	for i in range(fs):
		s, c = _isincos(i, fs)
		z = r2 * s
		rs = r1 + r2 * c
		segments.append((rs,z))
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
	passes = [(False, name+".Lo")]
	if "preview" not in _args:
		passes += [(True, name+".Hi")]

	for hi, pname in passes:
		global _is_hipoly
		_is_hipoly = hi
		with _Timer("PASS cg for %s" % pname):
			_cg = _CG(pname)
			cg()
			obj = _cg.construct()
			if len(obj.data.vertices) == 0:
				bpy.data.objects.remove(obj)

		_cg = None
		_is_hipoly = None

def clear():
	for bo in bpy.data.objects:
		bpy.data.objects.remove(bo)

def save_blend(name):
	bpy.ops.wm.save_as_mainfile(filepath = "%s.blend" % name)
