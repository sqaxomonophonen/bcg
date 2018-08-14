
# TODO
#  commands like preview-lopoly, preview-hipoly, preview-full...

import argparse
import distutils.spawn
import sys,os,stat

def fatal(msg):
	sys.stderr.write(msg + "\n")
	sys.exit(1)

def get_blender_path():
	def is_executable(path):
		if not path: return False
		m = os.stat(path)[stat.ST_MODE]
		return not stat.S_ISDIR(m) and bool((m&stat.S_IXUSR) or (m&stat.S_IXGRP) or (m&stat.S_IXOTH))

	path = os.getenv("BCG_BLENDER")
	if is_executable(path): return path

	path = distutils.spawn.find_executable("blender")
	if is_executable(path): return path

	if sys.platform == "darwin":
		# look for blender in standard MacOS location
		for app in ["blender.app", "Blender.app"]:
			path = "/Applications/%s/Contents/MacOS/blender" % app
			if is_executable(path): return path

	fatal("blender not found (search order: BCG_BLENDER environment variable, then 'blender' in $PATH, then platform specific stuff)")


def run_blender(bcgscript, background = False):
	blender_path = get_blender_path()

	argv = [blender_path, "-noaudio"]
	if background: argv += ["-b"]
	argv += ["-P", bcgscript]
	env = {
		"BCG_DIR": os.path.dirname(os.path.realpath(__file__))
	}
	for k,v in os.environ.items():
		env[k] = v
	# TODO pass options in an environment variable? json encoded or
	# something?
	os.execve(blender_path, argv, env)

parser = argparse.ArgumentParser(prog='bcg')
parser.add_argument('--foo', action='store_true', help='foo help me')
subparsers = parser.add_subparsers(dest='cmd', help='sub-command help')

# bcg init
parser_init = subparsers.add_parser('init', help='help for init')
parser_init.add_argument('--bar', action='store_true', help='does bar stuff')

# bcg preview
parser_init = subparsers.add_parser('init', help='help for init')
parser_preview = subparsers.add_parser('preview', help='show scene in blender')
parser_preview.add_argument('bcgscript', metavar='<bcg script>')

# bcg build
parser_build = subparsers.add_parser('build', help='build scene')
parser_build.add_argument('bcgscript', metavar='<bcg script>')

args = parser.parse_args()

if args.cmd is None:
	parser.print_help(sys.stderr)
	sys.exit(1)
elif args.cmd == "preview":
	run_blender(args.bcgscript, background = False)
elif args.cmd == "build":
	run_blender(args.bcgscript, background = True)
else:
	raise RuntimeError("unhandled cmd: %s" % cmd)

