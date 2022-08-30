# Copyright (c) 2022  PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from auto_scan_test import OPConvertAutoScanTest
from hypothesis import reproduce_failure
import hypothesis.strategies as st
import numpy as np
import unittest
import random


class TestHardSigmoidCovert(OPConvertAutoScanTest):
    """
    ONNX op: HardSigmoid
    OPset version: 7~15
    """

    def sample_convert_config(self, draw):
        input_shape = draw(
            st.lists(
                st.integers(
                    min_value=2, max_value=6), min_size=2, max_size=5))
        input_dtype = draw(st.sampled_from(["float32"]))

        alpha = random.random()

        beta = random.random()

        config = {
            "op_names": ["HardSigmoid"],
            "test_data_shapes": [input_shape],
            "test_data_types": [[input_dtype]],
            "inputs_shape": [input_shape],
            "min_opset_version": 7,
            "inputs_name": ["x"],
            "outputs_name": ["y"],
            "delta": 1e-4,
            "rtol": 1e-4
        }

        attrs = {
            "alpha": alpha,
            "beta": beta,
        }

        return (config, attrs)

    def test(self):
        self.run_and_statis(max_examples=30)


if __name__ == "__main__":
    unittest.main()
