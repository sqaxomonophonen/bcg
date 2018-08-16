import sys,os; sys.path.append(os.getenv("BCG_DIR")); from libbcg import * # bootstrapping

side = 15.0
margin = 1.5
depth = 1
corner_radius = 0.5
corner_segments = 32
corner_indent_depth = 0.4
corner_indent_r = 0.5
corner_indent_size = 1.1
screen_segments = 16
screen_depth = 0.5
screen_r1 = 0.5
screen_r2 = 0.3
button_spacer_segments = 6
button_spacer_r = 0.05
button_spacer_margin = 0.2
n_buttons_per_side = 5
button_spacing = 1.4
button_size = 0.9
button_bevel_depth = 0.05
button_bevel_r1 = 0.10
button_bevel_r2 = 0.05
button_bevel_segments = 4

clear()

def round_square(sx,sy,sz,r1,r2,fn):
	r = max(r1,r2)
	def ctor():
		cylinder(r1=r1,r2=r2,h=sz,fn=fn)
	with Translate(r,r): square_hull(sx-r*2,sy-r*2,ctor)

def round_cut(sx,sy,r,fn):
	def ctor():
		sphere(r=r,fn=fn)
	with Translate(r,r): square_hull(sx-r*2,sy-r*2,ctor)

def panel_outline():
	with Translate(z=-screen_depth):
		round_square(side,side,depth,corner_radius,corner_radius,corner_segments)

def screen_cut():
	r = max(screen_r1,screen_r2)
	m = margin+r
	s = side - m*2 - r*2
	segs = [
		(screen_r2,-depth*2),
		(screen_r2,0),
		(screen_r1,screen_depth),
		(screen_r1,depth*2)
	]
	with Translate(m,m):
		for segments in decompose_cylinder_segments(segs):
			square_hull(s,s,lambda:cylinder_segments(segments,fn=screen_segments))



def button_holes():
	def button_hole(sx=None, sy=None):
		if sx is None: sx = button_size
		if sy is None: sy = button_size
		with Translate(-sx/2.0, -sy/2.0):
			segs = [
				(button_bevel_r2, -depth),
				(button_bevel_r2, screen_depth - button_bevel_depth),
				(button_bevel_r1, screen_depth),
				(button_bevel_r1, screen_depth + depth),
			]
			for segments in decompose_cylinder_segments(segs):
				square_hull(sx,sy,lambda:cylinder_segments(segments,fn=screen_segments))

	for i in range(n_buttons_per_side):
		d = side / 2.0 + (i - n_buttons_per_side/2.0 + 0.5) * button_spacing
		with Translate(d,margin/2.0): button_hole()
		#with Translate(d,side-margin/2.0): button_hole()
		with Translate(margin/2.0,d): button_hole()
		with Translate(side-margin/2.0,d): button_hole()

def corner_indent():
	pass # TODO

def button_spacers():
	pass # TODO

def mfd_cg():
	with Translate(-side/2,-side/2) + Union():
		with Difference():
			panel_outline()
			screen_cut()
			button_holes()
			corner_indent()
		button_spacers()
mkobj("MFD", cg=mfd_cg)
