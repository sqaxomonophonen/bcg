import sys,os; sys.path.append(os.getenv("BCG_DIR")); from libbcg import * # bootstrapping

tx = lambda s: Translate(1*s,2*s,3*s) + Rotate(10+s, axis="X") + Translate(0,0,0)

clear()

def stuff_cg():
	fn = if_hipoly(512,32)
	with tx(1) + Hull():
		cylinder()
		with Translate(0,3,0) + Translate(3,0,0): cylinder(fn=fn)
	with Translate(-2,-2,0) + Difference():
		cylinder()
		with Translate(0,0,-1): cylinder(r=0.5,h=3, fn=fn)
	with Translate(2,-2,0) + Difference():
		cylinder()
		with Translate(0,0,1): sphere(r=0.5, fn=fn)
	with Translate(3,-4,0) + Difference():
		cylinder()
		with Translate(0,0,1): sphere(r=0.5, fn=fn)
mkobj("Stuff", cg=stuff_cg)

save_blend("test")
