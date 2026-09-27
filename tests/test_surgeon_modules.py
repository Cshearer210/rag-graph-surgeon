"""Wire every surgeon module's selftest into pytest, so CI exercises them and none can rot unseen.
Each module's selftest() returns 0 on success; a nonzero return fails the test with its name.
"""
import unittest

from ragghost.surgeon import (agents, diagnose, fix, gates, grade, graph, index, interview,
                             memory, road, workspace)
from ragghost.surgeon import builders


class TestSurgeonModuleSelftests(unittest.TestCase):
    pass


def _make(mod, name):
    def t(self):
        self.assertEqual(mod.selftest(), 0, "%s.selftest() reported a failure" % name)
    t.__name__ = "test_%s_selftest" % name
    return t


for _mod, _name in [(gates, "gates"), (index, "index"), (graph, "graph"),
                    (diagnose, "diagnose"), (fix, "fix"), (interview, "interview"),
                    (workspace, "workspace"), (memory, "memory"), (grade, "grade"), (agents, "agents"),
                    (builders, "builders"), (road, "road")]:
    setattr(TestSurgeonModuleSelftests, "test_%s_selftest" % _name, _make(_mod, _name))


if __name__ == "__main__":
    unittest.main(verbosity=2)
