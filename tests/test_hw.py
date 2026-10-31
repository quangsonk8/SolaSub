"""python -m unittest discover tests"""
import unittest

from solasub import hw


class GpuError(unittest.TestCase):
    def test_gpu_errors_fall_back_to_cpu(self):
        from solasub.engine import is_gpu_error
        self.assertTrue(is_gpu_error(RuntimeError("CUDA error: device lost")))
        self.assertTrue(is_gpu_error(RuntimeError("CUDA out of memory. Tried to allocate 2 GiB")))
        self.assertTrue(is_gpu_error(OSError("cublas64_12.dll not found")))

    def test_other_errors_are_reported(self):
        from solasub.engine import is_gpu_error
        self.assertFalse(is_gpu_error(ValueError("bad audio")))
        self.assertFalse(is_gpu_error(RuntimeError("Failed to load audio")))


class ThreadEnv(unittest.TestCase):
    def test_every_pool_is_capped(self):
        env = hw.thread_env(7)
        for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
            self.assertEqual(env[k], "7")
        self.assertEqual(env["KMP_BLOCKTIME"], "0")

    def test_physical_cores_sane(self):
        import os
        n = hw.physical_cores()
        self.assertTrue(1 <= n <= (os.cpu_count() or 1), n)

    def test_engine_does_not_import_numpy(self):
        # engine phai dat bien moi truong truoc khi numpy/torch vao -> import engine khong duoc keo numpy theo
        import subprocess, sys
        code = "import sys, solasub.engine; print('numpy' in sys.modules, 'torch' in sys.modules)"
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "False False")


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
