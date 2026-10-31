"""python -m unittest discover tests"""
import unittest

from solasub import hw


class CpuLimit(unittest.TestCase):
    def test_half_rounded_up_never_zero(self):
        self.assertEqual([hw.cpu_limit(n) for n in (1, 2, 4, 6, 14)], [1, 1, 2, 3, 7])

    def test_configured_wins_but_not_above_machine(self):
        self.assertEqual(hw.cpu_limit(8, 3), 3)
        self.assertEqual(hw.cpu_limit(8, 99), 8)


class Classify(unittest.TestCase):
    def test_guess_from_install(self):
        self.assertEqual(hw.classify("2.14.1+cu126", True), hw.READY)
        self.assertEqual(hw.classify("2.14.1+cpu", True), hw.NEED_PACK)    # may co GPU nhung chua co goi
        self.assertEqual(hw.classify("2.14.1+cpu", False), hw.NO_NVIDIA)   # AMD / Intel
        self.assertEqual(hw.classify("2.14.1+cu126", False), hw.NO_NVIDIA)

    def test_real_result_from_engine(self):
        self.assertEqual(hw.classify("2.14.1+cu126", True, cuda_available=True), hw.READY)
        self.assertEqual(hw.classify("2.14.1+cu126", True, cuda_available=False), hw.BROKEN)  # driver cu
        self.assertEqual(hw.classify("2.14.1+cpu", True, cuda_available=False), hw.NEED_PACK)

    def test_forced_cpu(self):
        self.assertEqual(hw.classify("2.14.1+cu126", True, True, requested="cpu"), hw.FORCED_CPU)

    def test_every_state_has_text(self):
        for s in (hw.READY, hw.NEED_PACK, hw.NO_NVIDIA, hw.BROKEN, hw.FORCED_CPU):
            self.assertTrue(hw.status_of(s).label and hw.status_of(s).detail)


if __name__ == "__main__":
    unittest.main()
