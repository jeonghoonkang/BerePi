import json
import unittest
from unittest.mock import patch

import server


class MacGPUTests(unittest.TestCase):
    def test_apple_gpu_detection_without_nvidia_tools(self):
        output = json.dumps({"SPDisplaysDataType": [{"sppci_model": "Apple M4 Max"}]})
        with patch.object(server.platform, "system", return_value="Darwin"), \
                patch.object(server.subprocess, "check_output", return_value=output) as command:
            gpus, error = server.list_gpus()
        self.assertEqual(error, "")
        self.assertEqual(gpus[0]["index"], "metal")
        self.assertTrue(gpus[0]["selectable"])
        self.assertEqual(command.call_args.args[0][0], "/usr/sbin/system_profiler")

    def test_mac_selection_and_environment(self):
        with patch.object(server.platform, "system", return_value="Darwin"), \
                patch.dict(server.os.environ, {"CUDA_VISIBLE_DEVICES": "0"}), \
                patch.object(server, "read_selected_gpu", return_value="metal"):
            for selection in ("metal", "mps", "0"):
                self.assertEqual(server.normalize_gpu_selection(selection), "metal")
            self.assertNotIn("CUDA_VISIBLE_DEVICES", server.ollama_environment())

    def test_cpu_overrides_request_gpu_option(self):
        with patch.object(server, "read_selected_gpu", return_value="cpu"):
            options = server.request_options({"options": {"num_gpu": 99, "temperature": 0.2}})
        self.assertEqual(options["num_gpu"], 0)
        self.assertEqual(options["temperature"], 0.2)

    def test_metal_allows_automatic_offload(self):
        with patch.object(server, "read_selected_gpu", return_value="metal"):
            self.assertNotIn("num_gpu", server.request_options({}))

    def test_linux_cuda_selection_is_preserved(self):
        with patch.object(server.platform, "system", return_value="Linux"), \
                patch.object(server, "read_selected_gpu", return_value="1"), \
                patch.object(server, "cuda_device_for_gpu_selection", return_value="GPU-test"):
            self.assertEqual(server.ollama_environment()["CUDA_VISIBLE_DEVICES"], "GPU-test")


if __name__ == "__main__":
    unittest.main()
