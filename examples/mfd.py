import sys,os; sys.path.append(os.getenv("BCG_DIR")); from libbcg import * # bootstrapping

side = 15.0
margin = 1.5
depth = 1
corner_radius = 0.5
corner_segments = 32
corner_indent_depth = 0.4
corner_indent_r = 0.5
corner_indent_size = 1.1
screen_segments = 16.0
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


def panel_outline():
	def corner_cut():
		with Difference():
			with Translate(-corner_radius, -corner_radius, -depth/2):
				cube(corner_radius*2, corner_radius*2, depth*2)
			with Translate(corner_radius, corner_radius, -depth):
				cylinder(r = corner_radius, h = depth*3, fn = corner_segments)

	with Difference():
		with Debug(tag = "cub"): cube(side,side,depth)
		with Debug(tag = "cut"):
			corner_cut()
			with Translate(side,0,0)    + Rotate(90,  axis="Z"): corner_cut()
			with Translate(0,side,0)    + Rotate(-90, axis="Z"): corner_cut()
			with Translate(side,side,0) + Rotate(180, axis="Z"): corner_cut()

def screen_cut():
	pass # TODO

def button_holes():
	pass # TODO

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
