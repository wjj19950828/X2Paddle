#   Copyright (c) 2020  PaddlePaddle Authors. All Rights Reserved.
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

import torch
from x2paddle.core.util import *


def prim_Constant(mapper, graph, node):
    """ 构造constant的PaddleLayer，该节点实现常量赋值。

    TorchScript示例:
        %2 : int = prim::Constant[value=-1]()
        参数含义:
        %2 (常量类型由赋值类型定义，该示例中为int型): 常量赋值结果输出。
    """
    output_name = mapper._get_outputs_name(node)[0]
    output = list(node.outputs())[0]
    value = output.toIValue()
    mapper.attrs[output_name] = value
    if isinstance(value, str):
        value = string(value)
    graph.add_layer(
        "prim.constant", inputs={}, outputs=[output_name], value=value)
    return [], [output_name]


def prim_GetAttr(mapper, graph, node):
    """ 获取attribute信息。

    TorchScript示例:
        %27 : Tensor? = prim::GetAttr[name="bias"](%7)
        参数含义:
        %7 (Tensor): 输入Tensor。
        %27 (Tensor): 输入Tensor。
    """
    output_name = mapper._get_outputs_name(node)[0]
    field_name_list = [node.s('name')]
    while True:
        input_node = list(node.inputs())[0].node()
        try:
            field_name_list.insert(0, input_node.s('name'))
            node = input_node
        except Exception:
            break
    if ".".join(field_name_list) in mapper.pytorch_params:
        mapper.pytorch_params[output_name] = mapper.pytorch_params[".".join(
            field_name_list)]
    else:
        part_script = mapper.script
        for field_name in field_name_list:
            if hasattr(part_script, field_name):
                param = getattr(part_script, field_name)
                if isinstance(param, torch.Tensor):
                    param = param.detach().numpy()
                mapper.pytorch_params[output_name] = param
                part_script = param
    return [], [output_name]


def prim_ListConstruct(mapper, graph, node):
    """ 构造list的PaddleLayer。

    TorchScript示例:
        %86 : int[] = prim::ListConstruct(%84, %85)
        参数含义:
        %86 (list): list节点输出。
        %84 (int/其他): list第一个元素信息。
        %85 (int/其他): list第二个元素信息。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理每个输入
    for i, input_name in enumerate(inputs_name):
        layer_inputs["input{}".format(i)] = input_name
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer("prim.list", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_RaiseException(mapper, graph, node):
    """ 构造抛出异常的PaddleLayer。

    TorchScript示例:
        = prim::RaiseException(%76)
        参数含义:
        %76 (str): 异常信息。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理输入0，即%76
    mapper._check_input(graph, inputs_node[0], inputs_name[0], current_outputs)
    layer_inputs["input"] = inputs_name[0]
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer(
        "prim.exception", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_Loop(mapper, graph, node):
    """ 构造loop循环的PaddleLayer。

    TorchScript示例:
        %x : Tensor = prim::Loop(%4, %3, %x.3)
        block0(%i : int, %x.12 : Tensor):
          %72 : int[] = prim::Constant[value=[6, 6]]()
          ...
          %x.5 : Tensor = aten::adaptive_avg_pool2d(%x.12, %_output_size.1)
          -> (%3, %x.5)
       参数含义:
       %4 (int): 循环次数。
       %3 (bool): 是否进入退出。
       %x.3 (Tensor): 循环中修改的Tensor。
       %x (Tensor): loop循环的输出，与%x.5对应。
    """
    node_outputs = mapper._get_outputs_name(node)
    loop_inputs = {}
    block = list(node.blocks())[0]
    loop_outputs = node_outputs.copy()
    for i, block_input_ivalue in enumerate(block.inputs()):
        if i == 0:
            block_input_node_name = '_x' + str(mapper.output_index)
        else:
            block_input_node_name = 'x' + str(mapper.output_index)
        unique_id = block_input_ivalue.unique()
        if unique_id not in mapper.outputs_info:
            mapper.outputs_info[unique_id] = block_input_node_name
            mapper.output_index += 1
        if i == 0:
            loop_input_node = list(node.inputs())[0].node()
            script_loop_input_unique_id = list(node.inputs())[0].unique()
            loop_input_node_name = mapper.outputs_info[
                script_loop_input_unique_id]
            mapper._check_input(graph, loop_input_node, loop_input_node_name,
                                node_outputs)
            loop_inputs['input'] = loop_input_node_name
            loop_outputs.append(block_input_node_name)
            node_outputs.append(block_input_node_name)
        else:
            loop_input_node = list(node.inputs())[i + 1].node()
            script_loop_input_unique_id = list(node.inputs())[i + 1].unique()
            loop_input_node_name = mapper.outputs_info[
                script_loop_input_unique_id]
            mapper._check_input(graph, loop_input_node, loop_input_node_name,
                                node_outputs)
            graph.add_layer(
                "prim.equal",
                inputs={'input': loop_input_node_name},
                outputs=[block_input_node_name])
            node_outputs.append(block_input_node_name)

    graph.add_layer("prim.loop", inputs=loop_inputs, outputs=loop_outputs)
    current_layer = list(graph.layers.values())[-1]
    block_graph, graph_inputs = mapper.traverse(block, current_layer)
    for i, input_name in enumerate(graph_inputs):
        if input_name == loop_outputs[1]:
            continue
        current_layer.inputs['input-{}'.format(i)] = input_name
    current_layer.add_block(block_graph)
    return list(current_layer.inputs.values()), node_outputs


def prim_If(mapper, graph, node):
    """ 构造if控制流的PaddleLayer。

    TorchScript示例:
        %input.5 : Tensor = prim::If(%107)
          block0():
            %109 : Tensor = aten::t(%102)
            %ret.2 : Tensor = aten::addmm(%103, %101, %109, %104, %104)
            -> (%ret.2)
          block1():
            %111 : Tensor = aten::t(%102)
            ...
            -> (%output.4)
        参数含义:
        %107 (bool): if判断条件。
        %input.5 (Tensor): if控制流的输出，与%output.4对应。
    """
    output_name = mapper._get_outputs_name(node)[0]
    node_outputs = [output_name]
    input_node = list(node.inputs())[0].node()
    script_input_unique_id = list(node.inputs())[0].unique()
    input_node_name = mapper.outputs_info[script_input_unique_id]
    mapper._check_input(graph, input_node, input_node_name, node_outputs)
    graph.add_layer("prim.if", {'input': input_node_name}, [output_name])
    current_layer = list(graph.layers.values())[-1]
    block0 = list(node.blocks())[0]
    block0_graph, graph_inputs0 = mapper.traverse(block0, current_layer)
    len0 = 0
    for i, input_name in enumerate(graph_inputs0):
        current_layer.inputs['input-{}'.format(i)] = input_name
        len0 = i
    current_layer.add_block(block0_graph)
    block1 = list(node.blocks())[1]
    block1_graph, graph_inputs1 = mapper.traverse(block1, current_layer)
    for i, input_name in enumerate(graph_inputs1):
        current_layer.inputs['input-{}'.format(len0 + 1 + i)] = input_name
    current_layer.add_block(block1_graph)
    return list(current_layer.inputs.values()), node_outputs


def prim_min(mapper, graph, node):
    """ 构造min的PaddleLayer。

    TorchScript示例:
        %87 : int = prim::min(%86)
        参数含义:
        %86 (list): 输入。
        %87 (int): 输出。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理输入0，即%86
    mapper._check_input(graph, inputs_node[0], inputs_name[0], current_outputs)
    layer_inputs["input"] = inputs_name[0]
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer("prim.min", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_requires_grad(mapper, graph, node):
    """ 构造是否计算梯度的PaddleLayer。

    TorchScript示例:
        %356 : bool = prim::requires_grad(%tensor.31)
        参数含义:
        %356 (bool): 输出，当前Tensor是否计算梯度。
        %tensor.31 (Tensor): 输入的Tensor。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理输入0，即%86
    mapper._check_input(graph, inputs_node[0], inputs_name[0], current_outputs)
    layer_inputs["input"] = inputs_name[0]
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer(
        "prim.requires_grad", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_SetAttr(mapper, graph, node):
    """ 设置attribute信息。

    TorchScript示例:
        = prim::SetAttr[name="num_batches_tracked"](%260, %277)
        参数含义:
        %260 (-): 属性名前缀。
        %277 (-): 需要设置的值。
    """
    output_name = mapper._get_outputs_name(node)[0]
    field_name_list = []
    tmp_node = node
    while True:
        input_node = list(tmp_node.inputs())[0].node()
        try:
            field_name_list.insert(0, input_node.s('name'))
            tmp_node = input_node
        except Exception:
            break
    field_name_list.append(node.s('name'))

    inputs_name, inputs_node = mapper._get_inputs_name(node)
    param = {"Tensor": inputs_name[1]}
    mapper.pytorch_params[".".join(field_name_list)] = param
    return [], [output_name]


def prim_shape(mapper, graph, node):
    """ 构造获取shape的PaddleLayer。

    TorchScript示例:
        %4701 : int[] = prim::shape(%result.1)
        参数含义:
        %4701 (list): 输出，shape信息。
        %result.1 (Tensor): 需要获取shape的值。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理输入0，即%input.8
    mapper._check_input(graph, inputs_node[0], inputs_name[0], current_outputs)
    layer_inputs["input"] = inputs_name[0]
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer("prim.shape", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_TupleConstruct(mapper, graph, node):
    """ 构造tuple的PaddleLayer。

    TorchScript示例:
        %4492 : (Tensor, Tensor?) = prim::TupleConstruct(%x.46, %aux)
        参数含义:
        %4492 (tuple): 输出，tuple。
        %x.46 (Tensor/其他): tuple第一个元素信息。
        %aux (Tensor/其他): tuple第二个元素信息。
    """
    output_name = mapper._get_outputs_name(node)[0]
    layer_outputs = [output_name]
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = [output_name]
    # 处理每个输入
    for i, input_name in enumerate(inputs_name):
        layer_inputs["input{}".format(i)] = input_name
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer("prim.tuple", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_TupleUnpack(mapper, graph, node):
    """ 构造获取tuple元素的PaddleLayer。

    TorchScript示例:
        %x.223 : Tensor, %aux.3 : Tensor? = prim::TupleUnpack(%4492)
        参数含义:
        %x.223 (Tensor/其他): 输出，tuple第一个元素信息。
        %aux.3 (Tensor/其他): 输出，tuple第二个元素信息。
        %4492 (tuple): 需要获取元素的tuple。
    """
    outputs_name = mapper._get_outputs_name(node)
    layer_outputs = outputs_name
    layer_inputs = {}
    inputs_name, inputs_node = mapper._get_inputs_name(node)
    # 获取当前节点输出的list
    current_outputs = outputs_name
    layer_inputs["input"] = inputs_name[0]
    # 获取当前节点输入的list
    current_inputs = list(layer_inputs.values())

    graph.add_layer(
        "prim.tuple_unpack", inputs=layer_inputs, outputs=layer_outputs)
    return current_inputs, current_outputs


def prim_Uninitialized(mapper, graph, node):
    """ 构造表示编译器永远不会使用的值的PaddleLayer，该节点转换为None。

    TorchScript示例:
        %345 : bool = prim::Uninitialized()
        参数含义:
        %345 (bool): 输出，为赋值的bool。
    """
    output_name = mapper._get_outputs_name(node)[0]
    output = list(node.outputs())[0]
    mapper.attrs[output_name] = None
    graph.add_layer(
        "prim.constant", inputs={}, outputs=[output_name], value=None)
    return [], [output_name]
