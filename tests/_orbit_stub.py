"""A tiny stand-in for the Orbit Local CLI, used by test_orbit_cli_stub.py.

It is NOT a test (leading underscore => pytest does not collect it). The orbit_cli test points
the driver at `[python, this_file]` so a real subprocess exercises the schema/sql path end-to-end
without needing a glab/orbit binary installed in CI. It emits canned, deterministic output.
"""
import sys

sub = sys.argv[1] if len(sys.argv) > 1 else ""
if sub == "schema":
    print("gl_definition(id BIGINT, name VARCHAR, fqn VARCHAR, file_path VARCHAR, definition_type VARCHAR)")
elif sub == "sql":
    print('[{"name": "tokenize"}, {"name": "serialize"}, {"name": "compute_blast_radius"}]')
else:
    sys.stderr.write("unknown subcommand %r\n" % sub)
    sys.exit(2)
